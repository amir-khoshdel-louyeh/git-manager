"""Central DPI / screen scaling for the whole GUI.

Every layout in this app is designed in *logical pixels at the baseline DPI*
(96 on Windows/Linux, 72 on macOS). :func:`init` reads the real DPI, derives a
single scale factor and applies it in two places so a 13" laptop and a 24"
monitor show the very same interface proportions:

* ``tk scaling`` — makes every point-sized font follow the factor, so text is
  the same physical size everywhere.
* :func:`px` — makes paddings, widths, row heights and window sizes follow the
  same factor.

The factor is additionally capped so the base layout always fits inside the
current screen: a small screen never gets a window bigger than itself.

All helpers are defensive; they never raise and fall back to sensible values.
"""

from __future__ import annotations

import platform
import re
import tkinter as tk

#: Baseline DPI the layouts were designed at.
BASE_DPI = 72.0 if platform.system() == "Darwin" else 96.0
MIN_SCALE = 0.8
MAX_SCALE = 2.0
#: Logical footprint the main window needs to stay usable (at BASE_DPI).
#: Kept close to the measured natural size of the redesigned workspace so a
#: 1024-wide screen does not shrink the interface unnecessarily.
BASE_FIT_W = 1000
BASE_FIT_H = 660
#: Screen margins used when clamping windows / dialogs.
SCREEN_W_MARGIN = 0.94
SCREEN_H_MARGIN = 0.92

_GEO_RE = re.compile(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$")

_scale: float = 1.0
_dpi: float = BASE_DPI


# --------------------------------------------------------------------- init
def _detect_dpi(root: tk.Misc) -> float:
    """Best-effort physical/effective DPI of the display Tk is using."""
    dpi: float | None = None
    try:
        dpi = float(root.winfo_fpixels("1i"))
    except Exception:
        dpi = None
    if platform.system() == "Windows":
        try:
            import ctypes

            try:
                dpi = max(dpi or 0.0, float(ctypes.windll.user32.GetDpiForSystem()))
            except Exception:
                hdc = ctypes.windll.user32.GetDC(0)
                try:
                    dpi = max(dpi or 0.0, float(ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)))
                finally:
                    ctypes.windll.user32.ReleaseDC(0, hdc)
        except Exception:
            pass
    if not dpi or not (48.0 <= dpi <= 480.0):
        return BASE_DPI
    return dpi


def init(root: tk.Misc) -> float:
    """Detect the display and arm the shared scale factor. Returns the factor."""
    global _scale, _dpi
    _dpi = _detect_dpi(root)
    factor = _dpi / BASE_DPI
    # Never scale the base layout past the current screen.
    try:
        sw = float(root.winfo_screenwidth())
        sh = float(root.winfo_screenheight())
        if sw > 0 and sh > 0:
            factor = min(factor, sw * SCREEN_W_MARGIN / BASE_FIT_W, sh * SCREEN_H_MARGIN / BASE_FIT_H)
    except tk.TclError:
        pass
    _scale = max(MIN_SCALE, min(MAX_SCALE, factor))
    # Fonts in points must follow the same factor (Tk maps points via scaling).
    try:
        root.tk.call("tk", "scaling", _scale * BASE_DPI / 72.0)
    except tk.TclError:
        pass
    return _scale


# ------------------------------------------------------------------ metrics
def scale() -> float:
    """Current UI scale factor (1.0 = baseline DPI at the designed size)."""
    return _scale


def px(value: float) -> int:
    """Scale a logical pixel value (padding, width, height, wraplength)."""
    return int(round(value * _scale))


def screen_size(root: tk.Misc) -> tuple[int, int]:
    """Return the usable screen size in pixels, with a safe fallback."""
    try:
        return int(root.winfo_screenwidth()), int(root.winfo_screenheight())
    except tk.TclError:
        return BASE_FIT_W, BASE_FIT_H


def _max_window_size(root: tk.Misc) -> tuple[int, int]:
    sw, sh = screen_size(root)
    return int(sw * SCREEN_W_MARGIN), int(sh * SCREEN_H_MARGIN)


def fit_size(root: tk.Misc, width: int, height: int) -> tuple[int, int]:
    """Scale a logical size and clamp it to the screen; never smaller than tiny."""
    max_w, max_h = _max_window_size(root)
    w = max(240, min(px(width), max_w))
    h = max(200, min(px(height), max_h))
    return w, h


def fit_window(window: tk.Misc, width: int, height: int, min_width: int = 0, min_height: int = 0) -> tuple[int, int]:
    """Resize a window to a scaled+clamped size and relax its minimum to match."""
    w, h = fit_size(window, width, height)
    if min_width or min_height:
        try:
            window.minsize(min(px(min_width), w), min(px(min_height), h))
        except tk.TclError:
            pass
    try:
        window.geometry(f"{w}x{h}")
    except tk.TclError:
        pass
    return w, h


def center_on_parent(window: tk.Misc, parent: tk.Misc | None = None) -> None:
    """Center a window on its parent (or the screen) without leaving the screen."""
    try:
        window.update_idletasks()
        w = window.winfo_width()
        h = window.winfo_height()
    except tk.TclError:
        return
    if w <= 1 or h <= 1:
        try:
            w, h = window.winfo_reqwidth(), window.winfo_reqheight()
        except tk.TclError:
            return
    sw, sh = screen_size(window)
    max_w, max_h = _max_window_size(window)
    w = max(200, min(w, max_w))
    h = max(150, min(h, max_h))
    x = y = 0
    if parent is not None:
        try:
            if parent.winfo_width() > 1 and parent.winfo_height() > 1:
                x = parent.winfo_x() + (parent.winfo_width() - w) // 2
                y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        except tk.TclError:
            x = y = 0
    if x <= 0 and y <= 0:
        x = (sw - w) // 2
        y = (sh - h) // 3
    x = max(0, min(x, max(0, sw - w)))
    y = max(0, min(y, max(0, sh - h)))
    try:
        window.geometry(f"{w}x{h}+{x}+{y}")
    except tk.TclError:
        pass


# ---------------------------------------------------------------- geometry IO
def parse_geometry(geom: str) -> tuple[int, int, int, int] | None:
    """Parse ``WxH+X+Y`` into (w, h, x, y), or None when malformed."""
    if not geom:
        return None
    match = _GEO_RE.match(geom.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))


def rescale_geometry(root: tk.Misc, geom: str, saved_scale: float | None = None) -> str | None:
    """Adapt a saved geometry string to this display.

    Sizes saved on another monitor/DPI are scaled by ``current / saved`` and
    everything is clamped so the window always lands fully on screen.
    """
    parsed = parse_geometry(geom)
    if parsed is None:
        return None
    w, h, x, y = parsed
    if saved_scale and saved_scale > 0:
        ratio = _scale / float(saved_scale)
        w, h = int(round(w * ratio)), int(round(h * ratio))
    max_w, max_h = _max_window_size(root)
    w = max(400, min(w, max_w))
    h = max(300, min(h, max_h))
    sw, sh = screen_size(root)
    x = max(0, min(x, max(0, sw - w)))
    y = max(0, min(y, max(0, sh - h)))
    return f"{w}x{h}+{x}+{y}"


def rescale_length(value: int, saved_scale: float | None = None) -> int:
    """Adapt a stored pixel length (tree column width) to this display."""
    if not saved_scale or saved_scale <= 0:
        return int(value)
    return int(round(int(value) * (_scale / float(saved_scale))))
