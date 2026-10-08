import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from ulanzi_manager.config import ConfigParser


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


if __name__ == "__main__":
    unittest.main()
