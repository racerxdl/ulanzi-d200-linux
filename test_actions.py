"""Real user-systemd regression: launched work must survive daemon restart."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

from ulanzi_manager.native_python import native_python


class IndependentLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('systemd-run'):
            raise unittest.SkipTest('systemd-run is unavailable')
        manager = subprocess.run(
            ['systemctl', '--user', 'show', '--property=Version', '--value'],
            capture_output=True, text=True, timeout=10,
        )
        if manager.returncode:
            raise unittest.SkipTest('No running user systemd manager')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ulanzi-action-')
        self.root = Path(self.temporary.name)
        self.unit = f'ulanzi-action-test-{uuid.uuid4().hex}.service'
        self.scopes = set()
        self.repo = Path(__file__).resolve().parent
        self.ready = self.root / 'ready.json'
        self.finish = self.root / 'finish'
        self.done = self.root / 'done.json'
        self.cwd = self.root / 'working directory'
        self.cwd.mkdir()
        self.probe = self.root / 'probe app'
        self.probe.write_text(
            f'#!{sys.executable}\n'
            'import json, os, sys, time\n'
            'from pathlib import Path\n'
            'record = {"pid": os.getpid(), "cwd": os.getcwd(),\n'
            '          "args": sys.argv[1:], "token": os.environ["ACTION_TOKEN"],\n'
            '          "cgroup": Path("/proc/self/cgroup").read_text()}\n'
            'def publish(name, value):\n'
            '    target = Path(os.environ[name])\n'
            '    temporary = target.with_suffix(".tmp")\n'
            '    temporary.write_text(json.dumps(value))\n'
            '    temporary.replace(target)\n'
            'publish("ACTION_READY", record)\n'
            'deadline = time.monotonic() + 30\n'
            'while not Path(os.environ["ACTION_FINISH"]).exists():\n'
            '    if time.monotonic() >= deadline: sys.exit(2)\n'
            '    time.sleep(0.02)\n'
            'record["result"] = 20 + 22\n'
            'publish("ACTION_DONE", record)\n',
            encoding='utf-8',
        )
        self.probe.chmod(0o700)

    def tearDown(self):
        # Stop only units created by this test, never the real daemon.
        if self.ready.exists():
            record = json.loads(self.ready.read_text())
            self.scopes.add(Path(record['cgroup'].split(':', 2)[2].strip()).name)
        for unit in [self.unit, *self.scopes]:
            subprocess.run(
                ['systemctl', '--user', 'stop', unit],
                capture_output=True, timeout=10,
            )
        self.temporary.cleanup()

    def _wait_record(self, path):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if path.exists():
                return json.loads(path.read_text())
            time.sleep(0.02)
        journal = subprocess.run(
            ['journalctl', '--user', '-u', self.unit, '-n', '20', '--no-pager'],
            capture_output=True, text=True, timeout=10,
        )
        self.fail(f'Application did not complete {path.name}: {journal.stdout}')

    def _exercise(self, handler, params, expected_args, extra_environment=None):
        token = "literal $HOME and quote's"
        code = (
            'import sys, time; from pathlib import Path; '
            f'sys.path.insert(0, {str(self.repo)!r}); '
            f'from ulanzi_manager.actions import {handler}; '
            f'\nif not Path({str(self.ready)!r}).exists():\n'
            f'    {handler}().execute({params!r})\n'
            'time.sleep(120)\n'
        )
        command = [
            'systemd-run', '--user', '--quiet', '--collect',
            '--expand-environment=no',
            '--unit', self.unit, '--property=Type=exec',
            '--working-directory', str(self.cwd),
        ]
        environment = {
            'ACTION_READY': str(self.ready), 'ACTION_FINISH': str(self.finish),
            'ACTION_DONE': str(self.done), 'ACTION_TOKEN': token,
        }
        environment.update(extra_environment or {})
        for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS'):
            if key in os.environ:
                environment[key] = os.environ[key]
        command.extend(f'--setenv={key}={value}' for key, value in environment.items())
        command.extend([sys.executable, '-c', code])
        subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)
        initial = self._wait_record(self.ready)
        scope = Path(initial['cgroup'].split(':', 2)[2].strip()).name
        self.assertTrue(scope.endswith('.scope'), initial['cgroup'])
        self.assertNotIn(self.unit, initial['cgroup'])
        self.scopes.add(scope)
        before = subprocess.run(
            ['systemctl', '--user', 'show', self.unit, '--property=MainPID', '--value'],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        subprocess.run(
            ['systemctl', '--user', 'restart', self.unit],
            capture_output=True, text=True, check=True, timeout=10,
        )
        after = subprocess.run(
            ['systemctl', '--user', 'show', self.unit, '--property=MainPID', '--value'],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
        self.assertNotEqual(before, after)
        # The same launched process must finish useful work after parent restart.
        self.finish.touch()
        completed = self._wait_record(self.done)
        self.assertEqual(completed['pid'], initial['pid'])
        self.assertEqual(completed['result'], 42)
        self.assertEqual(completed['args'], expected_args)
        self.assertEqual(completed['token'], token)
        self.assertEqual(completed['cwd'], str(self.cwd))

    def test_command_survives_restart_with_shell_expansion_and_quoting(self):
        command = f'{shlex.quote(str(self.probe))} "$ACTION_TOKEN" "two words"'
        self._exercise(
            'CommandAction', {'cmd': command}, ["literal $HOME and quote's", 'two words'],
        )

    def test_manual_application_survives_restart_with_spaces_in_path(self):
        self._exercise('AppAction', {'name': str(self.probe)}, [])

    def test_wrapped_desktop_application_survives_restart(self):
        try:
            python, environment = native_python()
        except RuntimeError as error:
            self.skipTest(str(error))
        native = subprocess.run(
            [*python, '-c',
             'import gi; gi.require_version("Gdk", "3.0"); '
             'from gi.repository import Gdk; Gdk.init_check([]); '
             'raise SystemExit(Gdk.Display.get_default() is None)'],
            env=environment, capture_output=True, timeout=10,
        )
        if native.returncode:
            self.skipTest('Graphical display unavailable')
        module_path = subprocess.check_output(
            [*python, '-c', 'import gi; from pathlib import Path; print(Path(gi.__file__).parent.parent)'],
            env=environment, text=True,
        ).strip()
        wrapper = self.root / 'wrapped python'
        wrapper.write_text(
            '#!/bin/sh\n'
            f'export PYTHONPATH={shlex.quote(module_path)}\n'
            f'exec {shlex.quote(python[0])} -S "$@"\n',
            encoding='utf-8',
        )
        wrapper.chmod(0o700)
        desktop = self.root / 'probe.desktop'
        desktop.write_text(
            '[Desktop Entry]\nType=Application\nName=Ulanzi lifecycle probe\n'
            f'Exec="{self.probe}" %U\nTerminal=false\n',
            encoding='utf-8',
        )
        self._exercise(
            'AppAction', {'name': str(desktop)}, [],
            {'ULANZI_DESKTOP_PYTHON': str(wrapper)},
        )


if __name__ == '__main__':
    unittest.main()
