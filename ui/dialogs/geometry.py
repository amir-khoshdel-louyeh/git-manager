"""Remember dialog sizes/positions across runs (stored in SettingsDB).

Saved pixel sizes are adapted to the current display with
:func:`ui.scaling.rescale_geometry`, so a dialog last used on a 24" monitor
opens fully visible on a 13" laptop (and vice versa).
"""

from __future__ import annotations

import tkinter as tk

from ui import scaling


def parse_geometry(geom: str) -> tuple[int, int, int, int] | None:
    """Parse 'WxH+X+Y' into (w, h, x, y), or None when malformed."""
    return scaling.parse_geometry(geom)


def fits_screen(window: tk.Misc, geom: str) -> str | None:
    """Return a clamped, scaled 'WxH+X+Y' for this display, or None."""
    return scaling.rescale_geometry(window, geom)


def enable_geometry_memory(window: tk.Toplevel, db, name: str, delay_ms: int = 600) -> None:
    """Restore a dialog's saved geometry and keep saving it on resize/move.

    Safe to call right after constructing the dialog (before wait_window):
    if nothing valid was saved, the dialog keeps whatever placement its own
    code chose. Saves are debounced; nothing is written after destroy.
    """
    if db is None:
        return
    try:
        saved = db.get_dialog_geometry(name)
        saved_scale = db.get_ui_scale()
    except Exception:
        saved = None
        saved_scale = None
    if saved:
        fitted = scaling.rescale_geometry(window, saved, saved_scale)
        if fitted:
            try:
                window.geometry(fitted)
            except tk.TclError:
                pass

    state: dict = {"after": None}

    def schedule(event: tk.Event | None = None) -> None:
        if event is not None and event.widget is not window:
            return  # ignore Configure events from child widgets
        try:
            if state["after"] is not None:
                window.after_cancel(state["after"])
        except (tk.TclError, ValueError):
            pass
        try:
            state["after"] = window.after(delay_ms, save)
        except tk.TclError:
            pass

    def save() -> None:
        state["after"] = None
        try:
            if not window.winfo_exists():
                return
            geom = window.geometry()
        except tk.TclError:
            return
        if scaling.parse_geometry(geom) is None:
            return
        try:
            db.set_dialog_geometry(name, geom)
        except Exception:
            pass

    try:
        window.bind("<Configure>", schedule, add="+")
    except tk.TclError:
        pass
