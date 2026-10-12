"""Application bootstrap for Git Manager."""

from __future__ import annotations

import tkinter as tk

from ui import scaling
from ui.main_window import GitManagerGUI
from utils.platform import enable_windows_dpi_awareness


def _maximize(root: tk.Tk) -> None:
    """Maximize the window with fallbacks for platforms without -zoomed."""
    try:
        root.attributes("-zoomed", True)
        return
    except tk.TclError:
        pass
    try:
        root.state("zoomed")
        return
    except tk.TclError:
        pass
    try:
        width, height = scaling.screen_size(root)
        root.geometry(f"{width}x{height}+0+0")
    except tk.TclError:
        pass


def main() -> None:
    enable_windows_dpi_awareness()
    root = tk.Tk()
    # Scale the whole interface once, before any widget is created, so the
    # same layout is legible on a 13" laptop and a 24" monitor.
    scaling.init(root)
    min_w, min_h = scaling.fit_size(root, 800, 540)
    root.minsize(min_w, min_h)

    # Restore saved geometry / maximized state if available; otherwise maximize.
    try:
        from core.settings_db import SettingsDB

        db = SettingsDB()
        geom = db.get_window_geometry()
        maximized = db.get_window_maximized()
        saved_scale = db.get_ui_scale()
        fitted = scaling.rescale_geometry(root, geom, saved_scale) if geom else None
        if maximized is True:
            # User last closed maximized -> restore maximized
            _maximize(root)
        elif maximized is False and fitted:
            try:
                root.geometry(fitted)
            except tk.TclError:
                _maximize(root)
        else:
            # No history -> default maximized (preserve original behavior)
            _maximize(root)
    except Exception:
        # On any error keep original maximizing behavior
        _maximize(root)

    def _toggle_fullscreen(event: tk.Event | None = None) -> None:
        is_fullscreen = bool(root.attributes('-fullscreen'))
        root.attributes('-fullscreen', not is_fullscreen)

    root.bind('<F11>', _toggle_fullscreen)
    root.bind('<Escape>', lambda e: root.attributes('-fullscreen', False))

    gui = GitManagerGUI(root)  # noqa: F841
    root.mainloop()


if __name__ == "__main__":
    main()
