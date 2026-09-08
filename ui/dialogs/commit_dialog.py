"""Commit dialog for message and add scope selection."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from utils.time_utils import build_custom_iso, is_future, now_date_str, now_time_str


class CommitDialog(tk.Toplevel):
    """Dialog for commit message and add options."""

    def __init__(self, parent: tk.Tk, repo_name: str, theme_mode: str = "light") -> None:
        super().__init__(parent)
        self.title(f"Make a Commit - {repo_name}")
        self.resizable(False, False)
        self.result: Optional[tuple[str, str, str, str, Optional[str]]] = None
        self.theme_mode = theme_mode
        self.date_mode: str = "current"
        self.custom_iso: Optional[str] = None

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Commit message:", font=("Helvetica", 10, "bold"), style="Dialog.TLabel")
        self.message_text = tk.Text(self, width=70, height=8, wrap=tk.WORD, font=("Helvetica", 10), bg="#1e2228" if theme_mode == "dark" else "#ffffff", fg="#e8e8e8" if theme_mode == "dark" else "#000000", insertbackground="#e8e8e8" if theme_mode == "dark" else "#000000")
        self.message_text.pack(padx=20, pady=(4, 10), fill=tk.BOTH)

        self.add_mode = tk.StringVar(value="all")
        add_frame = ttk.LabelFrame(self, text="Add scope", padding=10, style="Dialog.TLabelframe")
        add_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        ttk.Radiobutton(add_frame, text="All changes (tracked + untracked)", variable=self.add_mode, value="all").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(add_frame, text="Tracked changes only", variable=self.add_mode, value="tracked").pack(anchor=tk.W, pady=2)

        specific_frame = ttk.Frame(add_frame, style="Dialog.TFrame")
        specific_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Radiobutton(specific_frame, text="Specific paths:", variable=self.add_mode, value="paths").pack(side=tk.LEFT, anchor=tk.N)
        self.pathspec_var = tk.StringVar()
        self.pathspec_entry = ttk.Entry(specific_frame, textvariable=self.pathspec_var, width=48, style="Dialog.TEntry")
        self.pathspec_entry.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        # Date/time selection
        date_frame = ttk.LabelFrame(self, text="Commit date/time", padding=10, style="Dialog.TLabelframe")
        date_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        self.date_mode_var = tk.StringVar(value="current")
        ttk.Radiobutton(date_frame, text="Current date and time", variable=self.date_mode_var, value="current", command=self._on_date_mode_change).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(date_frame, text="Custom date and time", variable=self.date_mode_var, value="custom", command=self._on_date_mode_change).pack(anchor=tk.W, pady=2)
        custom_row = ttk.Frame(date_frame, style="Dialog.TFrame")
        custom_row.pack(fill=tk.X, pady=(6, 0))
        self.custom_date_var = tk.StringVar(value=now_date_str())
        self.custom_time_var = tk.StringVar(value=now_time_str())
        ttk.Label(custom_row, text="Date:", style="Dialog.TLabel").pack(side=tk.LEFT)
        self.custom_date_entry = ttk.Entry(custom_row, textvariable=self.custom_date_var, width=14, style="Dialog.TEntry")
        self.custom_date_entry.pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(custom_row, text="Time:", style="Dialog.TLabel").pack(side=tk.LEFT)
        self.custom_time_entry = ttk.Entry(custom_row, textvariable=self.custom_time_var, width=12, style="Dialog.TEntry")
        self.custom_time_entry.pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(date_frame, text="Format: YYYY-MM-DD and HH:MM:SS", font=("Helvetica", 8, "italic"), style="Dialog.TLabel").pack(anchor=tk.W, pady=(4, 0))
        self._set_custom_state(tk.DISABLED)

        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Commit", command=self._on_ok, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)

        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _set_custom_state(self, state: str) -> None:
        try:
            self.custom_date_entry.configure(state=state)
            self.custom_time_entry.configure(state=state)
        except tk.TclError:
            pass

    def _on_date_mode_change(self) -> None:
        mode = self.date_mode_var.get()
        if mode == "custom":
            self._set_custom_state(tk.NORMAL)
            try:
                self.custom_date_entry.focus_set()
            except tk.TclError:
                pass
        else:
            self._set_custom_state(tk.DISABLED)

    def _on_ok(self) -> None:
        message = self.message_text.get("1.0", tk.END).strip()
        if not message:
            messagebox.showerror("Commit message required", "Please enter a commit message.", parent=self)
            return

        add_mode = self.add_mode.get()
        pathspec = self.pathspec_var.get().strip()
        if add_mode == "paths" and not pathspec:
            messagebox.showerror("Pathspec required", "Please specify one or more file paths for the commit.", parent=self)
            return

        mode = self.date_mode_var.get()
        self.date_mode = mode
        if mode == "custom":
            date_str = self.custom_date_var.get().strip()
            time_str = self.custom_time_var.get().strip()
            try:
                custom_iso = build_custom_iso(date_str, time_str)
            except ValueError as exc:
                messagebox.showerror("Invalid date/time", str(exc), parent=self)
                return
            if is_future(custom_iso):
                if not messagebox.askyesno(
                    "Future commit warning",
                    f"هشدار: این کامیت برای آینده است!\n\nتاریخ انتخابی: {custom_iso}\nزمان فعلی: {now_date_str()} {now_time_str()}\n\nآیا می‌خواهید با این تاریخ آینده کامیت انجام شود؟",
                    parent=self,
                ):
                    return
            self.custom_iso = custom_iso
        else:
            self.custom_iso = None
            self.date_mode = "current"

        self.result = (message, add_mode, pathspec, self.date_mode, self.custom_iso)
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.custom_iso = None
        self.destroy()
