"""Numeric keypad dialog for commit count selection with date/time options."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from utils.time_utils import build_custom_iso, is_after_last_commit, now_date_str, now_time_str


class NumericKeypadDialog(tk.Toplevel):
    """Custom dialog with numeric keypad for entering number of commits.

    When ``show_date_options`` is True (used for Move Commits), the dialog also
    shows:
    - Last commit info for better experience
    - Two radio options: "Current date and time" (default) vs "Custom date and time"
    - Date (YYYY-MM-DD) and Time (HH:MM:SS) entry fields when custom is chosen
    - Validation that custom datetime is after last commit on base
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
        self.resizable(False, False)
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

        # Prompt label
        ttk.Label(self, text=prompt, font=("Helvetica", 11), justify=tk.CENTER, style="Dialog.TLabel").pack(pady=10, padx=20)

        # Display value
        self.value_var = tk.StringVar(value="0")
        entry_bg = "#1e2228" if theme_mode == "dark" else "#f1f5f9"
        entry_fg = "#e8e8e8" if theme_mode == "dark" else "#111827"
        display = tk.Entry(
            self,
            textvariable=self.value_var,
            font=("Helvetica", 14, "bold"),
            width=15,
            justify=tk.CENTER,
            state="readonly",
            bg=entry_bg,
            fg=entry_fg,
            readonlybackground=entry_bg,
            disabledforeground=entry_fg,
            relief=tk.SOLID,
            bd=1,
        )
        display.pack(pady=10, padx=20)

        # Numeric keypad
        keypad_frame = ttk.Frame(self, style="Dialog.TFrame")
        keypad_frame.pack(pady=10, padx=20)

        buttons = [
            ["7", "8", "9"],
            ["4", "5", "6"],
            ["1", "2", "3"],
            ["0", "C", "⌫"],
        ]

        for row in buttons:
            row_frame = ttk.Frame(keypad_frame)
            row_frame.pack()
            for btn_text in row:
                btn = ttk.Button(row_frame, text=btn_text, width=5, command=lambda t=btn_text: self._on_key(t))
                btn.pack(side=tk.LEFT, padx=2, pady=2)

        # --- Date/time options (only for move flow) ---
        if self.show_date_options:
            separator = ttk.Separator(self, orient=tk.HORIZONTAL)
            separator.pack(fill=tk.X, padx=20, pady=(8, 0))

            # Last commit info for better experience
            if self.last_commit_info:
                info_frame = ttk.LabelFrame(self, text="Last commit on base", padding=8, style="Dialog.TLabelframe")
                info_frame.pack(fill=tk.X, padx=20, pady=(8, 0))
                # Truncate for display but keep full in tooltip-ish
                info_label = ttk.Label(
                    info_frame,
                    text=self.last_commit_info,
                    font=("Courier", 8),
                    wraplength=420,
                    justify=tk.LEFT,
                    style="Dialog.TLabel",
                )
                info_label.pack(anchor=tk.W, fill=tk.X)
                ttk.Label(
                    info_frame,
                    text="Custom date/time must be after this commit.",
                    font=("Helvetica", 8, "italic"),
                    style="Dialog.TLabel",
                ).pack(anchor=tk.W, pady=(4, 0))
            else:
                ttk.Label(
                    self,
                    text="No prior commits on base (first commit). Any date/time is allowed.",
                    font=("Helvetica", 8, "italic"),
                    style="Dialog.TLabel",
                    wraplength=420,
                ).pack(pady=(8, 0), padx=20)

            date_frame = ttk.LabelFrame(self, text="Commit date/time", padding=10, style="Dialog.TLabelframe")
            date_frame.pack(fill=tk.X, padx=20, pady=10)

            self.date_mode_var = tk.StringVar(value="current")
            ttk.Radiobutton(
                date_frame,
                text="Current date and time (default)",
                variable=self.date_mode_var,
                value="current",
                style="Dialog.TRadiobutton",
                command=self._on_date_mode_change,
            ).pack(anchor=tk.W, pady=2)
            ttk.Radiobutton(
                date_frame,
                text="Custom date and time",
                variable=self.date_mode_var,
                value="custom",
                style="Dialog.TRadiobutton",
                command=self._on_date_mode_change,
            ).pack(anchor=tk.W, pady=2)

            custom_frame = ttk.Frame(date_frame, style="Dialog.TFrame")
            custom_frame.pack(fill=tk.X, pady=(8, 0))
            self._custom_frame = custom_frame

            self.custom_date_var = tk.StringVar(value=now_date_str())
            self.custom_time_var = tk.StringVar(value=now_time_str())

            # Date row
            date_row = ttk.Frame(custom_frame, style="Dialog.TFrame")
            date_row.pack(fill=tk.X, pady=2)
            ttk.Label(date_row, text="Date (YYYY-MM-DD):", font=("Helvetica", 9), style="Dialog.TLabel", width=18).pack(side=tk.LEFT)
            self.custom_date_entry = ttk.Entry(date_row, textvariable=self.custom_date_var, width=14, style="Dialog.TEntry")
            self.custom_date_entry.pack(side=tk.LEFT, padx=(8, 0))

            # Time row
            time_row = ttk.Frame(custom_frame, style="Dialog.TFrame")
            time_row.pack(fill=tk.X, pady=2)
            ttk.Label(time_row, text="Time (HH:MM:SS):", font=("Helvetica", 9), style="Dialog.TLabel", width=18).pack(side=tk.LEFT)
            self.custom_time_entry = ttk.Entry(time_row, textvariable=self.custom_time_var, width=14, style="Dialog.TEntry")
            self.custom_time_entry.pack(side=tk.LEFT, padx=(8, 0))

            # Initially disabled because current is default
            self._set_custom_entries_state(tk.DISABLED)

        # OK and Cancel buttons
        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="OK", command=self._on_ok, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)

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

        # Center on parent
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
