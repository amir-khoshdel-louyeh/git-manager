"""Settings dialog for application preferences."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional


class SettingsDialog(tk.Toplevel):
    """Dialog for changing application settings."""

    def __init__(
        self,
        parent: tk.Tk,
        base_directory: str,
        auto_switch: bool,
        theme_mode: str,
        auto_refresh: bool,
        refresh_interval: int,
        output_font_size: int,
        table_font_size: int,
        button_font_size: int,
        work_start_hour: str = "09:00",
        work_end_hour: str = "18:00",
        min_commits_per_day: int = 1,
        max_commits_per_day: int = 10,
        busy_workdays: bool = False,
    ) -> None:
        super().__init__(parent)
        self.title("Settings")
        self.resizable(True, True)
        self.result: Optional[tuple[str, bool, str, bool, int, int, int, int, str, str, int, int, bool]] = None
        self.theme_mode = theme_mode

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        self.transient(parent)
        self.grab_set()

        repo_frame = ttk.LabelFrame(self, text="Repository settings", style="Dialog.TLabelframe")
        repo_frame.pack(fill=tk.X, padx=20, pady=(16, 8))
        self.base_var = tk.StringVar(value=base_directory)
        entry_frame = ttk.Frame(repo_frame)
        entry_frame.pack(fill=tk.X, padx=12, pady=12)
        ttk.Entry(entry_frame, textvariable=self.base_var, width=48).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(entry_frame, text="Browse", command=self._browse_base_dir).pack(side=tk.LEFT, padx=(8, 0))

        startup_frame = ttk.LabelFrame(self, text="Startup behavior", style="Dialog.TLabelframe")
        startup_frame.pack(fill=tk.X, padx=20, pady=8)
        self.auto_switch_var = tk.BooleanVar(value=auto_switch)
        ttk.Checkbutton(startup_frame, text="Auto switch to local_commit on startup", variable=self.auto_switch_var, style="Dialog.TCheckbutton").pack(anchor=tk.W, padx=12, pady=12)

        refresh_frame = ttk.LabelFrame(self, text="Refresh settings", style="Dialog.TLabelframe")
        refresh_frame.pack(fill=tk.X, padx=20, pady=8)
        self.auto_refresh_var = tk.BooleanVar(value=auto_refresh)
        ttk.Checkbutton(refresh_frame, text="Auto refresh repositories", variable=self.auto_refresh_var, style="Dialog.TCheckbutton").pack(anchor=tk.W, padx=12, pady=(12, 8))

        interval_frame = ttk.Frame(refresh_frame, style="Dialog.TFrame")
        interval_frame.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Label(interval_frame, text="Refresh every", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT)
        self.refresh_interval_var = tk.StringVar(value=str(refresh_interval))
        ttk.Entry(interval_frame, textvariable=self.refresh_interval_var, width=6, style="Dialog.TEntry").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(interval_frame, text="minute(s)", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT, padx=(8, 0))

        appearance_frame = ttk.LabelFrame(self, text="Appearance", style="Dialog.TLabelframe")
        appearance_frame.pack(fill=tk.X, padx=20, pady=8)
        self.theme_mode = tk.StringVar(value=theme_mode)
        theme_frame = ttk.Frame(appearance_frame, style="Dialog.TFrame")
        theme_frame.pack(fill=tk.X, padx=12, pady=12)
        ttk.Radiobutton(theme_frame, text="Light", variable=self.theme_mode, value="light", style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(theme_frame, text="Dark", variable=self.theme_mode, value="dark", style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=4)

        zoom_frame = ttk.LabelFrame(self, text="Zoom", style="Dialog.TLabelframe")
        zoom_frame.pack(fill=tk.X, padx=20, pady=8)
        self.output_font_size_var = tk.StringVar(value=str(output_font_size))
        self.table_font_size_var = tk.StringVar(value=str(table_font_size))
        self.button_font_size_var = tk.StringVar(value=str(button_font_size))

        terminal_zoom_row = ttk.Frame(zoom_frame, style="Dialog.TFrame")
        terminal_zoom_row.pack(fill=tk.X, padx=12, pady=(8, 4))
        ttk.Label(terminal_zoom_row, text="Terminal font size:", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT)
        ttk.Spinbox(
            terminal_zoom_row,
            from_=8,
            to=24,
            increment=1,
            textvariable=self.output_font_size_var,
            width=6,
            justify=tk.CENTER,
            style="Dialog.TSpinbox",
        ).pack(side=tk.RIGHT)

        table_zoom_row = ttk.Frame(zoom_frame, style="Dialog.TFrame")
        table_zoom_row.pack(fill=tk.X, padx=12, pady=(4, 4))
        ttk.Label(table_zoom_row, text="Repository table font size:", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT)
        ttk.Spinbox(
            table_zoom_row,
            from_=8,
            to=24,
            increment=1,
            textvariable=self.table_font_size_var,
            width=6,
            justify=tk.CENTER,
            style="Dialog.TSpinbox",
        ).pack(side=tk.RIGHT)

        button_zoom_row = ttk.Frame(zoom_frame, style="Dialog.TFrame")
        button_zoom_row.pack(fill=tk.X, padx=12, pady=(4, 12))
        ttk.Label(button_zoom_row, text="Button font size:", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT)
        ttk.Spinbox(
            button_zoom_row,
            from_=8,
            to=24,
            increment=1,
            textvariable=self.button_font_size_var,
            width=6,
            justify=tk.CENTER,
            style="Dialog.TSpinbox",
        ).pack(side=tk.RIGHT)

        working_frame = ttk.LabelFrame(self, text="Working hours", style="Dialog.TLabelframe")
        working_frame.pack(fill=tk.X, padx=20, pady=8)
        self.work_start_var = tk.StringVar(value=work_start_hour)
        self.work_end_var = tk.StringVar(value=work_end_hour)

        working_row = ttk.Frame(working_frame, style="Dialog.TFrame")
        working_row.pack(fill=tk.X, padx=12, pady=12)
        ttk.Label(working_row, text="From (HH:MM):", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT)
        ttk.Entry(working_row, textvariable=self.work_start_var, width=8, style="Dialog.TEntry", justify=tk.CENTER).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(working_row, text="To (HH:MM):", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT, padx=(16, 0))
        ttk.Entry(working_row, textvariable=self.work_end_var, width=8, style="Dialog.TEntry", justify=tk.CENTER).pack(side=tk.LEFT, padx=(8, 0))

        distrib_frame = ttk.LabelFrame(self, text="Daily distribution (date range mode)", style="Dialog.TLabelframe")
        distrib_frame.pack(fill=tk.X, padx=20, pady=8)
        self.min_per_day_var = tk.StringVar(value=str(min_commits_per_day))
        self.max_per_day_var = tk.StringVar(value=str(max_commits_per_day))
        self.busy_workdays_var = tk.BooleanVar(value=busy_workdays)

        minmax_row = ttk.Frame(distrib_frame, style="Dialog.TFrame")
        minmax_row.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(minmax_row, text="Min commits per day:", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT)
        ttk.Entry(minmax_row, textvariable=self.min_per_day_var, width=6, style="Dialog.TEntry", justify=tk.CENTER).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(minmax_row, text="Max commits per day:", font=("Helvetica", 10), style="Dialog.TLabel").pack(side=tk.LEFT, padx=(16, 0))
        ttk.Entry(minmax_row, textvariable=self.max_per_day_var, width=6, style="Dialog.TEntry", justify=tk.CENTER).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Checkbutton(
            distrib_frame,
            text="Busy workdays (Mon–Fri get more, Sat–Sun fewer)",
            variable=self.busy_workdays_var,
            style="Dialog.TCheckbutton",
        ).pack(anchor=tk.W, padx=12, pady=(4, 12))

        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(pady=16)
        ttk.Button(button_frame, text="Save", command=self._on_ok, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)

        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _browse_base_dir(self) -> None:
        new_dir = filedialog.askdirectory(parent=self, title="Select Base Directory", initialdir=self.base_var.get())
        if new_dir:
            self.base_var.set(new_dir)

    def _on_ok(self) -> None:
        base = self.base_var.get().strip()
        if not base:
            messagebox.showerror("Base directory required", "Please choose a base directory.", parent=self)
            return

        interval = 5
        try:
            interval = max(1, int(self.refresh_interval_var.get().strip()))
        except ValueError:
            messagebox.showerror("Invalid interval", "Please enter a valid number of minutes.", parent=self)
            return

        output_font_size = 10
        try:
            output_font_size = max(8, min(24, int(self.output_font_size_var.get().strip())))
        except ValueError:
            messagebox.showerror("Invalid font size", "Please enter a valid terminal font size.", parent=self)
            return

        table_font_size = 10
        try:
            table_font_size = max(8, min(24, int(self.table_font_size_var.get().strip())))
        except ValueError:
            messagebox.showerror("Invalid font size", "Please enter a valid repository table font size.", parent=self)
            return

        button_font_size = 10
        try:
            button_font_size = max(8, min(24, int(self.button_font_size_var.get().strip())))
        except ValueError:
            messagebox.showerror("Invalid font size", "Please enter a valid button font size.", parent=self)
            return

        work_start = self.work_start_var.get().strip()
        work_end = self.work_end_var.get().strip()
        if not self._is_valid_hour(work_start):
            messagebox.showerror("Invalid working hours", "Start hour must be HH:MM (00:00 to 23:59).", parent=self)
            return
        if not self._is_valid_hour(work_end):
            messagebox.showerror("Invalid working hours", "End hour must be HH:MM (00:00 to 23:59).", parent=self)
            return

        try:
            min_per_day = max(0, int(self.min_per_day_var.get().strip()))
        except ValueError:
            messagebox.showerror("Invalid daily limits", "Min commits per day must be a number (0 or more).", parent=self)
            return
        try:
            max_per_day = max(1, int(self.max_per_day_var.get().strip()))
        except ValueError:
            messagebox.showerror("Invalid daily limits", "Max commits per day must be a number (1 or more).", parent=self)
            return
        if min_per_day > max_per_day:
            messagebox.showerror("Invalid daily limits", "Min commits per day must not exceed max.", parent=self)
            return

        self.result = (
            base,
            self.auto_switch_var.get(),
            self.theme_mode.get(),
            self.auto_refresh_var.get(),
            interval,
            output_font_size,
            table_font_size,
            button_font_size,
            work_start,
            work_end,
            min_per_day,
            max_per_day,
            self.busy_workdays_var.get(),
        )
        self.destroy()

    @staticmethod
    def _is_valid_hour(value: str) -> bool:
        import re as _re

        if not _re.match(r"^([01]\d|2[0-3]):[0-5]\d$", value):
            return False
        return True

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
