"""Resolve the interpreter that provides the system GTK stack."""

import os


DEFAULT_GI_PYTHON = "/usr/bin/python3"


def graphical_python() -> str:
    """Return the interpreter used by desktop activation and icon helpers."""
    return os.environ.get("ULANZI_GI_PYTHON", DEFAULT_GI_PYTHON)
