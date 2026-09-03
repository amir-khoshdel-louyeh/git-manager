"""Platform-specific helpers."""

from __future__ import annotations

import ctypes
import platform


def enable_windows_dpi_awareness() -> None:
    """Enable DPI awareness on Windows for crisp UI rendering."""
    if platform.system() != "Windows":
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except OSError:
            pass
