"""Find a desktop-capable Python without assuming a distribution's filesystem."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

_PROBE = (
    "import gi; "
    "gi.require_version('GioUnix', '2.0'); "
    "gi.require_version('Gtk', '3.0'); "
    "gi.require_version('Gdk', '3.0'); "
    "gi.require_version('GdkPixbuf', '2.0'); "
    "from gi.repository import Gio, GioUnix, Gtk, Gdk, GdkPixbuf"
)


def native_python():
    """Return (command prefix, environment) for both desktop helpers.

    Ignore the application's Python overrides, but let a selected Nix Python
    wrapper establish its own module paths. -I/-E would discard those paths.
    XDG, display, D-Bus and GI library settings remain inherited.
    ULANZI_GI_PYTHON explicitly selects an executable, not a shell command.
    """
    environment = os.environ.copy()
    for key in ('PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'PYTHONSTARTUP'):
        environment.pop(key, None)
    configured = environment.get('ULANZI_GI_PYTHON')
    if configured:
        candidates = [configured]
    else:
        candidates = ['/run/current-system/sw/bin/python3', '/usr/bin/python3']
        candidates.extend(
            str(Path(directory or os.curdir).absolute() / 'python3')
            for directory in os.get_exec_path(environment)
        )
        candidates.append(sys.executable)
    failures = []
    for candidate in dict.fromkeys(candidates):
        executable = shutil.which(candidate, path=environment.get('PATH'))
        if executable is None:
            if configured:
                failures.append(f'{candidate}: executable not found')
            continue
        try:
            result = subprocess.run(
                [executable, '-s', '-c', _PROBE], env=environment,
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            failures.append(f'{executable}: {error}')
            continue
        if result.returncode == 0:
            return [executable, '-s'], environment
        failures.append(f'{executable}: {result.stderr.strip()}')
    detail = '; '.join(failures) or 'no Python executable found'
    raise RuntimeError(
        'No desktop-capable Python found. Set ULANZI_GI_PYTHON to a Python '
        'executable with PyGObject and GioUnix/GTK 3/GdkPixbuf; on NixOS use '
        'python3.withPackages (ps: [ ps.pygobject3 ]) and provide GI_TYPELIB_PATH. '
        + detail
    )
