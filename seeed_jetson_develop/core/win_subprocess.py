"""Windows-only subprocess patch to suppress console popups in GUI mode."""
from __future__ import annotations

import os
import subprocess
import sys


_DISABLE_ENV_VAR = "SEEED_DISABLE_NO_CONSOLE_PATCH"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def install_no_console_patch() -> None:
    """Make ``subprocess.Popen`` default to ``CREATE_NO_WINDOW`` on Windows.

    When a Python GUI app runs without a console (``pythonw.exe`` or a
    PyInstaller ``--windowed`` executable), every child process that does not
    specify ``creationflags`` forces Windows to create a new console window.
    Applications that poll via subprocess (device scans, SSH checks, command
    runners, etc.) therefore produce repeated black cmd windows and visible UI
    flicker.

    This patch injects ``subprocess.CREATE_NO_WINDOW`` by default on Windows.
    It is installed once at application startup before any other imports that
    may spawn subprocesses.

    Set ``SEEED_DISABLE_NO_CONSOLE_PATCH=1`` to skip patching for debugging.
    """
    if sys.platform != "win32":
        return

    if os.environ.get(_DISABLE_ENV_VAR, "").lower() in {"1", "true", "yes", "on"}:
        return

    # Avoid double-patching if the module is imported more than once.
    if getattr(subprocess.Popen, "_seeed_no_console_patched", False):
        return

    _orig_popen_init = subprocess.Popen.__init__

    def _popen_init(self, *args, **kwargs):
        creationflags = kwargs.get("creationflags", 0)
        kwargs["creationflags"] = creationflags | _CREATE_NO_WINDOW
        return _orig_popen_init(self, *args, **kwargs)

    _popen_init._seeed_no_console_patched = True  # type: ignore[attr-defined]
    subprocess.Popen.__init__ = _popen_init
