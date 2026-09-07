"""Numeric keypad dialog for commit count selection with date/time options."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from utils.time_utils import build_custom_iso, is_after_last_commit, now_date_str, now_time_str


class NumericKeypadDialog(tk.Toplevel):
    """Custom dialog with numeric keypad for entering number of commits.

    When ``show_date_options`` is True (used for Move Commits), the dialog also
    shows a horizontally-split layout:
    - Left column: number display + large keypad (bigger window)
    - Right column: last commit info + date/time radios + entries
    The window is intentionally larger and uses a horizontal grid.
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
    ) -> None:
        super().__init__(parent)
        self.title(title)
        # Bigger window: allow resizing horizontally, but keep minsize large
        self.minsize(880, 520)
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
        self.date_mode_var: Optional[tk.StringVar] = None
        self.custom_date_var: Optional[tk.StringVar] = None
        self.custom_time_var: Optional[tk.StringVar] = None

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Prompt label (spans full width, top)
        ttk.Label(self, text=prompt, font=("Helvetica", 12, "bold"), justify=tk.CENTER, style="Dialog.TLabel", wraplength=820).pack(pady=(16, 10), padx=20, fill=tk.X)

        # ===================== HORIZONTAL GRID CONTENT =====================
        content = ttk.Frame(self, style="Dialog.TFrame")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        if self.show_date_options:
            # Horizontal split: left = number / keypad, right = date options
            content.columnconfigure(0, weight=1, uniform="col")
            content.columnconfigure(1, weight=1, uniform="col")
            content.rowconfigure(0, weight=1)

            # ----- LEFT COLUMN -----
            left = ttk.LabelFrame(content, text="Number of commits", padding=14, style="Dialog.TLabelframe")
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=5)
            left.columnconfigure(0, weight=1)

            # Display value - bigger
            self.value_var = tk.StringVar(value="0")
            entry_bg = "#1e2228" if theme_mode == "dark" else "#f1f5f9"
            entry_fg = "#e8e8e8" if theme_mode == "dark" else "#111827"
            display = tk.Entry(
                left,
                textvariable=self.value_var,
                font=("Helvetica", 18, "bold"),
                width=18,
                justify=tk.CENTER,
                state="readonly",
                bg=entry_bg,
                fg=entry_fg,
                readonlybackground=entry_bg,
                disabledforeground=entry_fg,
                relief=tk.SOLID,
                bd=1,
            )
            display.grid(row=0, column=0, pady=(8, 12), padx=10, sticky="ew")

            # Numeric keypad - bigger buttons, grid layout
            keypad_frame = ttk.Frame(left, style="Dialog.TFrame")
            keypad_frame.grid(row=1, column=0, pady=6, padx=10)

            buttons = [
                ["7", "8", "9"],
                ["4", "5", "6"],
                ["1", "2", "3"],
                ["0", "C", "⌫"],
            ]

            for r, row in enumerate(buttons):
                row_frame = ttk.Frame(keypad_frame, style="Dialog.TFrame")
                row_frame.grid(row=r, column=0, pady=3)
                for c, btn_text in enumerate(row):
                    btn = ttk.Button(row_frame, text=btn_text, width=7, command=lambda t=btn_text: self._on_key(t))
                    btn.grid(row=0, column=c, padx=5, pady=3, ipadx=4, ipady=8)
                    # Make buttons more tactile: larger padding

            # Hint label under keypad
            ttk.Label(left, text="Use keypad or keyboard (0-9, Backspace, C)", font=("Helvetica", 8, "italic"), style="Dialog.TLabel").grid(row=2, column=0, pady=(10, 4))

            # ----- RIGHT COLUMN -----
            right = ttk.Frame(content, style="Dialog.TFrame")
            right.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=5)
            right.columnconfigure(0, weight=1)

            # Last commit info for better experience
            if self.last_commit_info:
                info_frame = ttk.LabelFrame(right, text="Last commit on base", padding=10, style="Dialog.TLabelframe")
                info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
                info_frame.columnconfigure(0, weight=1)
                info_label = ttk.Label(
                    info_frame,
                    text=self.last_commit_info,
                    font=("Courier", 9),
                    wraplength=380,
                    justify=tk.LEFT,
                    style="Dialog.TLabel",
                )
                info_label.grid(row=0, column=0, sticky="w")
                ttk.Label(
                    info_frame,
                    text="Custom date/time must be after this commit.",
                    font=("Helvetica", 8, "italic"),
                    style="Dialog.TLabel",
                ).grid(row=1, column=0, sticky="w", pady=(6, 0))
            else:
                ttk.Label(
                    right,
                    text="No prior commits on base (first commit). Any date/time is allowed.",
                    font=("Helvetica", 9, "italic"),
                    style="Dialog.TLabel",
                    wraplength=380,
                ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

            date_frame = ttk.LabelFrame(right, text="Commit date/time", padding=12, style="Dialog.TLabelframe")
            date_frame.grid(row=1, column=0, sticky="ew", pady=5)
            date_frame.columnconfigure(0, weight=1)

            self.date_mode_var = tk.StringVar(value="current")
            ttk.Radiobutton(
                date_frame,
                text="Current date and time (default)",
                variable=self.date_mode_var,
                value="current",
                style="Dialog.TRadiobutton",
                command=self._on_date_mode_change,
            ).grid(row=0, column=0, sticky="w", pady=3)
            ttk.Radiobutton(
                date_frame,
                text="Custom date and time",
                variable=self.date_mode_var,
                value="custom",
                style="Dialog.TRadiobutton",
                command=self._on_date_mode_change,
            ).grid(row=1, column=0, sticky="w", pady=3)

            custom_frame = ttk.Frame(date_frame, style="Dialog.TFrame")
            custom_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
            custom_frame.columnconfigure(1, weight=1)
            self._custom_frame = custom_frame

            self.custom_date_var = tk.StringVar(value=now_date_str())
            self.custom_time_var = tk.StringVar(value=now_time_str())

            # Date row - grid
            ttk.Label(custom_frame, text="Date (YYYY-MM-DD):", font=("Helvetica", 10), style="Dialog.TLabel").grid(row=0, column=0, sticky="w", pady=4, padx=(4, 8))
            self.custom_date_entry = ttk.Entry(custom_frame, textvariable=self.custom_date_var, width=20, style="Dialog.TEntry", font=("Helvetica", 10))
            self.custom_date_entry.grid(row=0, column=1, sticky="ew", pady=4, padx=(0, 4))

            # Time row - grid
            ttk.Label(custom_frame, text="Time (HH:MM:SS):", font=("Helvetica", 10), style="Dialog.TLabel").grid(row=1, column=0, sticky="w", pady=4, padx=(4, 8))
            self.custom_time_entry = ttk.Entry(custom_frame, textvariable=self.custom_time_var, width=20, style="Dialog.TEntry", font=("Helvetica", 10))
            self.custom_time_entry.grid(row=1, column=1, sticky="ew", pady=4, padx=(0, 4))

            # Helper hint
            ttk.Label(custom_frame, text="Example: 2026-09-03 and 14:30:00", font=("Helvetica", 8, "italic"), style="Dialog.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0), padx=4)

            # Initially disabled because current is default
            self._set_custom_entries_state(tk.DISABLED)

        else:
            # Simple mode: no date options, single centered column but still big
            content.columnconfigure(0, weight=1)
            content.rowconfigure(0, weight=1)

            single = ttk.LabelFrame(content, text="Select number", padding=16, style="Dialog.TLabelframe")
            single.grid(row=0, column=0, sticky="nsew", padx=40)
            single.columnconfigure(0, weight=1)

            self.value_var = tk.StringVar(value="0")
            entry_bg = "#1e2228" if theme_mode == "dark" else "#f1f5f9"
            entry_fg = "#e8e8e8" if theme_mode == "dark" else "#111827"
            display = tk.Entry(
                single,
                textvariable=self.value_var,
                font=("Helvetica", 18, "bold"),
                width=20,
                justify=tk.CENTER,
                state="readonly",
                bg=entry_bg,
                fg=entry_fg,
                readonlybackground=entry_bg,
                disabledforeground=entry_fg,
                relief=tk.SOLID,
                bd=1,
            )
            display.grid(row=0, column=0, pady=(8, 14), sticky="ew")

            keypad_frame = ttk.Frame(single, style="Dialog.TFrame")
            keypad_frame.grid(row=1, column=0, pady=6)

            buttons = [
                ["7", "8", "9"],
                ["4", "5", "6"],
                ["1", "2", "3"],
                ["0", "C", "⌫"],
            ]

            for r, row in enumerate(buttons):
                row_frame = ttk.Frame(keypad_frame, style="Dialog.TFrame")
                row_frame.grid(row=r, column=0, pady=3)
                for c, btn_text in enumerate(row):
                    btn = ttk.Button(row_frame, text=btn_text, width=8, command=lambda t=btn_text: self._on_key(t))
                    btn.grid(row=0, column=c, padx=5, pady=3, ipadx=4, ipady=10)

        # OK and Cancel buttons - bottom, centered, bigger
        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(pady=16, fill=tk.X)
        inner_btn = ttk.Frame(button_frame, style="Dialog.TFrame")
        inner_btn.pack(anchor=tk.CENTER)
        ok_btn = ttk.Button(inner_btn, text="OK", command=self._on_ok, style="Dialog.TButton", width=12)
        ok_btn.pack(side=tk.LEFT, padx=8, ipady=4)
        cancel_btn = ttk.Button(inner_btn, text="Cancel", command=self._on_cancel, style="Dialog.TButton", width=12)
        cancel_btn.pack(side=tk.LEFT, padx=8, ipady=4)

        # Bind keyboard events
        self.bind("<Key-0>", lambda e: self._on_key("0"))
        self.bind("<Key-1>", lambda e: self._on_key("1"))
        self.bind("<Key-2>", lambda e: self._on_key("2"))
        self.bind("<Key-3>", lambda e: self._on_key("3"))
        self.bind("<Key-4>", lambda e: self._on_key("4"))
        self.bind("<Key-5>", lambda e: self._on_key("5"))
        self.bind("<Key-6>", lambda e: self._on_key("6"))
        self.bind("<Key-7>", lambda e: self._on_key("7"))
        self.bind("<Key-8>", lambda e: self._on_key("8"))
        self.bind("<Key-9>", lambda e: self._on_key("9"))
        self.bind("<BackSpace>", lambda e: self._on_key("⌫"))
        self.bind("<Delete>", lambda e: self._on_key("C"))
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        # Center on parent and enforce bigger geometry
        self.update_idletasks()
        # Enforce larger size for move dialog
        if self.show_date_options:
            cur_w = self.winfo_width()
            cur_h = self.winfo_height()
            target_w = max(cur_w, 880)
            target_h = max(cur_h, 520)
            self.geometry(f"{target_w}x{target_h}")
            self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _set_custom_entries_state(self, state: str) -> None:
        if hasattr(self, "custom_date_entry"):
            self.custom_date_entry.configure(state=state)
            self.custom_time_entry.configure(state=state)

    def _on_date_mode_change(self) -> None:
        if self.date_mode_var is None:
            return
        mode = self.date_mode_var.get()
        if mode == "custom":
            self._set_custom_entries_state(tk.NORMAL)
            # Focus date entry for convenience
            try:
                self.custom_date_entry.focus_set()
            except tk.TclError:
                pass
        else:
            self._set_custom_entries_state(tk.DISABLED)

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
            if mode == "custom":
                date_str = self.custom_date_var.get().strip() if self.custom_date_var else ""
                time_str = self.custom_time_var.get().strip() if self.custom_time_var else ""
                try:
                    custom_iso = build_custom_iso(date_str, time_str)
                except ValueError as exc:
                    messagebox.showerror("Invalid date/time", str(exc), parent=self)
                    return
                # Must be after last commit
                if not is_after_last_commit(custom_iso, self.last_commit_iso):
                    messagebox.showerror(
                        "Invalid date/time",
                        f"Custom date/time must be after the last commit on base.\n\n"
                        f"Last commit: {self.last_commit_iso or self.last_commit_info or 'N/A'}\n"
                        f"Your choice: {custom_iso}\n\n"
                        f"Please choose a later date/time.",
                        parent=self,
                    )
                    return
                self.custom_iso = custom_iso
            else:
                self.custom_iso = None
        else:
            self.date_mode = "current"
            self.custom_iso = None

        self.result = value
        self.destroy()

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = None
        self.custom_iso = None
        self.destroy()
