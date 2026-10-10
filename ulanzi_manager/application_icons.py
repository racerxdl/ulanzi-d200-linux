"""Import an authorized installed application's native icon into local storage.

Desktop-file authorization belongs to the caller (the visible application catalog),
not this module. No desktop command is executed. Native GTK/PyGObject dependencies
are loaded by the system Python helper, independently of the application's venv.
"""

import hashlib
import io
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

from ulanzi_manager.native import native_python

logger = logging.getLogger(__name__)

_MISSING_ICON = 3
_ICON_SIZE = (196, 196)


def import_application_icon(desktop_file: str, icons_dir: Path) -> Optional[str]:
    """Return a persistent PNG basename, or None if the application has no icon.

    The returned transparent 196×196 image contains the complete icon, centered
    without changing its aspect ratio. Identical PNG content shares one filename.
    Operational errors raise RuntimeError and are logged; callers should leave a
    manually configured icon unchanged for both missing icons and failed imports.
    """
    helper = Path(__file__).with_name("desktop_icon.py")
    try:
        python, environment = native_python()
        result = subprocess.run(
            [*python, str(helper), desktop_file],
            env=environment,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if result.returncode == _MISSING_ICON and not result.stdout:
            return None
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or f"Native icon helper exited with status {result.returncode}")

        # Only helper-produced PNG content enters the persistent icon directory.
        # Unexpected helper stdout must never become a broken device image.
        with Image.open(io.BytesIO(result.stdout)) as image:
            if image.format != "PNG" or image.size != _ICON_SIZE or image.mode != "RGBA":
                raise RuntimeError("Native icon helper returned an invalid 196×196 RGBA PNG")
            image.load()
        filename = f"application-{hashlib.sha256(result.stdout).hexdigest()}.png"
        icons_dir = Path(icons_dir)
        icons_dir.mkdir(parents=True, exist_ok=True)
        destination = icons_dir / filename
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb", dir=icons_dir, prefix=".application-", suffix=".png", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(result.stdout)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return filename
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, UnidentifiedImageError) as error:
        logger.error("Could not import application icon for %s: %s", desktop_file, error)
        raise RuntimeError(f"Could not import application icon: {error}") from error
