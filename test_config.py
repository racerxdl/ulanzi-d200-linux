import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from ulanzi_manager.config import ButtonConfig, Config, ConfigParser, parse_content_margin, parse_metrics_style


class FirstRunConfigTests(unittest.TestCase):
    def test_missing_parent_receives_valid_self_contained_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new" / "profile" / "config.yaml"
            ConfigParser.ensure_default(str(path))
            config = ConfigParser.load(str(path))
            self.assertEqual([], ConfigParser.validate(config))
            self.assertEqual([13], [button.index for button in config.buttons])
            self.assertEqual("stats", config.buttons[0].display_mode)
            self.assertTrue(all(not button.action_enabled for button in config.buttons))
            self.assertTrue(all(not button.image and not button.icon_spec for button in config.buttons))

    def test_existing_configuration_and_symlink_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "personal.yaml"
            original = b"# Keep comments and formatting\nbrightness: 37\nbuttons: []\n"
            path.write_bytes(original)
            alias = path.with_name("config.yaml")
            alias.symlink_to(path.name)
            ConfigParser.ensure_default(str(alias))
            ConfigParser.ensure_default(str(path))
            self.assertTrue(alias.is_symlink())
            self.assertEqual(path.name, str(alias.readlink()))
            self.assertEqual(original, path.read_bytes())

    def test_config_created_during_provisioning_wins_without_partial_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new" / "config.yaml"
            preparing = threading.Event()
            release = threading.Event()
            failures = []
            dump = yaml.safe_dump

            def paused_dump(*args, **kwargs):
                preparing.set()
                if not release.wait(5):
                    raise TimeoutError("Provisioning was not released")
                return dump(*args, **kwargs)

            def provision():
                try:
                    ConfigParser.ensure_default(str(path))
                except BaseException as error:
                    failures.append(error)

            creator = threading.Thread(target=provision)
            original = b"# Concurrent user save\nbrightness: 42\nbuttons: []\n"
            with patch("ulanzi_manager.config.yaml.safe_dump", side_effect=paused_dump):
                creator.start()
                try:
                    self.assertTrue(preparing.wait(5))
                    self.assertFalse(path.exists())
                    path.write_bytes(original)
                finally:
                    release.set()
                    creator.join(5)
            self.assertFalse(creator.is_alive())
            self.assertEqual([], failures)
            self.assertEqual(original, path.read_bytes())
            self.assertEqual(["config.yaml"], sorted(item.name for item in path.parent.iterdir()))

    def test_failed_preparation_does_not_leave_an_incomplete_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "new" / "config.yaml"
            with patch("ulanzi_manager.config.yaml.safe_dump", side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    ConfigParser.ensure_default(str(path))
            self.assertFalse(path.exists())
            self.assertEqual([], list(path.parent.iterdir()))


class ContentMarginConfigTests(unittest.TestCase):
    def test_default_and_boundary_values_survive_config_loading(self):
        for margin in (None, 0, 24, 48):
            with self.subTest(margin=margin), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.yaml"
                button = {"index": 13, "display_mode": "stats", "action_enabled": False}
                if margin is not None:
                    button["content_margin"] = margin
                path.write_text(yaml.safe_dump({"buttons": [None] * 13 + [button]}))
                config = ConfigParser.load(str(path))
                self.assertEqual(margin or 0, config.buttons[0].content_margin)
                self.assertEqual([], ConfigParser.validate(config))
        self.assertEqual(0, parse_content_margin())
        self.assertEqual(0, parse_metrics_style()["content_margin"])
        self.assertEqual(48, parse_metrics_style({"content_margin": 48})["content_margin"])

    def test_invalid_margin_rejected_in_both_serialized_locations(self):
        for margin in (-1, 49, True, False, 2.5, "12", None):
            with self.subTest(margin=margin):
                with self.assertRaises(ValueError):
                    parse_content_margin(margin)
                with self.assertRaises(ValueError):
                    ConfigParser._parse_button(13, {"content_margin": margin}, Path("."))
                with self.assertRaises(ValueError):
                    parse_metrics_style({"content_margin": margin})

    def test_programmatic_configuration_is_validated(self):
        config = Config(buttons=[ButtonConfig(
            index=13, image=None, label="", action_type="command", action_params={},
            action_enabled=False, display_mode="stats", content_margin=49,
        )])
        self.assertTrue(any("Espaço interno" in error for error in ConfigParser.validate(config)))


if __name__ == "__main__":
    unittest.main()
