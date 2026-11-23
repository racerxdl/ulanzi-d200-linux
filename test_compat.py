"""Compatibility with older systemd and GLib releases (e.g. Ubuntu 22.04)."""

import subprocess
import unittest
from unittest import mock

from ulanzi_manager import actions


def _version_output(text):
    return subprocess.CompletedProcess(['systemd-run', '--version'], 0, stdout=text, stderr='')


class SystemdRunCompatibilityTests(unittest.TestCase):
    def setUp(self):
        actions._systemd_run_expands_environment.cache_clear()
        self.addCleanup(actions._systemd_run_expands_environment.cache_clear)

    def _expands(self, **run_kwargs):
        with mock.patch.object(actions.subprocess, 'run', **run_kwargs):
            return actions._systemd_run_expands_environment()

    def test_systemd_249_omits_expand_environment(self):
        output = _version_output('systemd 249 (249.11-0ubuntu3.23)\n+PAM +AUDIT\n')
        self.assertFalse(self._expands(return_value=output))

    def test_systemd_254_and_newer_use_expand_environment(self):
        for version in ('254 (254.5-1)', '257 (257.4)'):
            with self.subTest(version=version):
                actions._systemd_run_expands_environment.cache_clear()
                output = _version_output(f'systemd {version}\n')
                self.assertTrue(self._expands(return_value=output))

    def test_unreadable_version_omits_expand_environment(self):
        self.assertFalse(self._expands(return_value=_version_output('')))
        actions._systemd_run_expands_environment.cache_clear()
        self.assertFalse(self._expands(side_effect=OSError('systemd-run missing')))

    def test_launch_command_follows_version(self):
        for supported, expected in ((True, True), (False, False)):
            with self.subTest(supported=supported), \
                    mock.patch.object(actions, '_systemd_run_expands_environment', return_value=supported), \
                    mock.patch.object(actions.subprocess, 'Popen') as popen:
                actions._launch_independent(['/bin/true'])
                command = popen.call_args.args[0]
                self.assertEqual('--expand-environment=no' in command, expected)
                self.assertEqual(command[-2:], ['--', '/bin/true'])


class NativeProbeCompatibilityTests(unittest.TestCase):
    def test_probe_accepts_gio_when_giounix_is_missing(self):
        from ulanzi_manager import native
        self.assertIn("DesktopGio = Gio", native._PROBE)
        compile(native._PROBE, '<probe>', 'exec')


if __name__ == '__main__':
    unittest.main()
