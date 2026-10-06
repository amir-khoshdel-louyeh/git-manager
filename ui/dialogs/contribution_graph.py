"""Embedded GitHub-style contribution graph (reusable canvas widget).

Same rendering as the Contributions dialog (uniform zoom, gold outline for
planned days, hover details), but packed as a plain frame so it can live
inside other dialogs — e.g. at the bottom of Move Commits. The big
Contributions dialog is intentionally left untouched.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date as _date
from pathlib import Path
from tkinter import ttk
from typing import Optional

from core.contributions import COLORS_DARK, COLORS_LIGHT, build_grid, collect_counts
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

# Viewport caps so big zooms stay usable; scrollbars take over past them.
# (Width stays below the move dialog's content width so it never stretches.)
_MAX_W = 1220
_MAX_H = 320


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

        canvas_frame = ttk.Frame(self, style="Dialog.TFrame")
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="#ffffff" if theme_mode == "light" else "#0d1117",
            highlightthickness=1,
            highlightbackground="#d0d7de" if theme_mode == "light" else "#30363d",
        )
        self.vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", lambda e: self._set_status_default())
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
        self._draw()
        self._set_status_default()
        return self.total

    # ------------------------------------------------------------------ zoom
    def _metrics(self) -> dict:
        """Scaled geometry for the current zoom (same formula as the dialog)."""
        z = self.zoom
        cell = max(2, round(_CELL * z))
        gap = max(1, round(_GAP * z))
        return {
            "cell": cell,
            "gap": gap,
            "step": cell + gap,
            "left": round(_LEFT_PAD * z) + _TABLE_PAD,
            "top": round(_TOP_PAD * z) + _TABLE_PAD,
            "pad": round(8 * z) + _TABLE_PAD,
            "font": max(8, round(9 * z)),
            "outline": max(2, round(z)),
        }

    def _zoom_by(self, factor: float) -> None:
        self.zoom = min(ZOOM_MAX, max(ZOOM_MIN, self.zoom * factor))
        self._m = self._metrics()
        self._draw()

    # ------------------------------------------------------------------ draw
    def _draw(self) -> None:
        columns = self._columns
        m = self._m
        cell, step, left, top = m["cell"], m["step"], m["left"], m["top"]
        self.canvas.delete("all")
        self._cells = []
        dark = self.theme_mode == "dark"
        colors = COLORS_DARK if dark else COLORS_LIGHT
        label_fg = "#8b949e" if dark else "#57606a"
        label_font = ("Helvetica", m["font"])
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        last_month_col = -10
        outline = "#e3b341" if dark else "#bf8700"
        pad = max(1, round(self.zoom / 2))
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
                        left - round(6 * self.zoom), y0 + cell / 2, text=names[row_idx],
                        anchor="e", font=label_font, fill=label_fg,
                    )
            first_day = column[0].day
            if first_day.day <= 7 and col_idx - last_month_col >= 3:
                self.canvas.create_text(
                    left + col_idx * step, top - round(6 * self.zoom),
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
        graph_w = left + 53 * step + m["pad"]
        graph_h = top + 7 * step + m["pad"]
        self.canvas.configure(scrollregion=(0, 0, graph_w, graph_h))
        self.canvas.configure(width=min(graph_w, _MAX_W), height=min(graph_h, _MAX_H))
        self.zoom_var.set(f"{int(round(self.zoom * 100))}%")

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

    def _set_status_default(self) -> None:
        base = f"{self.total} contributions in the last year. Hover a day for details."
        if self.cutoff is not None:
            base = f"{self.total} contributions in the last year. Shaded days are before the last commit."
        if self.highlight:
            base += " Gold outline = planned."
        try:
            self.status_var.set(base)
        except (tk.TclError, AttributeError):
            pass
