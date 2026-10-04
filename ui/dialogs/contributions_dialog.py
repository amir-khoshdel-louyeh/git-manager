"""GitHub-style contribution graph dialog rendered from local git history."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk
from pathlib import Path
from typing import Optional

from core.contributions import (
    COLORS_DARK,
    COLORS_LIGHT,
    build_grid,
    collect_counts,
)

_CELL = 14
_GAP = 4
_LEFT_PAD = 36
_TOP_PAD = 26

#: Zoom defaults/limits. Aspect ratio is always preserved: zoom scales the
#: cell size and every dependent metric uniformly, then redraws the canvas.
ZOOM_DEFAULT = 2.0
ZOOM_MIN = 0.5
ZOOM_MAX = 6.0


class ContributionsDialog(tk.Toplevel):
    """Show a GitHub-style contribution graph for managed repositories.

    Args:
        repo_items: [(name, path)] of repositories to include.
        default_author: author email prefilled in the filter ("" = all).
        highlight: optional {YYYY-MM-DD: note} days outlined as planned
            (used by the Move Commits preview).
    """

    def __init__(
        self,
        parent: tk.Misc,
        repo_items: list[tuple[str, str]],
        default_author: str = "",
        theme_mode: str = "light",
        highlight: Optional[dict[str, str]] = None,
        initial_zoom: float = 2.0,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self.title("Contributions")
        # Locked together: the window always shrink-wraps the table, so the
        # frame and the graph can never drift apart. Sizing is done via zoom.
        self.resizable(False, False)
        self.theme_mode = theme_mode
        self.repo_map: dict[str, str] = {name: path for name, path in repo_items}
        self.highlight: dict[str, str] = dict(highlight or {})
        try:
            self.zoom: float = min(6.0, max(0.5, float(initial_zoom)))
        except (ValueError, TypeError):
            self.zoom = 2.0
        self._columns: list = []

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ---------- filters ----------
        filters = ttk.Frame(self, style="Dialog.TFrame")
        filters.pack(fill=tk.X, padx=16, pady=(14, 4))
        ttk.Label(filters, text="Repo:", style="Dialog.TLabel").pack(side=tk.LEFT)
        names = ["All repositories"] + sorted(self.repo_map)
        self.repo_var = tk.StringVar(value=names[0])
        repo_menu = ttk.OptionMenu(filters, self.repo_var, names[0], *names)
        repo_menu.pack(side=tk.LEFT, padx=(6, 12))
        ttk.Label(filters, text="Author:", style="Dialog.TLabel").pack(side=tk.LEFT)
        self.author_var = tk.StringVar(value=default_author)
        ttk.Entry(filters, textvariable=self.author_var, width=28, style="Dialog.TEntry").pack(side=tk.LEFT, padx=(6, 0))
        self.all_authors_var = tk.BooleanVar(value=not bool(default_author))
        ttk.Checkbutton(
            filters,
            text="All authors",
            variable=self.all_authors_var,
            style="Dialog.TCheckbutton",
        ).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(filters, text="Refresh", command=self._reload, style="Dialog.TButton").pack(side=tk.LEFT, padx=(12, 0))

        # ---------- total ----------
        self.total_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.total_var, font=("Helvetica", 11, "bold"), style="Dialog.TLabel").pack(
            anchor=tk.W, padx=16, pady=(6, 2)
        )

        # ---------- graph canvas ----------
        canvas_frame = ttk.Frame(self, style="Dialog.TFrame")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=16)
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
        # Zoom with mouse: Ctrl+wheel (aspect ratio always preserved).
        self.canvas.bind("<Control-MouseWheel>", self._on_zoom_wheel)
        self.canvas.bind("<Control-Button-4>", lambda e: self._zoom_by(1.25))
        self.canvas.bind("<Control-Button-5>", lambda e: self._zoom_by(1 / 1.25))
        # Plain wheel scrolls (Linux buttons / Windows delta).
        self.canvas.bind("<MouseWheel>", self._on_scroll_wheel)
        self.canvas.bind("<Button-4>", lambda e: self._scroll_v(-1))
        self.canvas.bind("<Button-5>", lambda e: self._scroll_v(1))
        self._cells: list[list[dict]] = []  # per-column day meta for hover
        self._m = self._metrics()  # current scaled metrics

        # ---------- legend + status ----------
        bottom = ttk.Frame(self, style="Dialog.TFrame")
        bottom.pack(fill=tk.X, padx=16, pady=(4, 6))
        self.status_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.status_var, font=("Helvetica", 9, "italic"), style="Dialog.TLabel").pack(
            side=tk.LEFT
        )
        legend = ttk.Frame(bottom, style="Dialog.TFrame")
        legend.pack(side=tk.RIGHT)
        ttk.Label(legend, text="Less", font=("Helvetica", 9), style="Dialog.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        colors = COLORS_DARK if theme_mode == "dark" else COLORS_LIGHT
        for color in colors:
            swatch = tk.Label(legend, bg=color, width=2, relief=tk.SOLID, bd=1)
            swatch.pack(side=tk.LEFT, padx=1)
        ttk.Label(legend, text="More", font=("Helvetica", 9), style="Dialog.TLabel").pack(side=tk.LEFT, padx=(4, 12))
        # Zoom controls (mouse: Ctrl+wheel).
        ttk.Button(legend, text="−", width=3, command=lambda: self._zoom_by(1 / 1.25), style="Dialog.TButton").pack(side=tk.LEFT)
        self.zoom_var = tk.StringVar(value="")
        ttk.Label(legend, textvariable=self.zoom_var, font=("Helvetica", 9), width=6, anchor=tk.CENTER, style="Dialog.TLabel").pack(side=tk.LEFT, padx=2)
        ttk.Button(legend, text="+", width=3, command=lambda: self._zoom_by(1.25), style="Dialog.TButton").pack(side=tk.LEFT)

        buttons = ttk.Frame(self, style="Dialog.TFrame")
        buttons.pack(pady=(4, 14))
        ttk.Button(buttons, text="Close", command=self._on_close, style="Dialog.TButton", width=12).pack()
        self.bind("<Escape>", lambda e: self._on_close())

        self._reload()
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------ data
    def _selected_paths(self) -> list[Path]:
        choice = self.repo_var.get()
        if choice == "All repositories":
            return [Path(p) for p in self.repo_map.values()]
        path = self.repo_map.get(choice)
        return [Path(path)] if path else []

    def _reload(self) -> None:
        self.total_var.set("Loading…")
        self.update_idletasks()
        author = None if self.all_authors_var.get() else self.author_var.get().strip() or None
        paths = self._selected_paths()
        counts = collect_counts(paths, author_email=author)
        self._columns = build_grid(counts)
        total = sum(counts.values())
        self.total_var.set(f"{total} contributions in the last year ({len(paths)} repo(s))")
        self._draw()
        self._set_status_default()

    # ------------------------------------------------------------------ zoom
    def _metrics(self) -> dict:
        """Scaled geometry for the current zoom (uniform scale => ratio kept)."""
        z = self.zoom
        cell = max(2, round(_CELL * z))
        gap = max(1, round(_GAP * z))
        return {
            "cell": cell,
            "gap": gap,
            "step": cell + gap,
            "left": round(_LEFT_PAD * z),
            "top": round(_TOP_PAD * z),
            "pad": round(8 * z),
            "font": max(8, round(9 * z)),
            "outline": max(2, round(z)),
        }

    def _zoom_by(self, factor: float) -> None:
        self.zoom = min(ZOOM_MAX, max(ZOOM_MIN, self.zoom * factor))
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        self._m = self._metrics()
        self.zoom_var.set(f"{int(round(self.zoom * 100))}%")
        self._draw()

    def _on_zoom_wheel(self, event: tk.Event) -> str:
        self._zoom_by(1.25 if event.delta > 0 else 1 / 1.25)
        return "break"

    def _on_scroll_wheel(self, event: tk.Event) -> str:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _scroll_v(self, direction: int) -> str:
        self.canvas.yview_scroll(direction, "units")
        return "break"

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
        for col_idx, column in enumerate(columns):
            col_meta: list[dict] = []
            for row_idx, cell_obj in enumerate(column):
                x0 = left + col_idx * step
                y0 = top + row_idx * step
                if cell_obj.in_range:
                    fill = colors[cell_obj.level]
                    self.canvas.create_rectangle(
                        x0, y0, x0 + cell, y0 + cell, fill=fill, outline=fill
                    )
                    note = self.highlight.get(cell_obj.day.isoformat())
                    if note is not None:
                        self.canvas.create_rectangle(
                            x0 - pad, y0 - pad, x0 + cell + pad, y0 + cell + pad,
                            fill="", outline=outline, width=m["outline"],
                        )
                col_meta.append({"day": cell_obj.day, "count": cell_obj.count, "in_range": cell_obj.in_range,
                                 "note": self.highlight.get(cell_obj.day.isoformat())})
                # Day labels (Mon / Wed / Fri).
                if col_idx == 0 and row_idx in (1, 3, 5):
                    names = {1: "Mon", 3: "Wed", 5: "Fri"}
                    self.canvas.create_text(
                        left - round(6 * self.zoom), y0 + cell / 2, text=names[row_idx],
                        anchor="e", font=label_font, fill=label_fg,
                    )
            # Month label when the month changes (skip crowded ones).
            first_day = column[0].day
            if first_day.day <= 7 and col_idx - last_month_col >= 3:
                self.canvas.create_text(
                    left + col_idx * step, top - round(6 * self.zoom),
                    text=month_names[first_day.month - 1],
                    anchor="sw", font=label_font, fill=label_fg,
                )
                last_month_col = col_idx
            self._cells.append(col_meta)
        graph_w = left + 53 * step + m["pad"]
        graph_h = top + 7 * step + m["pad"]
        self.canvas.configure(scrollregion=(0, 0, graph_w, graph_h))
        # Cap the viewport so huge zooms stay usable; scrollbars take over.
        try:
            max_w = int(self.winfo_screenwidth() * 0.85)
            max_h = int(self.winfo_screenheight() * 0.55)
        except tk.TclError:
            max_w, max_h = graph_w, graph_h
        self.canvas.configure(width=min(graph_w, max_w), height=min(graph_h, max_h))
        self.zoom_var.set(f"{int(round(self.zoom * 100))}%")
        # Shrink-wrap the window around the table so frame and graph stay glued.
        try:
            self.update_idletasks()
            self.geometry("")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ hover
    def _on_hover(self, event: tk.Event) -> None:
        m = self._m
        # Viewport coords -> canvas coords (the canvas scrolls at big zooms).
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
                if meta["note"]:
                    text += f" — {meta['note']}"
                self.status_var.set(text)
                return
        self._set_status_default()

    def _set_status_default(self) -> None:
        if self.highlight:
            self.status_var.set("Gold outline = planned commits. Hover a day for details.")
        else:
            self.status_var.set("Hover a day for details. Ctrl+wheel zooms.")

    # ------------------------------------------------------------------ close
    def _on_close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        # Re-arm the parent dialog's grab for nested-modal (move preview) use.
        try:
            if isinstance(self._parent, tk.Toplevel):
                self._parent.grab_set()
        except tk.TclError:
            pass
        self.destroy()
