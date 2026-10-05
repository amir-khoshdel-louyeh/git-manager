"""Proportional dialog scaling: text (and spacing) follows window resizes.

When enabled on a dialog, every later resize recomputes a single factor
(``min(width/base_w, height/base_h)``) and applies it uniformly to:

- all widget fonts (explicit ones, plus style-driven ttk text which gets a
  private font copy resolved from its style — the global theme is never
  touched),
- wraplengths,
- grid/pack paddings (padx/pady/ipadx/ipady),
- tk.Scale pixel options (length/width/sliderlength).

Everything is defensive: any widget that cannot be read or written is
skipped, so scaling can never break a dialog. Canvas widgets are skipped
on purpose (the contributions graph has its own zoom system).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

_MIN_FACTOR = 0.5
_MAX_FACTOR = 3.0
_MIN_FONT_SIZE = 6
_EPSILON = 0.015


def _iter_widgets(window: tk.Misc):
    """Yield window and all descendants (excluding canvases)."""
    stack = [window]
    while stack:
        widget = stack.pop()
        if isinstance(widget, tk.Canvas):
            continue
        yield widget
        try:
            stack.extend(widget.winfo_children())
        except tk.TclError:
            pass


def _resolve_base_font(widget: tk.Widget) -> dict | None:
    """Return the widget's effective font as an actual() dict, or None."""
    try:
        spec = widget.cget("font")
    except tk.TclError:
        return None
    try:
        if spec:
            return tkfont.Font(font=spec).actual()
        if isinstance(widget, ttk.Widget):
            try:
                style_name = widget.cget("style") or widget.winfo_class()
            except tk.TclError:
                return None
            try:
                sfont = ttk.Style(widget).lookup(style_name, "font")
            except tk.TclError:
                sfont = ""
            if not sfont:
                sfont = "TkDefaultFont"
            return tkfont.Font(font=sfont).actual()
    except (tk.TclError, ValueError):
        return None
    return None


def _norm_pad(value) -> tuple[int, int] | None:
    """Normalize a grid/pack pad value to (a, b), or None if not numeric."""
    if value is None or value == "":
        return None
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            return None
        try:
            return int(value[0]), int(value[1])
        except (ValueError, TypeError):
            return None
    try:
        return int(value), int(value)
    except (ValueError, TypeError):
        return None


# ttk classes whose text can only come from their style (no -font option,
# e.g. ttk.Button). These get a per-dialog style clone (see below).
_STYLE_TEXT_CLASSES = frozenset({
    "TButton", "TCheckbutton", "TRadiobutton", "TMenubutton",
    "TEntry", "TCombobox", "TSpinbox",
})


def _font_size_of(spec) -> int | None:
    """Return the point size of a font spec, or None when unreadable."""
    if not spec:
        return None
    try:
        return int(tkfont.Font(font=spec).actual()["size"])
    except (tk.TclError, ValueError, TypeError):
        return None


