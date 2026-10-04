"""Remember dialog sizes/positions across runs (stored in SettingsDB)."""

from __future__ import annotations

import re
import tkinter as tk

_GEO_RE = re.compile(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$")


def parse_geometry(geom: str) -> tuple[int, int, int, int] | None:
    """Parse 'WxH+X+Y' into (w, h, x, y), or None when malformed."""
    if not geom:
        return None
    match = _GEO_RE.match(geom.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))


def fits_screen(window: tk.Misc, geom: str) -> str | None:
    """Return a clamped 'WxH+X+Y' if the size fits the screen, else None."""
    parsed = parse_geometry(geom)
    if parsed is None:
        return None
    w, h, x, y = parsed
    try:
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
    except tk.TclError:
        return None
    if w <= 0 or h <= 0 or w > screen_w or h > screen_h:
        return None
    # Clamp position so the window stays reachable.
    x = max(0, min(x, screen_w - min(w, 100)))
    y = max(0, min(y, screen_h - min(h, 100)))
    sign_x = "+" if x >= 0 else ""
    sign_y = "+" if y >= 0 else ""
    return f"{w}x{h}{sign_x}{x}{sign_y}{y}"


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
    except Exception:
        saved = None
    if saved:
        try:
            window.update_idletasks()
            clamped = fits_screen(window, saved)
        except tk.TclError:
            clamped = None
        if clamped:
            try:
                window.geometry(clamped)
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
        if parse_geometry(geom) is None:
            return
        try:
            db.set_dialog_geometry(name, geom)
        except Exception:
            pass

    try:
        window.bind("<Configure>", schedule, add="+")
    except tk.TclError:
        pass
