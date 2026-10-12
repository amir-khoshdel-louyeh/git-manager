"""Embedded GitHub-style contribution graph (reusable canvas widget).

Same rendering as the Contributions dialog (uniform zoom, gold outline for
planned days, hover details), but packed as a plain frame so it can live
inside other dialogs — e.g. at the bottom of Move Commits. The big
Contributions dialog is intentionally left untouched.

The table is drawn at its zoomed size, while the viewport is capped to the
dialog/screen and gets scrollbars, so the same widget stays usable on a 13"
laptop and a 24" monitor. Zooming redraws the table at the new size.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date as _date
from pathlib import Path
from tkinter import ttk
from typing import Optional

from core.contributions import COLORS_DARK, COLORS_LIGHT, build_grid, collect_counts
from ui import scaling
# Table geometry is shared with the Contributions dialog itself, so the
# embedded table is pixel-identical at the same zoom (single source).
from ui.dialogs.contributions_dialog import (
    _CELL,
    _GAP,
    _LEFT_PAD,
    _TABLE_PAD,
    _TOP_PAD,
    ZOOM_MAX,
    ZOOM_MIN,
)

#: Shade drawn OVER unavailable days (the table underneath stays intact).
#: Stipple dithers the shade so the contribution colors show through.
_SHADE_FILL = "#808080"
_SHADE_STIPPLE = "gray50"


def _parse_day(value: object) -> _date | None:
    """Return the calendar day of an ISO timestamp, or None when unreadable."""
    if not value:
        return None
    try:
        return _date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class ContributionGraph(ttk.Frame):
    """A compact contribution graph with its own zoom and hover status."""

    def __init__(self, parent: tk.Misc, theme_mode: str = "light", initial_zoom: float = 2.0) -> None:
        super().__init__(parent, style="Dialog.TFrame")
        self.theme_mode = theme_mode
        try:
            self.zoom: float = min(ZOOM_MAX, max(ZOOM_MIN, float(initial_zoom)))
        except (ValueError, TypeError):
            self.zoom = 2.0
        self.highlight: dict[str, str] = {}
        self.cutoff: _date | None = None
        self.total: int = 0
        self._columns: list = []
        self._cells: list[list[dict]] = []
        self._m = self._metrics()

        header = ttk.Frame(self, style="Dialog.TFrame")
        header.pack(fill=tk.X, pady=(0, 2))
        self.status_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.status_var, font=("Helvetica", 9, "italic"), style="Dialog.TLabel").pack(
            side=tk.LEFT
        )
        zoom_box = ttk.Frame(header, style="Dialog.TFrame")
        zoom_box.pack(side=tk.RIGHT)
        ttk.Button(zoom_box, text="−", width=3, command=lambda: self._zoom_by(1 / 1.25), style="Dialog.TButton").pack(
            side=tk.LEFT
        )
        self.zoom_var = tk.StringVar(value="")
        ttk.Label(zoom_box, textvariable=self.zoom_var, font=("Helvetica", 9), width=6, anchor=tk.CENTER,
                  style="Dialog.TLabel").pack(side=tk.LEFT, padx=2)
        ttk.Button(zoom_box, text="+", width=3, command=lambda: self._zoom_by(1.25), style="Dialog.TButton").pack(
            side=tk.LEFT
        )

        # The table keeps its native zoomed size but the viewport is capped to
        # the dialog/screen; scrollbars keep every week reachable on laptops.
        canvas_frame = ttk.Frame(self, style="Dialog.TFrame")
        canvas_frame.pack(fill=tk.X)
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#ffffff" if theme_mode == "light" else "#0d1117",
            highlightthickness=1,
            highlightbackground="#d0d7de" if theme_mode == "light" else "#30363d",
        )
        self.vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", lambda e: self._set_status_default())
        self.canvas.bind("<MouseWheel>", self._on_scroll_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._scroll_v(-1))
        self.canvas.bind("<Button-5>", lambda e: self._scroll_v(1))
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom_wheel)
        self._set_status_default()

    # ------------------------------------------------------------------ data
    def set_data(
        self,
        repo_paths: str | Path | list[str | Path] | None,
        author_email: Optional[str] = None,
        highlight: Optional[dict[str, str]] = None,
        cutoff_iso: Optional[str] = None,
    ) -> int:
        """Reload counts for one repo (or several) and redraw.

        Days strictly before ``cutoff_iso``'s day render gray (unavailable —
        e.g. before the picked repo's last commit). Returns the total count.
        """
        self.highlight = dict(highlight or {})
        self.cutoff = _parse_day(cutoff_iso)
        try:
            if not repo_paths:
                paths: list[Path] = []
            elif isinstance(repo_paths, (str, Path)):
                paths = [Path(repo_paths)]
            else:
                paths = [Path(p) for p in repo_paths]
            counts = collect_counts(paths, author_email=author_email)
        except Exception:
            counts = {}
        self._columns = build_grid(counts)
        self.total = sum(counts.values())
        self._draw(scroll_to_end=True)
        self._set_status_default()
        return self.total

    # ------------------------------------------------------------------ zoom
    def _metrics(self) -> dict:
        """Scaled geometry for the current zoom (same formula as the dialog)."""
        z = self.zoom * scaling.scale()
        table_pad = scaling.px(_TABLE_PAD)
        cell = max(2, round(_CELL * z))
        gap = max(1, round(_GAP * z))
        return {
            "cell": cell,
            "gap": gap,
            "step": cell + gap,
            "left": round(_LEFT_PAD * z) + table_pad,
            "top": round(_TOP_PAD * z) + table_pad,
            "pad": round(8 * z) + table_pad,
            "font": max(8, round(9 * self.zoom)),
            "outline": max(2, round(z)),
            "label_offset": round(6 * z),
            "year_offset": round(14 * z),
            "highlight_pad": max(1, round(z / 2)),
        }

    def _zoom_by(self, factor: float) -> None:
        self.zoom = min(ZOOM_MAX, max(ZOOM_MIN, self.zoom * factor))
        self._m = self._metrics()
        self._draw()

    # ------------------------------------------------------------------ draw
    def _draw(self, scroll_to_end: bool = False) -> None:
        columns = self._columns
        m = self._m
        cell, step, left, top = m["cell"], m["step"], m["left"], m["top"]
        self.canvas.delete("all")
        self._cells = []
        dark = self.theme_mode == "dark"
        colors = COLORS_DARK if dark else COLORS_LIGHT
        label_fg = "#8b949e" if dark else "#57606a"
        label_font = ("Helvetica", m["font"])
        year_font = ("Helvetica", m["font"], "bold")
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        last_month_col = -10
        last_year: Optional[int] = None
        outline = "#e3b341" if dark else "#bf8700"
        pad = m["highlight_pad"]
        shaded: list[tuple[int, int]] = []
        for col_idx, column in enumerate(columns):
            col_meta: list[dict] = []
            for row_idx, cell_obj in enumerate(column):
                x0 = left + col_idx * step
                y0 = top + row_idx * step
                unavailable = bool(
                    cell_obj.in_range and self.cutoff is not None and cell_obj.day < self.cutoff
                )
                if cell_obj.in_range:
                    # The main table is always drawn whole; unavailable days
                    # only get a shade overlaid afterwards.
                    fill = colors[cell_obj.level]
                    self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=fill, outline=fill)
                    note = self.highlight.get(cell_obj.day.isoformat())
                    if note is not None:
                        self.canvas.create_rectangle(
                            x0 - pad, y0 - pad, x0 + cell + pad, y0 + cell + pad,
                            fill="", outline=outline, width=m["outline"],
                        )
                    if unavailable:
                        shaded.append((x0, y0))
                col_meta.append({"day": cell_obj.day, "count": cell_obj.count, "in_range": cell_obj.in_range,
                                 "note": self.highlight.get(cell_obj.day.isoformat()),
                                 "unavailable": unavailable})
                if col_idx == 0 and row_idx in (1, 3, 5):
                    names = {1: "Mon", 3: "Wed", 5: "Fri"}
                    self.canvas.create_text(
                        left - m["label_offset"], y0 + cell / 2, text=names[row_idx],
                        anchor="e", font=label_font, fill=label_fg,
                    )
            first_day = column[0].day
            drew_year = False
            if first_day.year != last_year:
                self.canvas.create_text(
                    left + col_idx * step,
                    top - m["label_offset"] - m["year_offset"],
                    text=str(first_day.year),
                    anchor="sw", font=year_font, fill=label_fg,
                )
                last_year = first_day.year
                last_month_col = -10
                drew_year = True
            if not drew_year and first_day.day <= 7 and col_idx - last_month_col >= 3:
                self.canvas.create_text(
                    left + col_idx * step, top - m["label_offset"],
                    text=month_names[first_day.month - 1],
                    anchor="sw", font=label_font, fill=label_fg,
                )
                last_month_col = col_idx
            self._cells.append(col_meta)
        # Shade over unavailable days (dithered: the table shows through).
        for x0, y0 in shaded:
            self.canvas.create_rectangle(
                x0, y0, x0 + cell, y0 + cell,
                fill=_SHADE_FILL, outline="", stipple=_SHADE_STIPPLE,
            )
        graph_w = left + max(1, len(columns)) * step + m["pad"]
        graph_h = top + 7 * step + m["pad"]
        self.canvas.configure(scrollregion=(0, 0, graph_w, graph_h))
        # Cap the visible viewport so the table never forces the dialog wider
        # than the screen; the scrollbars expose the rest at any zoom.
        try:
            screen_w = int(self.winfo_screenwidth())
            screen_h = int(self.winfo_screenheight())
        except tk.TclError:
            screen_w, screen_h = graph_w, graph_h
        logical_w = screen_w / scaling.scale()
        logical_h = screen_h / scaling.scale()
        view_w = min(graph_w, scaling.px(min(860, max(420, int(logical_w * 0.55)))))
        view_h = min(graph_h, scaling.px(min(260, max(110, int(logical_h * 0.13)))))
        self.canvas.configure(width=view_w, height=view_h)
        self.zoom_var.set(f"{int(round(self.zoom * 100))}%")
        # A long history opens on the newest weeks; scrollbars reach the rest.
        if scroll_to_end:
            try:
                self.canvas.update_idletasks()
                self.canvas.xview_moveto(1.0)
            except tk.TclError:
                pass

    # ---------------------------------------------------------------- scroll
    def _scroll_v(self, direction: int) -> str:
        self.canvas.yview_scroll(direction, "units")
        return "break"

    def _on_scroll_wheel(self, event: tk.Event) -> str:
        delta = getattr(event, "delta", 0)
        self.canvas.yview_scroll(-1 if delta and delta > 0 else 1, "units")
        return "break"

    def _on_shift_wheel(self, event: tk.Event) -> str:
        delta = getattr(event, "delta", 0)
        self.canvas.xview_scroll(-1 if delta and delta > 0 else 1, "units")
        return "break"

    def _on_zoom_wheel(self, event: tk.Event) -> str:
        delta = getattr(event, "delta", 0)
        self._zoom_by(1.25 if delta and delta > 0 else 1 / 1.25)
        return "break"

    # ------------------------------------------------------------------ hover
    def _on_hover(self, event: tk.Event) -> None:
        m = self._m
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        col = int((x - m["left"]) // m["step"])
        row = int((y - m["top"]) // m["step"])
        if 0 <= col < len(self._cells) and 0 <= row < 7:
            meta = self._cells[col][row]
            if meta["in_range"]:
                day = meta["day"]
                label = f"{day.strftime('%b')} {day.day}, {day.year}"
                if meta["count"] == 0:
                    text = f"No contributions on {label}"
                elif meta["count"] == 1:
                    text = f"1 contribution on {label}"
                else:
                    text = f"{meta['count']} contributions on {label}"
                if meta["unavailable"]:
                    text += " — unavailable (before last commit)"
                elif meta["note"]:
                    text += f" — {meta['note']}"
                self.status_var.set(text)
                return
        self._set_status_default()

    def _range_text(self) -> str:
        """Describe the years the table covers (full history)."""
        if not self._columns:
            return ""
        first = next((c.day for c in self._columns[0] if c.in_range), None)
        last = None
        for column in reversed(self._columns):
            last = next((c.day for c in reversed(column) if c.in_range), None)
            if last is not None:
                break
        if first is None or last is None:
            return ""
        if first.year == last.year:
            return f" in {first.year}"
        if last.year - first.year == 1:
            return f" in {first.year}–{last.year}"
        return f" from {first.year} to {last.year}"

    def _set_status_default(self) -> None:
        span = self._range_text()
        base = f"{self.total} contributions{span}. Hover a day for details."
        if self.cutoff is not None:
            base = f"{self.total} contributions{span}. Shaded days are before the last commit."
        if self.highlight:
            base += " Gold outline = planned."
        try:
            self.status_var.set(base)
        except (tk.TclError, AttributeError):
            pass