class _AutoScale:
    def __init__(self, window: tk.Toplevel) -> None:
        self.window = window
        self.style = ttk.Style(window)
        self.tag = str(id(window))
        self.fonts: list[tuple[tkfont.Font, int]] = []
        self.style_clones: dict[str, tuple[str, tkfont.Font, int]] = {}
        self.pads: list[tuple[tk.Widget, str, str, tuple[int, int]]] = []
        self.wraps: list[tuple[tk.Widget, int]] = []
        self.scales: list[tuple[tk.Widget, dict[str, int]]] = []
        self.base_w = 0
        self.base_h = 0
        self.last_factor = 1.0
        self._after: str | None = None

    # ------------------------------------------------------------ record
    def record(self) -> bool:
        try:
            self.window.update_idletasks()
            self.base_w = self.window.winfo_width()
            self.base_h = self.window.winfo_height()
        except tk.TclError:
            return False
        if self.base_w < 50 or self.base_h < 50:
            return False
        for widget in _iter_widgets(self.window):
            self._record_widget(widget)
        return True

    def _record_explicit_font(self, widget: tk.Widget) -> None:
        try:
            actual = _resolve_base_font(widget)
        except Exception:
            actual = None
        if actual and isinstance(actual.get("size"), int) and actual["size"] > 0:
            try:
                private = tkfont.Font(
                    root=self.window,
                    family=actual["family"],
                    size=actual["size"],
                    weight=actual["weight"],
                    slant=actual["slant"],
                    underline=actual["underline"],
                    overstrike=actual["overstrike"],
                )
                widget.configure(font=private)
                self.fonts.append((private, actual["size"]))
            except (tk.TclError, ValueError):
                pass

    def _record_style_clone(self, widget: tk.Widget) -> None:
        """Give a style-driven text widget a per-dialog style copy."""
        try:
            orig = widget.cget("style") or widget.winfo_class()
        except tk.TclError:
            return
        if orig in self.style_clones:
            clone = self.style_clones[orig][0]
            try:
                widget.configure(style=clone)
            except tk.TclError:
                pass
            return
        try:
            base_size = _font_size_of(self.style.lookup(orig, "font")) or _font_size_of("TkDefaultFont")
        except tk.TclError:
            base_size = None
        if not base_size or base_size <= 0:
            return
        clone = f"{orig}__auto{self.tag}"
        try:
            try:
                self.style.layout(clone, self.style.layout(orig))
            except tk.TclError:
                pass
            try:
                cfg = dict(self.style.configure(orig) or {})
            except tk.TclError:
                cfg = {}
            cfg.pop("font", None)
            if cfg:
                try:
                    self.style.configure(clone, **cfg)
                except tk.TclError:
                    pass
            try:
                mapping = self.style.map(orig) or {}
                if mapping:
                    self.style.map(clone, **mapping)
            except tk.TclError:
                pass
            private = tkfont.Font(root=self.window, family="Helvetica", size=base_size)
            try:
                # Keep the original family when resolvable.
                spec = self.style.lookup(orig, "font") or "TkDefaultFont"
                fam = tkfont.Font(font=spec).actual().get("family") or "Helvetica"
                private.configure(family=fam)
            except (tk.TclError, ValueError):
                pass
            self.style.configure(clone, font=private)
            widget.configure(style=clone)
            self.style_clones[orig] = (clone, private, base_size)
        except tk.TclError:
            pass

    def _record_widget(self, widget: tk.Widget) -> None:
        try:
            has_font = "font" in widget.keys()
        except tk.TclError:
            return
        if has_font:
            self._record_explicit_font(widget)
        elif isinstance(widget, ttk.Widget):
            # Style-driven text (ttk.Button etc. have no -font option):
            # clone the style per dialog so only this dialog scales.
            try:
                cls = widget.winfo_class()
            except tk.TclError:
                return
            if cls in _STYLE_TEXT_CLASSES:
                self._record_style_clone(widget)
        # Wraplength.
        try:
            if "wraplength" in widget.keys():
                wrap = int(widget.cget("wraplength"))
                if wrap > 0:
                    self.wraps.append((widget, wrap))
        except (tk.TclError, ValueError):
            pass
        # Grid / pack padding.
        try:
            manager = widget.winfo_manager()
        except tk.TclError:
            return
        if manager == "grid":
            try:
                info = widget.grid_info()
            except tk.TclError:
                return
            for key in ("padx", "pady", "ipadx", "ipady"):
                norm = _norm_pad(info.get(key))
                if norm is not None:
                    self.pads.append((widget, "grid", key, norm))
        elif manager == "pack":
            try:
                info = widget.pack_info()
            except tk.TclError:
                return
            for key in ("padx", "pady", "ipadx", "ipady"):
                norm = _norm_pad(info.get(key))
                if norm is not None:
                    self.pads.append((widget, "pack", key, norm))
        # tk.Scale pixel geometry.
        if isinstance(widget, tk.Scale):
            opts: dict[str, int] = {}
            for key in ("length", "width", "sliderlength"):
                try:
                    opts[key] = int(widget.cget(key))
                except (tk.TclError, ValueError):
                    pass
            if opts:
                self.scales.append((widget, opts))

    # ------------------------------------------------------------ apply
    def apply(self, factor: float) -> None:
        for private, base in self.fonts:
            try:
                private.configure(size=max(_MIN_FONT_SIZE, int(round(base * factor))))
            except tk.TclError:
                pass
        for _clone, private, base in self.style_clones.values():
            try:
                private.configure(size=max(_MIN_FONT_SIZE, int(round(base * factor))))
            except tk.TclError:
                pass
        for widget, manager, key, (a, b) in self.pads:
            try:
                if manager == "grid":
                    widget.grid_configure(**{key: (int(round(a * factor)), int(round(b * factor)))})
                else:
                    widget.pack_configure(**{key: (int(round(a * factor)), int(round(b * factor)))})
            except tk.TclError:
                pass
        for widget, base in self.wraps:
            try:
                widget.configure(wraplength=max(50, int(round(base * factor))))
            except tk.TclError:
                pass
        for widget, opts in self.scales:
            try:
                widget.configure(
                    length=max(20, int(round(opts.get("length", 200) * factor))),
                    width=max(6, int(round(opts.get("width", 18) * factor))),
                    sliderlength=max(8, int(round(opts.get("sliderlength", 30) * factor))),
                )
            except tk.TclError:
                pass

    # ------------------------------------------------------------ trigger
    def on_configure(self, event: tk.Event) -> None:
        if event.widget is not self.window:
            return
        if self._after is not None:
            try:
                self.window.after_cancel(self._after)
            except (tk.TclError, ValueError):
                pass
            self._after = None
        try:
            self._after = self.window.after(120, self._rescale_from_window)
        except tk.TclError:
            pass

    def _rescale_from_window(self) -> None:
        self._after = None
        try:
            if not self.window.winfo_exists():
                return
            w = self.window.winfo_width()
            h = self.window.winfo_height()
        except tk.TclError:
            return
        if w < 50 or h < 50:
            return
        factor = min(w / self.base_w, h / self.base_h)
        factor = min(_MAX_FACTOR, max(_MIN_FACTOR, factor))
        if abs(factor - self.last_factor) < _EPSILON:
            return
        self.last_factor = factor
        self.apply(factor)


def enable_autoscale(window: tk.Toplevel) -> bool:
    """Make all text/spacing in a dialog follow window resizes proportionally.

    Returns True when armed. Never raises and never alters appearance until
    the user actually resizes (factor starts at 1.0).
    """
    try:
        scaler = _AutoScale(window)
        if not scaler.record():
            return False
        window.bind("<Configure>", scaler.on_configure, add="+")
        window._autoscale = scaler  # keep alive via the widget
        return True
    except Exception:
        return False
