"""Key action: ydotool translation (Wayland) with xdotool fallback."""

import os
import subprocess
import unittest
from unittest.mock import patch

from ulanzi_manager.actions import KeyAction, ydotool_sequence, ydotool_socket


class YdotoolSequenceTest(unittest.TestCase):
    def test_presses_in_order_and_releases_in_reverse(self):
        self.assertEqual(
            ydotool_sequence("ctrl+shift+tab"),
            ["29:1", "42:1", "15:1", "15:0", "42:0", "29:0"],
        )

    def test_single_keys_digits_and_function_keys(self):
        self.assertEqual(ydotool_sequence("super"), ["125:1", "125:0"])
        self.assertEqual(ydotool_sequence("Print"), ["99:1", "99:0"])
        self.assertEqual(ydotool_sequence("ctrl+0")[1], "11:1")
        self.assertEqual(ydotool_sequence("ctrl+1")[1], "2:1")
        self.assertEqual(ydotool_sequence("alt+f4")[1], "62:1")
        self.assertEqual(ydotool_sequence("f12"), ["88:1", "88:0"])

    def test_rejects_unknown_or_empty(self):
        with self.assertRaises(ValueError):
            ydotool_sequence("ctrl+ç")
        with self.assertRaises(ValueError):
            ydotool_sequence(" + ")

    def test_socket_defaults_to_runtime_dir(self):
        with patch.dict(os.environ, {"XDG_RUNTIME_DIR": "/run/user/42"}, clear=True):
            self.assertEqual(ydotool_socket(), "/run/user/42/.ydotool_socket")
        with patch.dict(os.environ, {"YDOTOOL_SOCKET": "/tmp/x"}, clear=True):
            self.assertEqual(ydotool_socket(), "/tmp/x")


class KeyActionTest(unittest.TestCase):
    def test_uses_ydotool_when_available(self):
        with patch("ulanzi_manager.actions.shutil.which", return_value="/usr/bin/ydotool"), \
                patch("ulanzi_manager.actions.subprocess.run") as run:
            KeyAction().execute({"keys": "ctrl+tab"})
        args = run.call_args.args[0]
        self.assertEqual(args, ["ydotool", "key", "29:1", "15:1", "15:0", "29:0"])
        self.assertIn("YDOTOOL_SOCKET", run.call_args.kwargs["env"])

    def test_falls_back_to_xdotool(self):
        with patch("ulanzi_manager.actions.shutil.which", return_value=None), \
                patch("ulanzi_manager.actions.subprocess.run") as run:
            KeyAction().execute({"keys": "ctrl+tab"})
        self.assertEqual(run.call_args.args[0], ["xdotool", "key", "ctrl+tab"])

    def test_failure_is_logged_not_raised(self):
        error = subprocess.CalledProcessError(1, "ydotool", stderr=b"socket missing")
        with patch("ulanzi_manager.actions.shutil.which", return_value="/usr/bin/ydotool"), \
                patch("ulanzi_manager.actions.subprocess.run", side_effect=error), \
                self.assertLogs("ulanzi_manager.actions", "ERROR") as logs:
            KeyAction().execute({"keys": "super"})
        self.assertIn("socket missing", logs.output[0])


if __name__ == "__main__":
    unittest.main()
