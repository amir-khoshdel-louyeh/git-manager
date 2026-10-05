"""Commit selection dialog with date options (mode B layout)."""

from __future__ import annotations

import tkinter as tk
from datetime import timedelta
from tkinter import messagebox, ttk
from typing import Callable, Optional

from utils.time_utils import (
    build_custom_iso,
    is_after_last_commit,
    is_future,
    now_date_str,
    now_time_str,
    parse_iso_to_dt,
)
from ui.dialogs.contribution_graph import ContributionGraph


def suggest_date_after(last_commit_iso: Optional[str]) -> str:
    """Return the suggested date: day after the last commit (YYYY-MM-DD).

    Falls back to today when there is no last commit or it can't be parsed.
    """
    if last_commit_iso:
        try:
            return (parse_iso_to_dt(last_commit_iso).date() + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return now_date_str()


# Display scale for this dialog (sizes and fonts are multiplied by this).
_UI_SCALE = 1.5


def _px(value: int) -> int:
    """Scale a pixel size (padding, width, wrap length, geometry)."""
    return int(round(value * _UI_SCALE))


def _font(name: str, size: int, *attrs: str) -> tuple:
    """Scale a font tuple, e.g. _font("Helvetica", 10, "bold")."""
    return (name, int(round(size * _UI_SCALE)), *attrs)


class NumericKeypadDialog(tk.Toplevel):
    """Dialog for selecting number of commits with date options (mode B layout).

    When ``show_date_options`` is True (used for Move Commits), the dialog shows
    a horizontally-split layout:
    - Left column: repository navigator (when ``repo_options`` are given) +
      "Commits to move" count spinbox + commit list preview showing the first
      N pending commits (oldest first). Switching repository reloads the
      count, list, last-commit info and date defaults, so several
      repositories can be pushed one after another.
    - Right column: last commit info + "When" section (Today / Day / Range).
      Only the sub-panel of the selected mode is visible; specific day is
      date-only plus a time range (from → to) on that same day.
    A live summary line spans the bottom above OK/Cancel.

    ``repo_options`` entries are dicts with ``name``, ``path``,
    ``base_branch``, ``pending``, ``commit_items``, ``last_commit_info`` and
    ``last_commit_iso``. The chosen entry is available as ``selected_repo``
    after OK (``result`` stays the plain commit count).
    """

    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        prompt: str,
        minvalue: int = 1,
        maxvalue: int = 100,
        theme_mode: str = "light",
        show_date_options: bool = False,
        last_commit_info: Optional[str] = None,
        last_commit_iso: Optional[str] = None,
        work_start_hour: str = "09:00",
        work_end_hour: str = "18:00",
        min_commits_per_day: int = 1,
        max_commits_per_day: int = 10,
        commit_items: Optional[list[str]] = None,
        on_preview: Optional[Callable[[], None]] = None,
        repo_options: Optional[list[dict]] = None,
        selected_index: int = 0,
        graph_author: str = "",
    ) -> None:
        super().__init__(parent)
        self.title(title)
        # Bigger window: allow resizing horizontally, but keep minsize large
        self.minsize(_px(920), _px(600) - 25)
        self.resizable(True, True)
        self.result: Optional[int] = None
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.theme_mode = theme_mode
        self.show_date_options = show_date_options
        self.last_commit_info = last_commit_info
        self.last_commit_iso = last_commit_iso

        # Date/time selection state (only relevant when show_date_options)
        self.date_mode: str = "current"
        self.custom_iso: Optional[str] = None
        self.custom_start_iso: Optional[str] = None
        self.custom_end_iso: Optional[str] = None
        self.range_start_iso: Optional[str] = None
        self.range_end_iso: Optional[str] = None
        self.date_mode_var: Optional[tk.StringVar] = None
        self.custom_date_var: Optional[tk.StringVar] = None
        self.custom_time_from_var: Optional[tk.StringVar] = None
        self.custom_time_to_var: Optional[tk.StringVar] = None
        self.range_start_date_var: Optional[tk.StringVar] = None
        self.range_end_date_var: Optional[tk.StringVar] = None
        self.min_commits_per_day = max(0, int(min_commits_per_day))
        self.max_commits_per_day = max(1, int(max_commits_per_day))
        # Pending commits (oldest first), e.g. ["a1b2c3 Fix login", ...]
        self.commit_items: list[str] = list(commit_items or [])
        self.on_preview: Optional[Callable[[], None]] = on_preview

        # Multi-repo navigation (Move Commits): each option carries everything
        # needed to render one repository; switching reloads the panel.
        self.repo_options: list[dict] = list(repo_options or [])
        if self.repo_options:
            selected_index = max(0, min(int(selected_index), len(self.repo_options) - 1))
            opt = self.repo_options[selected_index]
            minvalue = 1
            maxvalue = max(1, int(opt.get("pending", 1)))
            last_commit_info = opt.get("last_commit_info")
            last_commit_iso = opt.get("last_commit_iso")
            commit_items = list(opt.get("commit_items") or [])
            self.commit_items = list(commit_items)
        self._repo_index: int = selected_index if self.repo_options else -1
        self.selected_repo: Optional[dict] = (
            self.repo_options[self._repo_index] if self.repo_options else None
        )
        # Embedded contribution graph (bottom of the Move dialog).
        self.graph_author: str = graph_author or ""
        self.graph: Optional[ContributionGraph] = None
        self.graph_frame: Optional[ttk.LabelFrame] = None
        self._graph_job: Optional[str] = None

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Prompt label (spans full width, top)
        self.prompt_label = ttk.Label(self, text=prompt, font=_font("Helvetica", 12, "bold"), justify=tk.CENTER, style="Dialog.TLabel", wraplength=_px(820))
        self.prompt_label.pack(pady=(_px(16), _px(10)), padx=_px(20), fill=tk.X)
        if self.repo_options:
            self.prompt_label.configure(text=self._prompt_for(self.repo_options[self._repo_index]))

        # ===================== HORIZONTAL GRID CONTENT =====================
        content = ttk.Frame(self, style="Dialog.TFrame")
        content.pack(fill=tk.BOTH, expand=True, padx=_px(20), pady=_px(4))

        if self.show_date_options:
            # Horizontal split: left = count + commit list, right = date options
            content.columnconfigure(0, weight=1, uniform="col")
            content.columnconfigure(1, weight=1, uniform="col")
            content.rowconfigure(0, weight=1)

            # ----- LEFT COLUMN: repository navigator + commits to move -----
            left = ttk.LabelFrame(content, text="Commits to move", padding=_px(14), style="Dialog.TLabelframe")
            left.grid(row=0, column=0, sticky="nsew", padx=(0, _px(10)), pady=_px(5))
            left.columnconfigure(0, weight=1)
            # Row offset when the repository navigator is present.
            ro = 1 if self.repo_options else 0
            left.rowconfigure(ro + 2, weight=1)

            if self.repo_options:
                repo_frame = ttk.LabelFrame(left, text="Repository (has commits to push)", padding=_px(4), style="Dialog.TLabelframe")
                repo_frame.grid(row=0, column=0, sticky="ew", pady=(0, _px(4)))
                repo_frame.columnconfigure(0, weight=1)
                repo_bg = "#1e2228" if theme_mode == "dark" else "#f1f5f9"
                repo_fg = "#e8e8e8" if theme_mode == "dark" else "#111827"
                self.repo_listbox = tk.Listbox(
                    repo_frame,
                    height=min(6, len(self.repo_options)),
                    font=_font("Helvetica", 10),
                    bg=repo_bg,
                    fg=repo_fg,
                    selectbackground="#4a90d9",
                    selectforeground="#ffffff",
                    activestyle="none",
                    highlightthickness=0,
                    relief=tk.SOLID,
                    bd=1,
                    exportselection=False,
                )
                self.repo_listbox.grid(row=0, column=0, sticky="ew")
                repo_scroll = ttk.Scrollbar(repo_frame, orient=tk.VERTICAL, command=self.repo_listbox.yview)
                repo_scroll.grid(row=0, column=1, sticky="ns")
                self.repo_listbox.configure(yscrollcommand=repo_scroll.set)
                for option in self.repo_options:
                    if option.get("path"):
                        self.repo_listbox.insert(tk.END, f"{option.get('name')} ({option.get('pending')})")
                    else:
                        self.repo_listbox.insert(tk.END, option.get("name"))
                self.repo_listbox.selection_set(self._repo_index)
                self.repo_listbox.see(self._repo_index)
                self.repo_listbox.bind("<<ListboxSelect>>", self._on_repo_select)

            # Count row: slider + number + All button + total (easy grab, no tiny +/-)
            self.value_var = tk.StringVar(value=str(maxvalue))
            self._syncing_scale = False
            count_row = ttk.Frame(left, style="Dialog.TFrame")
            count_row.grid(row=ro + 0, column=0, sticky="ew", pady=(_px(2), _px(8)))
            ttk.Label(count_row, text="Count:", font=_font("Helvetica", 11, "bold"), style="Dialog.TLabel").pack(side=tk.LEFT)
            scale_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
            scale_trough = "#1e2228" if theme_mode == "dark" else "#d7dde5"
            scale_fg = "#e8e8e8" if theme_mode == "dark" else "#111827"
            self.count_scale = tk.Scale(
                count_row,
                from_=minvalue,
                to=maxvalue,
                orient=tk.HORIZONTAL,
                resolution=1,
                showvalue=False,
                tickinterval=0,
                length=_px(200),
                width=_px(18),
                sliderlength=_px(30),
                command=self._on_slide,
                bg=scale_bg,
                fg=scale_fg,
                troughcolor=scale_trough,
                activebackground="#4a90d9",
                highlightthickness=0,
                bd=0,
            )
            self.count_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(_px(8), _px(4)))
            self.count_scale.set(maxvalue)
            ttk.Label(count_row, textvariable=self.value_var, font=_font("Helvetica", 12, "bold"), width=_px(4), anchor=tk.CENTER, style="Dialog.TLabel").pack(side=tk.LEFT)
            ttk.Button(count_row, text="All", width=_px(6), command=self._on_select_all, style="Dialog.TButton").pack(side=tk.LEFT, padx=(_px(8), 0))
            self.of_var = tk.StringVar(value=f"of {maxvalue}")
            ttk.Label(count_row, textvariable=self.of_var, font=_font("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT, padx=(_px(8), 0))

            self.count_info_var = tk.StringVar(value="")
            ttk.Label(left, textvariable=self.count_info_var, font=_font("Helvetica", 9, "italic"), style="Dialog.TLabel").grid(row=ro + 1, column=0, sticky="w", pady=(0, _px(6)))

            # Commit list preview (first N, oldest first)
            list_frame = ttk.Frame(left, style="Dialog.TFrame")
            list_frame.grid(row=ro + 2, column=0, sticky="nsew")
            list_frame.columnconfigure(0, weight=1)
            list_frame.rowconfigure(0, weight=1)
            entry_bg = "#1e2228" if theme_mode == "dark" else "#f1f5f9"
            entry_fg = "#e8e8e8" if theme_mode == "dark" else "#111827"
            self.commit_listbox = tk.Listbox(
                list_frame,
                height=_px(12),
                width=_px(44),
                font=_font("Courier", 9),
                bg=entry_bg,
                fg=entry_fg,
                selectbackground=entry_bg,
                selectforeground=entry_fg,
                activestyle="none",
                highlightthickness=0,
                relief=tk.SOLID,
                bd=1,
                takefocus=0,
                cursor="hand2",
            )
            self.commit_listbox.grid(row=0, column=0, sticky="nsew")
            list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.commit_listbox.yview)
            list_scroll.grid(row=0, column=1, sticky="ns")
            self.commit_listbox.configure(yscrollcommand=list_scroll.set)
            # Click a row to select the first N commits up to that row
            self.commit_listbox.bind("<ButtonRelease-1>", self._on_list_click)
            ttk.Label(
                left,
                text="Tip: drag the slider or click a row to pick how many.",
                font=_font("Helvetica", 8, "italic"),
                style="Dialog.TLabel",
            ).grid(row=ro + 3, column=0, sticky="w", pady=(_px(6), 0))

            # ----- RIGHT COLUMN -----
            right = ttk.Frame(content, style="Dialog.TFrame")
            right.grid(row=0, column=1, sticky="nsew", padx=(_px(10), 0), pady=_px(5))
            right.columnconfigure(0, weight=1)
            right.rowconfigure(1, weight=1)

            # Last commit info — compact, collapsible feel
            # (StringVar-backed when switching repositories dynamically)
            self.info_text_var: Optional[tk.StringVar] = None
            self.info_hint_var: Optional[tk.StringVar] = None
            if self.repo_options or self.last_commit_info:
                info_frame = ttk.LabelFrame(right, text="Last commit on base", padding=_px(10), style="Dialog.TLabelframe")
                info_frame.grid(row=0, column=0, sticky="ew", pady=(0, _px(10)))
                info_frame.columnconfigure(0, weight=1)
                if self.repo_options:
                    self.info_text_var = tk.StringVar(value=self.last_commit_info or "")
                    info_label = ttk.Label(
                        info_frame,
                        textvariable=self.info_text_var,
                        font=_font("Courier", 9),
                        wraplength=_px(380),
                        justify=tk.LEFT,
                        style="Dialog.TLabel",
                    )
                else:
                    info_label = ttk.Label(
                        info_frame,
                        text=self.last_commit_info,
                        font=_font("Courier", 9),
                        wraplength=_px(380),
                        justify=tk.LEFT,
                        style="Dialog.TLabel",
                    )
                info_label.grid(row=0, column=0, sticky="w")
                if self.repo_options:
                    self.info_hint_var = tk.StringVar(
                        value="Chosen date must be after this commit." if self.last_commit_info else ""
                    )
                    ttk.Label(
                        info_frame,
                        textvariable=self.info_hint_var,
                        font=_font("Helvetica", 8, "italic"),
                        style="Dialog.TLabel",
                    ).grid(row=1, column=0, sticky="w", pady=(_px(6), 0))
                else:
                    ttk.Label(
                        info_frame,
                        text="Chosen date must be after this commit.",
                        font=_font("Helvetica", 8, "italic"),
                        style="Dialog.TLabel",
                    ).grid(row=1, column=0, sticky="w", pady=(_px(6), 0))
            else:
                ttk.Label(
                    right,
                    text="No prior commits on base (first commit). Any date is allowed.",
                    font=_font("Helvetica", 9, "italic"),
                    style="Dialog.TLabel",
                    wraplength=_px(380),
                ).grid(row=0, column=0, sticky="ew", pady=(0, _px(10)))

            date_frame = ttk.LabelFrame(right, text="When", padding=_px(12), style="Dialog.TLabelframe")
            date_frame.grid(row=1, column=0, sticky="new", pady=_px(5))
            date_frame.columnconfigure(0, weight=1)

            self.date_mode_var = tk.StringVar(value="current")

            # Mode switch: single horizontal row (Today | Day | Range)
            mode_row = ttk.Frame(date_frame, style="Dialog.TFrame")
            mode_row.grid(row=0, column=0, sticky="ew", pady=(_px(2), _px(8)))
            ttk.Radiobutton(
                mode_row,
                text="Today",
                variable=self.date_mode_var,
                value="current",
                style="Dialog.TRadiobutton",
                command=self._on_date_mode_change,
            ).pack(side=tk.LEFT, padx=(0, _px(12)))
            ttk.Radiobutton(
                mode_row,
                text="Day",
                variable=self.date_mode_var,
                value="custom",
                style="Dialog.TRadiobutton",
                command=self._on_date_mode_change,
            ).pack(side=tk.LEFT, padx=_px(12))
            ttk.Radiobutton(
                mode_row,
                text="Range",
                variable=self.date_mode_var,
                value="range",
                style="Dialog.TRadiobutton",
                command=self._on_date_mode_change,
            ).pack(side=tk.LEFT, padx=_px(12))

            custom_frame = ttk.Frame(date_frame, style="Dialog.TFrame")
            custom_frame.grid(row=1, column=0, sticky="ew", padx=(_px(8), 0), pady=(0, _px(4)))
            custom_frame.columnconfigure(1, weight=1)
            self._custom_frame = custom_frame

            self.custom_date_var = tk.StringVar(value=suggest_date_after(last_commit_iso))
            self.custom_time_from_var = tk.StringVar(value=work_start_hour)
            self.custom_time_to_var = tk.StringVar(value=work_end_hour)

            ttk.Label(custom_frame, text="Date (YYYY-MM-DD):", font=_font("Helvetica", 10), style="Dialog.TLabel").grid(row=0, column=0, sticky="w", pady=_px(4), padx=(_px(4), _px(8)))
            self.custom_date_entry = ttk.Entry(custom_frame, textvariable=self.custom_date_var, width=_px(20), style="Dialog.TEntry", font=_font("Helvetica", 10))
            self.custom_date_entry.grid(row=0, column=1, sticky="ew", pady=_px(4), padx=(0, _px(4)))
            ttk.Label(custom_frame, text="From (HH:MM):", font=_font("Helvetica", 10), style="Dialog.TLabel").grid(row=1, column=0, sticky="w", pady=_px(4), padx=(_px(4), _px(8)))
            self.custom_time_from_entry = ttk.Entry(custom_frame, textvariable=self.custom_time_from_var, width=_px(20), style="Dialog.TEntry", font=_font("Helvetica", 10), justify=tk.CENTER)
            self.custom_time_from_entry.grid(row=1, column=1, sticky="ew", pady=_px(4), padx=(0, _px(4)))
            ttk.Label(custom_frame, text="To (HH:MM):", font=_font("Helvetica", 10), style="Dialog.TLabel").grid(row=2, column=0, sticky="w", pady=_px(4), padx=(_px(4), _px(8)))
            self.custom_time_to_entry = ttk.Entry(custom_frame, textvariable=self.custom_time_to_var, width=_px(20), style="Dialog.TEntry", font=_font("Helvetica", 10), justify=tk.CENTER)
            self.custom_time_to_entry.grid(row=2, column=1, sticky="ew", pady=_px(4), padx=(0, _px(4)))

            range_frame = ttk.Frame(date_frame, style="Dialog.TFrame")
            range_frame.grid(row=2, column=0, sticky="ew", padx=(_px(8), 0), pady=(0, _px(2)))
            range_frame.columnconfigure(1, weight=1)
            self._range_frame = range_frame

            self.range_start_date_var = tk.StringVar(value=suggest_date_after(last_commit_iso))
            self.range_end_date_var = tk.StringVar(value=suggest_date_after(last_commit_iso))

            ttk.Label(range_frame, text="From (YYYY-MM-DD):", font=_font("Helvetica", 10), style="Dialog.TLabel").grid(row=0, column=0, sticky="w", pady=_px(4), padx=(_px(4), _px(8)))
            self.range_start_entry = ttk.Entry(range_frame, textvariable=self.range_start_date_var, width=_px(20), style="Dialog.TEntry", font=_font("Helvetica", 10))
            self.range_start_entry.grid(row=0, column=1, sticky="ew", pady=_px(4), padx=(0, _px(4)))

            ttk.Label(range_frame, text="To (YYYY-MM-DD):", font=_font("Helvetica", 10), style="Dialog.TLabel").grid(row=1, column=0, sticky="w", pady=_px(4), padx=(_px(4), _px(8)))
            self.range_end_entry = ttk.Entry(range_frame, textvariable=self.range_end_date_var, width=_px(20), style="Dialog.TEntry", font=_font("Helvetica", 10))
            self.range_end_entry.grid(row=1, column=1, sticky="ew", pady=_px(4), padx=(0, _px(4)))

            self.range_hint_label = ttk.Label(
                range_frame,
                text="",
                font=_font("Helvetica", 8, "italic"),
                style="Dialog.TLabel",
                wraplength=_px(380),
                justify=tk.LEFT,
            )
            self.range_hint_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(_px(6), 0), padx=_px(4))

            self._set_custom_entries_state(tk.DISABLED)
            self._set_range_entries_state(tk.DISABLED)
            self._update_date_panels()
            # Live updates: refresh list, capacity hint and summary on any change
            self.range_start_date_var.trace_add("write", lambda *a: self._refresh_live())
            self.range_end_date_var.trace_add("write", lambda *a: self._refresh_live())
            self.custom_date_var.trace_add("write", lambda *a: self._update_summary())
            self.custom_time_from_var.trace_add("write", lambda *a: self._update_summary())
            self.custom_time_to_var.trace_add("write", lambda *a: self._update_summary())
            self.value_var.trace_add("write", lambda *a: self._refresh_live())
            if self.repo_options:
                self._select_repo(self._repo_index)
            self._refresh_commit_list()
            self._update_range_hint()
            self._update_summary()

        else:
            # Simple mode: no date options, single centered column but still big
            content.columnconfigure(0, weight=1)
            content.rowconfigure(0, weight=1)

            single = ttk.LabelFrame(content, text="Select number", padding=_px(16), style="Dialog.TLabelframe")
            single.grid(row=0, column=0, sticky="nsew", padx=_px(40))
            single.columnconfigure(0, weight=1)

            self.value_var = tk.StringVar(value="0")
            entry_bg = "#1e2228" if theme_mode == "dark" else "#f1f5f9"
            entry_fg = "#e8e8e8" if theme_mode == "dark" else "#111827"
            display = tk.Entry(
                single,
                textvariable=self.value_var,
                font=_font("Helvetica", 18, "bold"),
                width=_px(20),
                justify=tk.CENTER,
                state="readonly",
                bg=entry_bg,
                fg=entry_fg,
                readonlybackground=entry_bg,
                disabledforeground=entry_fg,
                relief=tk.SOLID,
                bd=1,
            )
            display.grid(row=0, column=0, pady=(_px(8), _px(14)), sticky="ew")

            keypad_frame = ttk.Frame(single, style="Dialog.TFrame")
            keypad_frame.grid(row=1, column=0, pady=_px(6))

            buttons = [
                ["7", "8", "9"],
                ["4", "5", "6"],
                ["1", "2", "3"],
                ["0", "C", "⌫"],
            ]

            for r, row in enumerate(buttons):
                row_frame = ttk.Frame(keypad_frame, style="Dialog.TFrame")
                row_frame.grid(row=r, column=0, pady=_px(3))
                for c, btn_text in enumerate(row):
                    btn = ttk.Button(row_frame, text=btn_text, width=_px(8), command=lambda t=btn_text: self._on_key(t))
                    btn.grid(row=0, column=c, padx=_px(5), pady=_px(3), ipadx=_px(4), ipady=_px(10))

        # ---------- embedded contributions graph (bottom) ----------
        if self.show_date_options:
            self.graph_frame = ttk.LabelFrame(self, text="Contributions", padding=_px(10), style="Dialog.TLabelframe")
            self.graph_frame.pack(fill=tk.X, padx=_px(20), pady=(_px(4), _px(2)))
            self.graph = ContributionGraph(self.graph_frame, theme_mode=theme_mode, initial_zoom=1.0)
            self.graph.pack(fill=tk.X)
            if self.repo_options:
                try:
                    self.graph_frame.configure(
                        text=f"Contributions — {self.repo_options[self._repo_index].get('name')}"
                    )
                except (tk.TclError, AttributeError):
                    pass
            self._refresh_graph()

        # Live summary line (spans full width, above buttons)
        self.summary_label: Optional[ttk.Label] = None
        if self.show_date_options:
            self.summary_var = tk.StringVar(value="")
            self.summary_label = ttk.Label(
                self,
                textvariable=self.summary_var,
                font=_font("Helvetica", 10, "bold"),
                justify=tk.CENTER,
                style="Dialog.TLabel",
                wraplength=_px(860),
            )
            self.summary_label.pack(pady=(_px(4), _px(2)), padx=_px(20), fill=tk.X)
            if self.on_preview is not None:
                preview_row = ttk.Frame(self, style="Dialog.TFrame")
                preview_row.pack(pady=(0, _px(4)), fill=tk.X)
                inner_preview = ttk.Frame(preview_row, style="Dialog.TFrame")
                inner_preview.pack(anchor=tk.CENTER)
                ttk.Button(
                    inner_preview,
                    text="👁 Preview on graph",
                    command=self.on_preview,
                    style="Dialog.TButton",
                ).pack()

        # OK and Cancel buttons - bottom, centered, bigger
        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(pady=_px(16), fill=tk.X)
        inner_btn = ttk.Frame(button_frame, style="Dialog.TFrame")
        inner_btn.pack(anchor=tk.CENTER)
        ok_btn = ttk.Button(inner_btn, text="OK", command=self._on_ok, style="Dialog.TButton", width=_px(12))
        ok_btn.pack(side=tk.LEFT, padx=_px(8), ipady=_px(4))
        cancel_btn = ttk.Button(inner_btn, text="Cancel", command=self._on_cancel, style="Dialog.TButton", width=_px(12))
        cancel_btn.pack(side=tk.LEFT, padx=_px(8), ipady=_px(4))

        # Bind keyboard events
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        # Center on parent and enforce bigger geometry
        self.update_idletasks()
        # Enforce larger size for move dialog
        if self.show_date_options:
            cur_w = self.winfo_width()
            cur_h = self.winfo_height()
            target_w = max(cur_w, _px(920))
            target_h = max(cur_h, _px(600) - 25)
            self.geometry(f"{target_w}x{target_h}")
            self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        try:
            if self.show_date_options and hasattr(self, "count_scale"):
                self.count_scale.focus_set()
        except tk.TclError:
            pass

    def _set_custom_entries_state(self, state: str) -> None:
        if hasattr(self, "custom_date_entry"):
            self.custom_date_entry.configure(state=state)
        if hasattr(self, "custom_time_from_entry"):
            self.custom_time_from_entry.configure(state=state)
            self.custom_time_to_entry.configure(state=state)

    @staticmethod
    def _prompt_for(opt: dict) -> str:
        """Prompt line for one repository option (count info is enough)."""
        if not opt.get("path"):
            return "Select a repository to move its commits."
        return (
            f"How many commits to move to {opt.get('base_branch')}?\n"
            f"(1 to {opt.get('pending')})"
        )

    def _on_repo_select(self, event: tk.Event | None = None) -> None:
        """Repository navigator clicked: reload the panel for that repo."""
        try:
            sel = self.repo_listbox.curselection()
            if not sel:
                return
            idx = int(sel[0])
        except (tk.TclError, ValueError, AttributeError):
            return
        if idx == self._repo_index:
            return
        self._select_repo(idx)
        self._update_range_hint()
        self._update_summary()

    def _select_repo(self, idx: int) -> None:
        """Switch the whole panel to another repository option."""
        if not self.repo_options:
            return
        idx = max(0, min(int(idx), len(self.repo_options) - 1))
        self._repo_index = idx
        opt = self.repo_options[idx]
        self.selected_repo = opt
        pending = max(1, int(opt.get("pending", 1)))
        self.minvalue = 1
        self.maxvalue = pending
        self.last_commit_info = opt.get("last_commit_info")
        self.last_commit_iso = opt.get("last_commit_iso")
        self.commit_items = list(opt.get("commit_items") or [])
        try:
            self.prompt_label.configure(text=self._prompt_for(opt))
        except (tk.TclError, AttributeError):
            pass
        try:
            self.value_var.set(str(pending))
        except (tk.TclError, AttributeError):
            pass
        if getattr(self, "of_var", None) is not None:
            try:
                self.of_var.set(f"of {pending}")
            except (tk.TclError, AttributeError):
                pass
        if hasattr(self, "count_scale"):
            try:
                self.count_scale.configure(from_=1, to=pending)
            except tk.TclError:
                pass
        self._refresh_commit_list()
        if getattr(self, "info_text_var", None) is not None:
            try:
                info = self.last_commit_info
                if not opt.get("path"):
                    self.info_text_var.set("No repository selected — pick one from the list above.")
                    if getattr(self, "info_hint_var", None) is not None:
                        self.info_hint_var.set("")
                else:
                    self.info_text_var.set(
                        info if info else "No prior commits on base (first commit). Any date is allowed."
                    )
                    if getattr(self, "info_hint_var", None) is not None:
                        self.info_hint_var.set("Chosen date must be after this commit." if info else "")
            except (tk.TclError, AttributeError):
                pass
        # Date defaults follow the new repo's tip commit.
        try:
            if self.custom_date_var is not None:
                self.custom_date_var.set(suggest_date_after(self.last_commit_iso))
            if self.range_start_date_var is not None:
                self.range_start_date_var.set(suggest_date_after(self.last_commit_iso))
            if self.range_end_date_var is not None:
                self.range_end_date_var.set(suggest_date_after(self.last_commit_iso))
        except (tk.TclError, AttributeError):
            pass
        # Embedded graph follows the newly picked repository.
        if getattr(self, "graph_frame", None) is not None:
            try:
                self.graph_frame.configure(text=f"Contributions — {opt.get('name')}")
            except (tk.TclError, AttributeError):
                pass
        self._schedule_graph_refresh()

    def _set_range_entries_state(self, state: str) -> None:
        if hasattr(self, "range_start_entry"):
            self.range_start_entry.configure(state=state)
            self.range_end_entry.configure(state=state)

    def _update_date_panels(self) -> None:
        """Show only the sub-panel belonging to the selected mode."""
        if self.date_mode_var is None or not hasattr(self, "_custom_frame"):
            return
        mode = self.date_mode_var.get()
        if mode == "custom":
            self._custom_frame.grid()
            self._range_frame.grid_remove()
        elif mode == "range":
            self._custom_frame.grid_remove()
            self._range_frame.grid()
        else:
            self._custom_frame.grid_remove()
            self._range_frame.grid_remove()

    def _range_day_count(self) -> Optional[int]:
        """Return the number of days in the range, or None if dates invalid."""
        from datetime import datetime as _dt

        try:
            start = self.range_start_date_var.get().strip() if self.range_start_date_var else ""
            end = self.range_end_date_var.get().strip() if self.range_end_date_var else ""
            d0 = _dt.strptime(start, "%Y-%m-%d").date()
            d1 = _dt.strptime(end, "%Y-%m-%d").date()
        except (ValueError, AttributeError):
            return None
        if d1 < d0:
            return None
        return (d1 - d0).days + 1

    def _range_capacity(self) -> Optional[tuple[int, int, int]]:
        """Return (days, min_fit, max_fit) for the current range, or None."""
        days = self._range_day_count()
        if days is None:
            return None
        return days, days * self.min_commits_per_day, days * self.max_commits_per_day

    def _update_range_hint(self) -> None:
        """Refresh the live capacity hint under the range entries."""
        if not hasattr(self, "range_hint_label"):
            return
        cap = self._range_capacity()
        if cap is None:
            self.range_hint_label.configure(text="Enter valid From/To dates (YYYY-MM-DD).")
            try:
                self.range_hint_label.configure(foreground="")
            except tk.TclError:
                pass
            return
        days, lo_fit, hi_fit = cap
        try:
            count = int(self.value_var.get()) if hasattr(self, "value_var") else 0
        except (ValueError, tk.TclError):
            count = 0
        base = (
            f"{days} day(s) × {self.min_commits_per_day}–{self.max_commits_per_day}/day "
            f"fits {lo_fit}–{hi_fit} commits."
        )
        if self.minvalue > 0 and count > 0 and (count < lo_fit or count > hi_fit):
            self.range_hint_label.configure(text=f"⚠ {base} Selected: {count} — outside this fit!")
            try:
                self.range_hint_label.configure(foreground="red")
            except tk.TclError:
                pass
        else:
            self.range_hint_label.configure(text=base)
            try:
                self.range_hint_label.configure(foreground="")
            except tk.TclError:
                pass

    def _on_date_mode_change(self) -> None:
        if self.date_mode_var is None:
            return
        mode = self.date_mode_var.get()
        if mode == "custom":
            self._set_custom_entries_state(tk.NORMAL)
            self._set_range_entries_state(tk.DISABLED)
            self._update_date_panels()
            # Focus date entry for convenience
            try:
                self.custom_date_entry.focus_set()
            except tk.TclError:
                pass
        elif mode == "range":
            self._set_custom_entries_state(tk.DISABLED)
            self._set_range_entries_state(tk.NORMAL)
            self._update_date_panels()
            try:
                self.range_start_entry.focus_set()
            except tk.TclError:
                pass
        else:
            self._set_custom_entries_state(tk.DISABLED)
            self._set_range_entries_state(tk.DISABLED)
            self._update_date_panels()
        self._update_summary()

    def _selected_count(self) -> int:
        """Return the clamped commit count from the count field."""
        try:
            value = int(self.value_var.get())
        except (ValueError, tk.TclError, AttributeError):
            return 0
        return max(0, min(value, len(self.commit_items) if self.commit_items else self.maxvalue))

    def _on_slide(self, val: str) -> None:
        """Slider moved: push the value into the count field."""
        if self._syncing_scale:
            return
        try:
            self.value_var.set(str(int(float(val))))
        except (ValueError, tk.TclError):
            pass

    def _sync_scale(self) -> None:
        """Move the slider to match the count field (guarded, no loops)."""
        if not hasattr(self, "count_scale"):
            return
        try:
            target = int(self.value_var.get())
        except (ValueError, tk.TclError, AttributeError):
            return
        target = max(self.minvalue, min(target, self.maxvalue))
        try:
            if int(float(self.count_scale.get())) == target:
                return
        except (ValueError, tk.TclError):
            return
        self._syncing_scale = True
        try:
            self.count_scale.set(target)
        finally:
            self._syncing_scale = False

    def _on_list_click(self, event: tk.Event) -> None:
        """Clicking row i selects the first i+1 commits."""
        try:
            idx = self.commit_listbox.nearest(event.y)
            if idx < 0 or idx >= self.commit_listbox.size():
                return
            bbox = self.commit_listbox.bbox(idx)
            if bbox is None or event.y > bbox[1] + bbox[3]:
                return  # clicked empty space below the rows
            self.value_var.set(str(idx + 1))
        except (tk.TclError, AttributeError):
            pass

    def _on_select_all(self) -> None:
        """Select all pending commits."""
        self.value_var.set(str(self.maxvalue))

    def _refresh_live(self) -> None:
        """Refresh commit list, slider, capacity hint and summary together."""
        self._refresh_commit_list()
        self._sync_scale()
        self._update_range_hint()
        self._update_summary()
        self._schedule_graph_refresh()

    def _refresh_commit_list(self) -> None:
        """Show the first N pending commits (oldest first) in the listbox."""
        if not hasattr(self, "commit_listbox"):
            return
        count = self._selected_count()
        self.commit_listbox.delete(0, tk.END)
        for i, item in enumerate(self.commit_items[:count]):
            self.commit_listbox.insert(tk.END, f"{i + 1}. {item}")
        total = len(self.commit_items)
        if hasattr(self, "count_info_var"):
            self.count_info_var.set(f"Showing first {count} of {total} pending commit(s).")

    def _update_summary(self) -> None:
        """Refresh the live plan summary line."""
        self._schedule_graph_refresh()
        if getattr(self, "summary_label", None) is None or self.date_mode_var is None:
            return
        count = self._selected_count()
        mode = self.date_mode_var.get()
        if mode == "custom":
            date = self.custom_date_var.get().strip() if self.custom_date_var else ""
            frm = self.custom_time_from_var.get().strip() if self.custom_time_from_var else ""
            to = self.custom_time_to_var.get().strip() if self.custom_time_to_var else ""
            text = f"{count} commit(s) → {date or '…'}, {frm or '…'}–{to or '…'}"
        elif mode == "range":
            cap = self._range_capacity()
            if cap is not None:
                days, lo_fit, hi_fit = cap
                text = f"{count} commit(s) → {days} day(s), fits {lo_fit}–{hi_fit}"
            else:
                text = f"{count} commit(s) → …"
        else:
            text = f"{count} commit(s) → today, current time"
        try:
            self.summary_var.set(text)
        except (tk.TclError, AttributeError):
            pass

    def _planned_highlight(self) -> dict[str, str]:
        """Planned commit days {YYYY-MM-DD: note} for the embedded graph.

        Same mapping as the "Preview on graph" button but silent: invalid
        input simply yields no highlight instead of popups. Days on/before
        the picked repo's last commit are dropped (unavailable).
        """
        from datetime import date as _date
        from datetime import datetime as _dt

        try:
            count = self._selected_count()
        except Exception:
            return {}
        if count <= 0 or self.date_mode_var is None:
            return {}
        note = f"{count} planned commit(s)"
        try:
            mode = self.date_mode_var.get()
        except (tk.TclError, AttributeError):
            return {}
        result: dict[str, str] = {}
        if mode == "custom":
            try:
                day = (self.custom_date_var.get().strip() if self.custom_date_var else "")
                _dt.strptime(day, "%Y-%m-%d")
            except (ValueError, AttributeError):
                return {}
            result = {day: note}
        elif mode == "range":
            try:
                start = (self.range_start_date_var.get().strip() if self.range_start_date_var else "")
                end = (self.range_end_date_var.get().strip() if self.range_end_date_var else "")
                d0 = _dt.strptime(start, "%Y-%m-%d").date()
                d1 = _dt.strptime(end, "%Y-%m-%d").date()
            except (ValueError, AttributeError):
                return {}
            if d1 < d0:
                return {}
            day_d = d0
            while day_d <= d1:
                result[day_d.isoformat()] = note
                day_d += timedelta(days=1)
        else:
            result = {_dt.now().strftime("%Y-%m-%d"): note}
        try:
            if self.last_commit_iso:
                cut = _date.fromisoformat(str(self.last_commit_iso)[:10])
                result = {day: text for day, text in result.items() if _date.fromisoformat(day) >= cut}
        except (ValueError, AttributeError):
            pass
        return result

    def _schedule_graph_refresh(self) -> None:
        """Debounced reload of the embedded contribution graph."""
        if getattr(self, "graph", None) is None:
            return
        try:
            if self._graph_job is not None:
                self.after_cancel(self._graph_job)
        except (tk.TclError, ValueError, AttributeError):
            pass
        self._graph_job = None
        try:
            self._graph_job = self.after(250, self._refresh_graph)
        except tk.TclError:
            pass

    def _refresh_graph(self) -> None:
        """Reload the embedded graph for the picked repo + planned days."""
        self._graph_job = None
        graph = getattr(self, "graph", None)
        if graph is None:
            return
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        paths: list = []
        cutoff: Optional[str] = None
        if self.repo_options:
            # The table always aggregates every repository; the picked repo
            # only sets the cutoff for the shade overlay.
            none_opt = self.repo_options[0]
            paths = list(none_opt.get("all_paths") or
                         [c.get("path") for c in self.repo_options if c.get("path")])
            opt = self.repo_options[self._repo_index]
            if opt.get("path"):
                cutoff = opt.get("last_commit_iso")
        if getattr(self, "graph_frame", None) is not None:
            try:
                if not self.repo_options:
                    title = "Contributions"
                else:
                    picked = self.repo_options[self._repo_index]
                    title = (f"Contributions — {picked.get('name')}" if picked.get("path")
                             else "Contributions — all repositories")
                self.graph_frame.configure(text=title)
            except (tk.TclError, AttributeError):
                pass
        try:
            graph.set_data(paths, self.graph_author or None, self._planned_highlight(), cutoff)
        except Exception:
            pass

    def _on_key(self, key: str) -> None:
        """Handle keypad button press."""
        current = self.value_var.get()

        if key == "C":  # Clear
            self.value_var.set("0")
        elif key == "⌫":  # Backspace
            if len(current) > 1:
                self.value_var.set(current[:-1])
            else:
                self.value_var.set("0")
        else:  # Digit
            if current == "0":
                # Block standalone 0 when minvalue >0 (e.g., min=1)
                if key == "0" and self.minvalue > 0:
                    return
                if int(key) <= self.maxvalue:
                    self.value_var.set(key)
            else:
                new_val = current + key
                if int(new_val) <= self.maxvalue:
                    self.value_var.set(new_val)

    def _on_ok(self) -> None:
        """Handle OK button."""
        # NONE is for browsing only — a real repository is needed to move.
        if self.repo_options and not (self.selected_repo or {}).get("path"):
            messagebox.showinfo("Select repository", "Please select a repository from the list first.", parent=self)
            return
        # Validate number first
        try:
            value = int(self.value_var.get())
            if not (self.minvalue <= value <= self.maxvalue):
                messagebox.showerror("Invalid Input", f"Please enter a number between {self.minvalue} and {self.maxvalue}", parent=self)
                return
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number", parent=self)
            return

        # Validate date/time if shown
        if self.show_date_options and self.date_mode_var is not None:
            mode = self.date_mode_var.get()
            self.date_mode = mode
            if mode == "range":
                start_str = self.range_start_date_var.get().strip() if self.range_start_date_var else ""
                end_str = self.range_end_date_var.get().strip() if self.range_end_date_var else ""
                try:
                    start_iso = build_custom_iso(start_str, "00:00:00")
                    end_iso = build_custom_iso(end_str, "23:59:59")
                except ValueError as exc:
                    messagebox.showerror("Invalid date range", str(exc), parent=self)
                    return
                if start_iso > end_iso:
                    messagebox.showerror(
                        "Invalid date range",
                        f"Start date must be before (or equal to) end date.\n\nFrom: {start_str}\nTo: {end_str}",
                        parent=self,
                    )
                    return
                # Must be after last commit (check start of range)
                if not is_after_last_commit(start_iso, self.last_commit_iso):
                    messagebox.showerror(
                        "Invalid date range",
                        f"Range start must be after the last commit on base.\n\n"
                        f"Last commit: {self.last_commit_iso or self.last_commit_info or 'N/A'}\n"
                        f"Your range: {start_str} to {end_str}\n\n"
                        f"Please choose a later range.",
                        parent=self,
                    )
                    return
                if is_future(end_iso):
                    if not messagebox.askyesno(
                        "Future commit warning",
                        f"Warning: This range ends in the future!\n\nSelected range: {start_str} to {end_str}\nDo you want to continue?",
                        parent=self,
                    ):
                        return
                # Capacity warnings against daily min/max limits (protect the move)
                cap = self._range_capacity()
                if cap is not None:
                    days, lo_fit, hi_fit = cap
                    if value > hi_fit:
                        messagebox.showerror(
                            "Too many commits for this range",
                            f"Warning: {value} commits don't fit in {days} day(s) "
                            f"with max {self.max_commits_per_day}/day (capacity {hi_fit}).\n\n"
                            f"Extend the range, select fewer commits, or raise "
                            f"'Max commits per day' in Settings.",
                            parent=self,
                        )
                        return
                    if value < lo_fit:
                        if not messagebox.askyesno(
                            "Fewer commits than minimum",
                            f"Warning: {value} commits is below the fit for {days} day(s) "
                            f"with min {self.min_commits_per_day}/day (minimum {lo_fit}).\n\n"
                            f"Some days will end up below the minimum. Do you want to continue?",
                            parent=self,
                        ):
                            return
                self.range_start_iso = start_iso
                self.range_end_iso = end_iso
                self.custom_iso = None
                self.custom_start_iso = None
                self.custom_end_iso = None
            elif mode == "custom":
                date_str = self.custom_date_var.get().strip() if self.custom_date_var else ""
                from_str = self.custom_time_from_var.get().strip() if self.custom_time_from_var else ""
                to_str = self.custom_time_to_var.get().strip() if self.custom_time_to_var else ""
                try:
                    from_hms = self._normalize_time(from_str)
                    to_hms = self._normalize_time(to_str)
                    start_iso = build_custom_iso(date_str, from_hms)
                    end_iso = build_custom_iso(date_str, to_hms)
                except ValueError as exc:
                    messagebox.showerror("Invalid date", str(exc), parent=self)
                    return
                if start_iso > end_iso:
                    messagebox.showerror(
                        "Invalid time range",
                        f"Start time must be before (or equal to) end time.\n\nFrom: {from_str}\nTo: {to_str}",
                        parent=self,
                    )
                    return
                # Must be after last commit (check start of window)
                if not is_after_last_commit(start_iso, self.last_commit_iso):
                    messagebox.showerror(
                        "Invalid date",
                        f"Custom date must be after the last commit on base.\n\n"
                        f"Last commit: {self.last_commit_iso or self.last_commit_info or 'N/A'}\n"
                        f"Your choice: {date_str} {from_str}–{to_str}\n\n"
                        f"Please choose a later date.",
                        parent=self,
                    )
                    return
                if is_future(end_iso):
                    if not messagebox.askyesno(
                        "Future commit warning",
                        f"Warning: This time window ends in the future!\n\nSelected: {date_str} {from_str}–{to_str}\nDo you want to continue?",
                        parent=self,
                    ):
                        return
                self.custom_start_iso = start_iso
                self.custom_end_iso = end_iso
                self.custom_iso = start_iso  # backward compat: single-timestamp consumers use window start
                self.range_start_iso = None
                self.range_end_iso = None
            else:
                # Current date/time may also be future if system clock is off; check
                cur_iso = build_custom_iso(now_date_str(), now_time_str())
                if is_future(cur_iso):
                    # Still warn for current mode if somehow future
                    if not messagebox.askyesno(
                        "Future commit warning",
                        f"Warning: System current time is in the future ({cur_iso}). Do you want to create the commit with this time?",
                        parent=self,
                    ):
                        return
                self.custom_iso = None
                self.custom_start_iso = None
                self.custom_end_iso = None
                self.range_start_iso = None
                self.range_end_iso = None
        else:
            self.date_mode = "current"
            self.custom_iso = None
            self.custom_start_iso = None
            self.custom_end_iso = None
            self.range_start_iso = None
            self.range_end_iso = None

        self.result = value
        if self.repo_options:
            self.selected_repo = self.repo_options[self._repo_index]
        self.destroy()

    @staticmethod
    def _normalize_time(value: str) -> str:
        """Normalize HH:MM (or HH:MM:SS) to HH:MM:SS, validating 24h ranges."""
        import re as _re

        value = value.strip()
        m = _re.match(r"^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?$", value)
        if not m:
            raise ValueError(f"Invalid time '{value}'. Expected HH:MM (00:00 to 23:59)")
        hh, mm, ss = m.group(1), m.group(2), m.group(3) or "00"
        return f"{hh}:{mm}:{ss}"

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = None
        self.custom_iso = None
        self.custom_start_iso = None
        self.custom_end_iso = None
        self.range_start_iso = None
        self.range_end_iso = None
        self.destroy()
