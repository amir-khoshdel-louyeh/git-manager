#!/usr/bin/env python3
"""Standalone GUI for managing git repositories with proper OOP structure."""
from __future__ import annotations

import ctypes
import platform
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog, filedialog
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from git_operations import GitOperations, GitManagerError
from repo_state import RepoState
from branch_manager import BranchManager
from working_tree_manager import WorkingTreeManager
from git_config import GitConfig
from repo_scanner import RepoScanner
from settings_db import SettingsDB


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def now_iso() -> str:
    """Return current time in ISO 8601 format."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S%z")


def now_display() -> str:
    """Return current time in human-readable format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %z")


class NumericKeypadDialog(tk.Toplevel):
    """Custom dialog with numeric keypad for entering number of commits."""
    
    def __init__(self, parent: tk.Tk, title: str, prompt: str, minvalue: int = 1, maxvalue: int = 100, theme_mode: str = "light") -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[int] = None
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.theme_mode = theme_mode
        
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
        try:
            value = int(self.value_var.get())
            if self.minvalue <= value <= self.maxvalue:
                self.result = value
                self.destroy()
            else:
                messagebox.showerror("Invalid Input", f"Please enter a number between {self.minvalue} and {self.maxvalue}")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number")
    
    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = None
        self.destroy()


class CommitDialog(tk.Toplevel):
    """Dialog for commit message and add options."""

    def __init__(self, parent: tk.Tk, repo_name: str, theme_mode: str = "light") -> None:
        super().__init__(parent)
        self.title(f"Make a Commit - {repo_name}")
        self.resizable(False, False)
        self.result: Optional[tuple[str, str, str]] = None
        self.theme_mode = theme_mode

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

        self.result = (message, add_mode, pathspec)
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


class PreviewModeDialog(tk.Toplevel):
    """Dialog asking whether to preview pushed or unpushed commits."""

    def __init__(self, parent: tk.Tk, theme_mode: str = "light") -> None:
        super().__init__(parent)
        self.title("Preview Commits")
        self.resizable(False, False)
        self.result: Optional[str] = None
        self.theme_mode = theme_mode

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Which commits would you like to preview?", font=("Helvetica", 11, "bold"), wraplength=360, style="Dialog.TLabel").pack(padx=20, pady=(16, 8))

        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(padx=20, pady=(0, 16), fill=tk.X)

        ttk.Button(button_frame, text="Pushed commits", command=self._on_pushed, width=18, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Unpushed commits", command=self._on_unpushed, width=18, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)

        cancel_frame = ttk.Frame(self, style="Dialog.TFrame")
        cancel_frame.pack(padx=20, pady=(0, 16), fill=tk.X)
        ttk.Button(cancel_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton").pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda e: self._on_cancel())
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _on_pushed(self) -> None:
        self.result = "pushed"
        self.destroy()

    def _on_unpushed(self) -> None:
        self.result = "unpushed"
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


class ResetDialog(tk.Toplevel):
    """Dialog to select a reset target commit and reset type."""

    def __init__(self, parent: tk.Tk, repo_name: str, theme_mode: str = "light") -> None:
        super().__init__(parent)
        self.title(f"Reset {repo_name}")
        self.resizable(False, False)
        self.result: Optional[tuple[str, str]] = None
        self.theme_mode = theme_mode

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Reset target commit or ref:", font=("Helvetica", 10, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, padx=20, pady=(16, 4))
        self.target_var = tk.StringVar(value="")
        ttk.Entry(self, textvariable=self.target_var, width=56, style="Dialog.TEntry").pack(padx=20, pady=(0, 12), fill=tk.X)

        ttk.Label(self, text="Reset type:", font=("Helvetica", 10, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, padx=20, pady=(0, 4))
        self.reset_type = tk.StringVar(value="hard")
        types_frame = ttk.Frame(self, style="Dialog.TFrame")
        types_frame.pack(fill=tk.X, padx=20)
        ttk.Radiobutton(types_frame, text="Hard", variable=self.reset_type, value="hard", style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(types_frame, text="Mixed", variable=self.reset_type, value="mixed", style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(types_frame, text="Soft", variable=self.reset_type, value="soft", style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=4)

        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(pady=16)
        ttk.Button(button_frame, text="Reset", command=self._on_ok, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)

        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _on_ok(self) -> None:
        target = self.target_var.get().strip()
        if not target:
            messagebox.showerror("Target required", "Please enter a commit hash or ref to reset to.", parent=self)
            return

        self.result = (target, self.reset_type.get())
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


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
    ) -> None:
        super().__init__(parent)
        self.title("Settings")
        self.resizable(False, False)
        self.result: Optional[tuple[str, bool, str, bool, int, int, int, int]] = None
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

        self.result = (
            base,
            self.auto_switch_var.get(),
            self.theme_mode.get(),
            self.auto_refresh_var.get(),
            interval,
            output_font_size,
            table_font_size,
            button_font_size,
        )
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


# ============================================================================
# GUI APPLICATION
# ============================================================================
DEFAULT_BASE_DIR = Path.home() / "GitHub"


class GitManagerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Git Manager - Repository Management Tool")
        self.root.configure(bg="#f0f0f0")

        # Initialize settings database
        self.db = SettingsDB()
        saved_base = self.db.get_base_directory()
        initial_base = saved_base if saved_base else str(DEFAULT_BASE_DIR)
        self.auto_switch_to_local_commit = self.db.get_auto_switch_local_commit()
        self.auto_refresh_enabled = self.db.get_auto_refresh_enabled()
        self.refresh_interval = self.db.get_refresh_interval()
        self.theme_mode = self.db.get_theme_mode()

        self.base_var = tk.StringVar(value=initial_base)
        self.output_font_size = self.db.get_output_font_size()
        self.table_font_size = self.db.get_table_font_size()
        self.button_font_size = self.db.get_button_font_size()
        self.states: List[RepoState] = []
        self.auto_refresh_job: Optional[str] = None
        self.operation_in_progress = False

        self._build_layout()
        self.apply_theme(self.theme_mode)
        self.refresh_repos()
        if self.auto_switch_to_local_commit:
            self.switch_all_to_local_commit(skip_busy_check=True)
        self._update_auto_refresh()
        
        # Register cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _start_operation(self, description: str) -> bool:
        if self.operation_in_progress:
            messagebox.showerror(
                "Operation in progress",
                f"Another operation is already running. Please wait for it to finish before {description}.",
                parent=self.root,
            )
            return False
        self.operation_in_progress = True
        self.status_var.set(f"⏳ {description.capitalize()}... Please wait.")
        self.root.update_idletasks()
        return True

    def _end_operation(self) -> None:
        self.operation_in_progress = False
        self.status_var.set("✓ Ready")
        self.root.update_idletasks()

    def _confirm_exit_during_operation(self) -> bool:
        return messagebox.askyesno(
            "Operation in progress",
            "An operation is currently running. Do you want to exit anyway?\n"
            "This may interrupt the current task.",
            parent=self.root,
        )

    def apply_theme(self, mode: str) -> None:
        style = ttk.Style()
        if mode == "dark":
            bg = "#141619"
            frame_bg = "#1f242a"
            text_bg = "#181c21"
            fg = "#e4e6eb"
            button_bg = "#2c3138"
            button_active = "#3b4350"
            heading_bg = "#232a33"
            heading_fg = "#e8ebf0"
            entry_bg = "#1e2228"
            entry_fg = "#e8ebf0"
            status_fg = "#8ab4f8"
            tree_tag_has = "#2b3137"
            tree_tag_clean = "#1e2228"
            selected_bg = "#264a6c"
            selected_fg = "#ffffff"
        else:
            bg = "#eef2f6"
            frame_bg = "#f7f9fb"
            text_bg = "#fafbff"
            fg = "#1f2937"
            button_bg = "#e2e8f0"
            button_active = "#cbd5e1"
            heading_bg = "#e6eef6"
            heading_fg = "#111827"
            entry_bg = "#f1f5f9"
            entry_fg = "#111827"
            status_fg = "#2563eb"
            tree_tag_has = "#fdf2e9"
            tree_tag_clean = "#eef4fb"
            selected_bg = "#dbeafe"
            selected_fg = "#0f172a"

        self.theme_mode = mode
        self.root.configure(bg=bg)

        if platform.system() == "Windows":
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass

        style.configure("TFrame", background=frame_bg)
        style.configure("TLabel", background=frame_bg, foreground=fg)
        style.configure("TCheckbutton", background=frame_bg, foreground=fg, font=("Helvetica", self.button_font_size))
        style.configure("TRadiobutton", background=frame_bg, foreground=fg, font=("Helvetica", self.button_font_size))
        style.configure("TEntry", fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg)
        style.configure("TSpinbox", fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg)
        style.configure(
            "TButton",
            font=("Helvetica", self.button_font_size),
            background=button_bg,
            foreground=fg,
            borderwidth=1,
            focusthickness=3,
            focuscolor=button_active,
        )
        style.map("TButton",
            background=[('active', button_active), ('pressed', button_active), ('!disabled', button_bg)],
            foreground=[('disabled', '#888888'), ('!disabled', fg)]
        )
        style.configure("Action.TButton", font=("Helvetica", self.button_font_size, "bold"), background=button_bg, foreground=fg, padding=max(6, self.button_font_size // 1))
        style.map("Action.TButton",
            background=[('active', button_active), ('pressed', button_active), ('!disabled', button_bg)],
            foreground=[('disabled', '#888888'), ('!disabled', fg)]
        )
        style.configure("Dialog.TFrame", background=frame_bg)
        style.configure("Dialog.TLabel", background=frame_bg, foreground=fg)
        style.configure("Dialog.TButton", font=("Helvetica", self.button_font_size), background=button_bg, foreground=fg)
        style.map("Dialog.TButton",
            background=[('active', button_active), ('pressed', button_active), ('!disabled', button_bg)],
            foreground=[('disabled', '#888888'), ('!disabled', fg)]
        )
        style.map("TCheckbutton",
            background=[('active', frame_bg), ('pressed', frame_bg), ('!disabled', frame_bg)],
            foreground=[('disabled', '#888888'), ('!disabled', fg)]
        )
        style.map("TRadiobutton",
            background=[('active', frame_bg), ('pressed', frame_bg), ('!disabled', frame_bg)],
            foreground=[('disabled', '#888888'), ('!disabled', fg)]
        )
        style.configure("Dialog.TEntry", fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg)
        style.configure("Dialog.TLabelframe", background=frame_bg, foreground=fg)
        style.configure("Dialog.TLabelframe.Label", background=frame_bg, foreground=fg)
        style.configure("Dialog.TRadiobutton", background=frame_bg, foreground=fg)
        style.configure("Dialog.TSpinbox", fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg)
        style.map("Action.TButton",
            background=[('active', button_active), ('pressed', button_active)],
            foreground=[('disabled', '#888888')]
        )
        style.configure(
            "Treeview",
            background=text_bg,
            fieldbackground=text_bg,
            foreground=fg,
            font=("Helvetica", self.table_font_size),
            rowheight=max(24, int(self.table_font_size * 2.8)),
        )
        style.map("Treeview", background=[('selected', selected_bg)], foreground=[('selected', selected_fg)])
        style.configure(
            "Treeview.Heading",
            background=heading_bg,
            foreground=heading_fg,
            relief="raised",
            font=("Helvetica", self.table_font_size, "bold"),
            padding=(8, 10),
        )
        style.map("Treeview.Heading",
            background=[('active', heading_bg), ('pressed', heading_bg)],
            foreground=[('active', heading_fg), ('pressed', heading_fg)]
        )
        style.configure("Horizontal.TScrollbar", background=frame_bg)
        style.configure("Vertical.TScrollbar", background=frame_bg)

        if hasattr(self, "output"):
            self.output.configure(bg=text_bg, fg=fg, insertbackground=fg, font=("Courier", self.output_font_size))

        if hasattr(self, "status_label"):
            self.status_label.configure(background=frame_bg, foreground=status_fg)

        if hasattr(self, "status_var"):
            self.status_var.set(self.status_var.get())

        self._theme_tree_tags(tree_tag_has, tree_tag_clean)

    def _theme_tree_tags(self, has_color: str, clean_color: str) -> None:
        if hasattr(self, "tree"):
            self.tree.tag_configure("has_commits", background=has_color)
            self.tree.tag_configure("clean", background=clean_color)

    def _build_layout(self) -> None:
        # Action buttons with better styling
        buttons = ttk.Frame(self.root, padding=8)
        buttons.pack(fill=tk.X, padx=12, pady=12)
        
        style = ttk.Style()
        style.configure("Action.TButton", font=("Helvetica", 10, "bold"), padding=8)
        
        ttk.Button(buttons, text="🔄 Refresh", command=self.refresh_repos, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="🔀 Switch Branch", command=self.action_switch, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="👁 Preview Commits", command=self.action_preview, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="📝 Make a Commit", command=self.action_make_commit, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="🚀 Move Commits", command=self.action_move, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="🔁 Reset", command=self.action_reset, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="⚙️ Settings", command=self.action_settings, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Split main content into resizable panes
        paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        # Repository tree with improved styling
        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=1)
        ttk.Label(tree_frame, text="📊 Repositories", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        style.configure("Treeview", font=("Helvetica", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))
        tree_container = ttk.Frame(tree_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_container,
            columns=("name", "commits", "pushed", "branch", "base"),
            show="tree headings",
            selectmode="browse",
            height=12,
        )
        self.tree.heading("#0", text="")
        self.tree.heading("name", text="Repository")
        self.tree.heading("commits", text="Pending")
        self.tree.heading("pushed", text="Pushed")
        self.tree.heading("branch", text="Current Branch")
        self.tree.heading("base", text="Base Branch")
        self.tree.column("#0", width=60, stretch=False)
        self.tree.column("name", width=250, anchor=tk.W)
        self.tree.column("commits", width=90, anchor=tk.CENTER)
        self.tree.column("pushed", width=90, anchor=tk.CENTER)
        self.tree.column("branch", width=170, anchor=tk.CENTER)
        self.tree.column("base", width=140, anchor=tk.CENTER)
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Output pane with better styling
        output_frame = ttk.Frame(paned)
        paned.add(output_frame, weight=1)
        ttk.Label(output_frame, text="📝 Output", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        output_container = ttk.Frame(output_frame)
        output_container.pack(fill=tk.BOTH, expand=True)
        self.output = scrolledtext.ScrolledText(
            output_container,
            height=12,
            state="disabled",
            font=("Courier", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            wrap=tk.WORD,
        )
        self.output.pack(fill=tk.BOTH, expand=True)

        # Status bar with better styling
        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(12, 8))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_var = tk.StringVar(value="✓ Ready")
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            anchor=tk.W,
            font=("Helvetica", 10, "bold"),
        )
        self.status_label.pack(fill=tk.X, ipady=2)

    def refresh_repos(self) -> None:
        base_dir = Path(self.base_var.get()).expanduser()
        try:
            states = RepoScanner.scan(base_dir)
        except GitManagerError as exc:
            messagebox.showerror("Error", str(exc))
            return

        self.states = states
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, state in enumerate(states, start=1):
            # Add visual indicators: icon + dirty marker in the first tree column
            icon = "📦" if state.local_exists else "📁"
            tag = "has_commits" if state.commit_count > 0 else "clean"
            first_col_text = f"{icon}{' ★' if state.dirty else ''}"
            repo_name = state.name
            
            self.tree.insert(
                "",
                tk.END,
                iid=str(idx - 1),
                values=(
                    repo_name,
                    state.commit_count,
                    state.pushed_count,
                    state.current_branch,
                    state.base_branch,
                ),
                text=first_col_text,
                tags=(tag,)
            )
        
        # Configure tag colors
        if self.theme_mode == "dark":
            self.tree.tag_configure("has_commits", background="#333333")
            self.tree.tag_configure("clean", background="#2b2b2b")
        else:
            self.tree.tag_configure("has_commits", background="#fff9e6")
            self.tree.tag_configure("clean", background="#f0f8ff")
        
        self.status_var.set(f"✓ Loaded {len(states)} repositories from {base_dir}")

    def switch_all_to_local_commit(self, skip_busy_check: bool = False) -> None:
        """Switch all repositories to local_commit branch."""
        if not self.states:
            return
        if not skip_busy_check and not self._start_operation("switch all repositories to local_commit"):
            return

        try:
            self.append_output("🔄 Ensuring all repositories are on local_commit branch...\n")
            for state in self.states:
                try:
                    if state.current_branch != "local_commit":
                        if state.local_exists:
                            BranchManager.checkout(state.path, "local_commit")
                            self.append_output(f"  ✓ {state.name}: switched to local_commit\n")
                        else:
                            # Create local_commit from base branch
                            BranchManager.switch_to_local_commit(state.path, state.base_branch)
                            self.append_output(f"  ✓ {state.name}: created and switched to local_commit\n")
                    else:
                        self.append_output(f"  ✓ {state.name}: already on local_commit\n")
                except GitManagerError as exc:
                    self.append_output(f"  ⚠️  {state.name}: {str(exc)}\n")
            self.append_output("✅ Branch check complete\n\n")
            self.refresh_repos()
        finally:
            if not skip_busy_check:
                self._end_operation()

    def on_closing(self) -> None:
        """Handle window close event."""
        if self.operation_in_progress:
            if not self._confirm_exit_during_operation():
                return
        self._cancel_auto_refresh()
        self.switch_all_to_local_commit(skip_busy_check=True)
        self.root.destroy()

    def append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert(tk.END, text + "\n")
        self.output.configure(state="disabled")
        self.output.see(tk.END)
        self.root.update()  # Force GUI refresh to show updates in real-time

    def _schedule_auto_refresh(self) -> None:
        self._cancel_auto_refresh()
        if not self.auto_refresh_enabled:
            return

        interval_ms = max(1, self.refresh_interval) * 60_000
        self.auto_refresh_job = self.root.after(interval_ms, self._auto_refresh_callback)

    def _cancel_auto_refresh(self) -> None:
        if getattr(self, "auto_refresh_job", None) is not None:
            try:
                self.root.after_cancel(self.auto_refresh_job)
            except Exception:
                pass
            self.auto_refresh_job = None

    def _update_auto_refresh(self) -> None:
        if self.auto_refresh_enabled:
            self._schedule_auto_refresh()
        else:
            self._cancel_auto_refresh()

    def _auto_refresh_callback(self) -> None:
        self.refresh_repos()
        self._schedule_auto_refresh()

    # --- helpers ---------------------------------------------------------
    def _abort_in_progress_ops(self, repo: Path) -> None:
        git_dir = repo / ".git"
        if (git_dir / "MERGE_HEAD").exists():
            try:
                GitOperations.run_git(["merge", "--abort"], cwd=repo)
            except GitManagerError as exc:
                self.append_output(f"⚠️  Could not abort merge cleanly: {str(exc)}\n")
        if (git_dir / "CHERRY_PICK_HEAD").exists():
            try:
                GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
            except GitManagerError as exc:
                self.append_output(f"⚠️  Could not abort cherry-pick cleanly: {str(exc)}\n")
        if (git_dir / "rebase-merge").exists():
            try:
                GitOperations.run_git(["rebase", "--abort"], cwd=repo)
            except GitManagerError as exc:
                self.append_output(f"⚠️  Could not abort rebase cleanly: {str(exc)}\n")

    def _choose_conflict_resolution(self, commit: str, conflicts: str) -> str:
        prompt = (
            f"Cherry-pick conflicts for {commit[:7]}\n\n"
            f"Conflicted files:\n{conflicts}\n\n"
            "Choose: 1) Keep base (ours)  2) Incoming (theirs)  3) Abort  4) Skip"
        )
        choice = simpledialog.askstring("Conflicts", prompt, parent=self.root)
        if not choice:
            raise GitManagerError("Conflict resolution cancelled")
        choice = choice.strip()
        if choice == "1":
            return "ours"
        if choice == "2":
            return "theirs"
        if choice == "3":
            return "abort"
        if choice == "4":
            return "skip"
        raise GitManagerError("Invalid conflict resolution choice")

    def _backup_local_commit(self, repo: Path) -> str:
        backup_name = f"backup_local_commit_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            GitOperations.run_git(["branch", backup_name, "local_commit"], cwd=repo)
            self.append_output(f"🛟 Created {backup_name} from local_commit before rewrite")
        except GitManagerError as exc:
            self.append_output(f"⚠️  Failed to create backup branch: {str(exc)}\n")
        return backup_name

    def selected_state(self) -> Optional[RepoState]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select repository", "Please select a repository first.")
            return None
        idx = int(sel[0])
        if idx < 0 or idx >= len(self.states):
            return None
        return self.states[idx]

    def action_change_base_directory(self) -> None:
        if not self._start_operation("change the base directory"):
            return
        try:
            new_dir = filedialog.askdirectory(
                parent=self.root,
                title="Select Base Directory",
                initialdir=self.base_var.get(),
            )
            if not new_dir:
                return
            self.base_var.set(new_dir)
            self.db.set_base_directory(new_dir)
            self.append_output(f"💾 Saved base directory: {new_dir}\n")
            self.refresh_repos()
            self.append_output("✅ Base directory updated. You may continue or close the app.\n")
        finally:
            self._end_operation()

    def action_settings(self) -> None:
        if self.operation_in_progress:
            messagebox.showerror(
                "Operation in progress",
                "Another operation is currently running. Please wait for it to finish before opening settings.",
                parent=self.root,
            )
            return
        dialog = SettingsDialog(
            self.root,
            self.base_var.get(),
            self.auto_switch_to_local_commit,
            self.theme_mode,
            self.auto_refresh_enabled,
            self.refresh_interval,
            self.output_font_size,
            self.table_font_size,
            self.button_font_size,
        )
        self.root.wait_window(dialog)
        if dialog.result is None:
            return

        new_base, auto_switch, theme_mode, auto_refresh_enabled, refresh_interval, output_font_size, table_font_size, button_font_size = dialog.result
        self.base_var.set(new_base)
        self.auto_switch_to_local_commit = auto_switch
        self.auto_refresh_enabled = auto_refresh_enabled
        self.refresh_interval = refresh_interval
        self.theme_mode = theme_mode
        self.output_font_size = output_font_size
        self.table_font_size = table_font_size
        self.button_font_size = button_font_size
        self.db.set_base_directory(new_base)
        self.db.set_auto_switch_local_commit(auto_switch)
        self.db.set_theme_mode(theme_mode)
        self.db.set_auto_refresh_enabled(auto_refresh_enabled)
        self.db.set_refresh_interval(refresh_interval)
        self.db.set_output_font_size(output_font_size)
        self.db.set_table_font_size(table_font_size)
        self.db.set_button_font_size(button_font_size)

        self.append_output(f"💾 Settings saved. Base directory: {new_base}\n")
        self.apply_theme(self.theme_mode)
        self._update_auto_refresh()
        self.refresh_repos()
        if auto_switch:
            self.switch_all_to_local_commit()
        self.append_output("✅ Settings saved. You may continue or close the app.\n")

    def action_switch(self) -> None:
        if not self._start_operation("switch branches"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return
        try:
            GitConfig.ensure_identity(state.path)
            if state.current_branch == "local_commit":
                BranchManager.switch_to_base(state.path, state.base_branch)
                new_branch = state.base_branch
            else:
                BranchManager.switch_to_local_commit(state.path, state.base_branch)
                new_branch = "local_commit"
            self.append_output(f"Switched to {new_branch} in {state.name}")
            self.refresh_repos()
            self.append_output("✅ Operation complete. The branch switch is done.\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")
        finally:
            self._end_operation()

    def _resolve_upstream(self, repo: Path, branch: str, base_branch: str) -> Optional[str]:
        try:
            upstream = GitOperations.run_git(
                ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                cwd=repo,
            ).strip()
            if upstream:
                return upstream
        except GitManagerError:
            pass

        if branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], cwd=repo):
            return f"origin/{branch}"

        if branch == base_branch and base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
            return f"origin/{base_branch}"

        if GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "origin/HEAD"], cwd=repo):
            origin_head = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo).strip()
            if origin_head and origin_head != "HEAD":
                return origin_head

        return None

    def action_preview(self) -> None:
        if not self._start_operation("preview commits"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return

        try:
            dialog = PreviewModeDialog(self.root, self.theme_mode)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return

            mode = dialog.result
            branch = state.current_branch
            upstream = self._resolve_upstream(state.path, branch, state.base_branch)

            if mode == "unpushed":
                if branch == "local_commit":
                    if not state.base_branch:
                        raise GitManagerError("Cannot preview unpushed commits for local_commit without a configured base branch.")
                    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.base_branch}"], cwd=state.path):
                        remote_base = f"origin/{state.base_branch}"
                    elif GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "origin/HEAD"], cwd=state.path):
                        remote_base = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=state.path).strip()
                    else:
                        raise GitManagerError("No remote base branch found for local_commit preview.")
                    log_range = f"{remote_base}..local_commit"
                    title = f"Unpushed commits on local_commit relative to {remote_base}"
                else:
                    if upstream:
                        log_range = f"{upstream}..{branch}"
                    elif GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], cwd=state.path):
                        log_range = f"origin/{branch}..{branch}"
                    elif branch == state.base_branch and state.base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.base_branch}"], cwd=state.path):
                        log_range = f"origin/{state.base_branch}..{state.base_branch}"
                    else:
                        raise GitManagerError("Current branch has no upstream or remote tracking branch to compare for unpushed commits.")
                    title = f"Unpushed commits on {branch}"
            else:
                if upstream:
                    log_range = upstream
                elif branch == state.base_branch and state.base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.base_branch}"], cwd=state.path):
                    log_range = f"origin/{state.base_branch}"
                elif GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], cwd=state.path):
                    log_range = f"origin/{branch}"
                elif branch == "local_commit" and state.base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.base_branch}"], cwd=state.path):
                    log_range = f"origin/{state.base_branch}"
                else:
                    raise GitManagerError("Current branch has no upstream or remote branch to display pushed commits.")
                title = f"Pushed commits on {log_range}"

            log = GitOperations.run_git(
                [
                    "log",
                    "--reverse",
                    "--no-decorate",
                    "--date=short",
                    "--pretty=format:  %h  %ad  %s",
                    log_range,
                ],
                cwd=state.path,
            )
            if not log.strip():
                self.append_output(f"No {mode} commits found for {state.name}.\n")
                self.append_output("✅ Preview complete. No changes were made.\n")
                return
            self.append_output(f"{title} for {state.name}:\n{log}\n")
            self.append_output("✅ Preview complete. You may review the output and close this view.\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")
        finally:
            self._end_operation()

    def action_reset(self) -> None:
        if not self._start_operation("reset the repository"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return

        try:
            dialog = ResetDialog(self.root, state.name, self.theme_mode)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return

            target, reset_type = dialog.result
            if reset_type == "hard" and not messagebox.askyesno(
                "Confirm Hard Reset",
                f"Hard reset will discard uncommitted changes and move the branch to {target}. Continue?",
                parent=self.root,
            ):
                return

            self.append_output(f"🔁 Resetting {state.name} to {target} with --{reset_type}...\n")
            GitOperations.run_git(["reset", f"--{reset_type}", target], cwd=state.path)
            self.append_output(f"✅ Reset {state.name} to {target} with --{reset_type}\n")
            self.refresh_repos()
            self.append_output("✅ Reset complete. The repository is now on the target branch.\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            messagebox.showerror("Reset Failed", "An error occurred during reset. Check the output panel for details.")
        finally:
            self._end_operation()

    def action_make_commit(self) -> None:
        if not self._start_operation("make a commit"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return

        repo = state.path
        try:
            GitConfig.ensure_identity(repo)

            if GitOperations.git_ok(["diff", "--quiet"], cwd=repo) and GitOperations.git_ok(["diff", "--cached", "--quiet"], cwd=repo):
                messagebox.showinfo("No changes", "There are no changes to commit in the selected repository.")
                return

            dialog = CommitDialog(self.root, state.name, self.theme_mode)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return

            message, add_mode, pathspec = dialog.result
            self.append_output(f"📝 Preparing commit in {state.name}...\n")

            if add_mode == "all":
                self.append_output("   • Staging all changes (tracked + untracked)\n")
                GitOperations.run_git(["add", "-A"], cwd=repo)
            elif add_mode == "tracked":
                self.append_output("   • Staging tracked changes only\n")
                GitOperations.run_git(["add", "-u"], cwd=repo)
            else:
                self.append_output(f"   • Staging specified paths: {pathspec}\n")
                GitOperations.run_git(["add", *pathspec.split()], cwd=repo)

            if GitOperations.git_ok(["diff", "--cached", "--quiet"], cwd=repo):
                messagebox.showinfo("Nothing staged", "No changes were staged for commit. Adjust the add scope and try again.")
                return

            GitOperations.run_git(["commit", "-m", message.strip()], cwd=repo)
            self.append_output(f"✅ Commit created in {state.name}: {message.strip()}")
            self.refresh_repos()
            self.append_output("✅ Commit complete. You may close the app or continue working.\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            messagebox.showerror("Commit Failed", "An error occurred while committing. Check the output panel for details.")
        finally:
            self._end_operation()

    def action_move(self) -> None:
        if not self._start_operation("move commits"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return
        repo = state.path
        base_branch = state.base_branch
        temp_branch: str | None = None
        base_before: str | None = None
        local_before: str | None = None
        stashed = False
        original_branch = "HEAD"
        try:
            GitConfig.ensure_identity(repo)
            if not GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "local_commit"], cwd=repo):
                raise GitManagerError("local_commit does not exist")

            if GitOperations.git_ok(["remote", "get-url", "origin"], cwd=repo):
                try:
                    self.append_output("🔄 Fetching origin before move...\n")
                    GitOperations.run_git(["fetch", "--prune", "origin"], cwd=repo)
                except GitManagerError as exc:
                    raise GitManagerError(
                        f"Failed to fetch origin before move. Remote is unavailable or access is denied: {str(exc)}"
                    )

            remote_base = f"origin/{base_branch}"
            if base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/{remote_base}"], cwd=repo):
                ahead = int(
                    GitOperations.run_git(["rev-list", "--count", f"{base_branch}..{remote_base}"], cwd=repo).strip() or "0"
                )
                behind = int(
                    GitOperations.run_git(["rev-list", "--count", f"{remote_base}..{base_branch}"], cwd=repo).strip() or "0"
                )
                if ahead > 0 and behind > 0:
                    raise GitManagerError(
                        f"Local {base_branch} diverges from {remote_base}. Sync or rebase before moving commits."
                    )
                if ahead > 0:
                    self.append_output(f"ℹ️ Local {base_branch} is behind {remote_base}; applying commits onto remote history.\n")
                    start_ref = remote_base
                elif behind > 0:
                    raise GitManagerError(
                        f"Local {base_branch} has unpushed commits. Push or rebase it before moving commits."
                    )
                else:
                    start_ref = base_branch
            else:
                start_ref = base_branch

            base_before = GitOperations.run_git(["rev-parse", "--verify", start_ref], cwd=repo).strip()
            local_before = GitOperations.run_git(["rev-parse", "--verify", "local_commit"], cwd=repo).strip()
            pending = int(GitOperations.run_git(["rev-list", "--count", f"{base_branch}..local_commit"], cwd=repo).strip() or "0")
            if pending == 0:
                messagebox.showinfo("No commits", "No commits to move.")
                return

            dialog = NumericKeypadDialog(
                self.root,
                "Move commits",
                f"How many commits to move to {state.base_branch}?\n(1 to {pending})",
                minvalue=1,
                maxvalue=pending,
                theme_mode=self.theme_mode,
            )
            self.root.wait_window(dialog)
            num = dialog.result
            if num is None:
                return

            original_branch = GitOperations.run_git(["branch", "--show-current"], cwd=repo).strip() or "HEAD"
            if not WorkingTreeManager.is_clean(repo):
                if not messagebox.askyesno(
                    "Uncommitted Changes",
                    "Working tree not clean. Stash (incl. untracked) and continue?\n"
                    "This will also abort any ongoing merge/cherry-pick/rebase first.",
                ):
                    return
                self._abort_in_progress_ops(repo)
                WorkingTreeManager.stash(repo, f"git-manager auto-stash before moving commits ({now_display()})")
                stashed = True

            all_commits = GitOperations.run_git(["rev-list", "--reverse", f"{base_branch}..local_commit"], cwd=repo).strip().splitlines()
            if not all_commits:
                raise GitManagerError("No commits to process")
            commits = all_commits[:num]  # Only process the first num commits
            processed: list[str] = []

            self.append_output(f"🕒 Rewriting commits with current user info...\n")
            expected_email = GitOperations.run_git(["config", "user.email"], cwd=repo).strip()
            expected_name = GitOperations.run_git(["config", "user.name"], cwd=repo).strip()
            self.append_output(f"⚠️  All commits will be authored by: {expected_name} <{expected_email}>\n")

            temp_branch = f"tmp_git_manager_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            GitOperations.run_git(["branch", temp_branch, base_before], cwd=repo)
            BranchManager.checkout(repo, temp_branch)
            now_iso_value = now_iso()
            for idx, commit in enumerate(commits):
                remaining = len(commits) - idx - 1
                subject = GitOperations.run_git(["show", "-s", "--format=%s", commit], cwd=repo).strip()
                self.append_output(f"📌 Processing {idx + 1}/{len(commits)}: {commit[:7]} '{subject}' ({remaining} remaining)...\n")
                try:
                    GitOperations.run_git(["cherry-pick", "--no-commit", commit], cwd=repo)
                except GitManagerError:
                    conflict_names = GitOperations.run_git(["diff", "--name-only", "--diff-filter=U"], cwd=repo).strip()
                    if conflict_names:
                        try:
                            choice = self._choose_conflict_resolution(commit, conflict_names)
                        except GitManagerError as choice_err:
                            GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                            raise choice_err

                        if choice == "ours":
                            GitOperations.run_git(["checkout", "--ours", "."], cwd=repo)
                            GitOperations.run_git(["add", "."], cwd=repo)
                            msg = GitOperations.run_git(["show", "-s", "--format=%B", commit], cwd=repo)
                            GitOperations.run_git_env(
                                ["commit", "-m", msg, "--date", now_iso_value],
                                cwd=repo,
                                extra_env={"GIT_AUTHOR_DATE": now_iso_value, "GIT_COMMITTER_DATE": now_iso_value},
                            )
                            self.append_output(f"✓ Resolved with ours for {commit[:7]}")
                            self.append_output(GitOperations.run_git(["show", "-s", "--date=iso", "--pretty=format:  ✔ %h  %ad  %an <%ae>"], cwd=repo) + "\n")
                            processed.append(commit)
                            continue

                        if choice == "theirs":
                            GitOperations.run_git(["checkout", "--theirs", "."], cwd=repo)
                            GitOperations.run_git(["add", "."], cwd=repo)
                            msg = GitOperations.run_git(["show", "-s", "--format=%B", commit], cwd=repo)
                            GitOperations.run_git_env(
                                ["commit", "-m", msg, "--date", now_iso_value],
                                cwd=repo,
                                extra_env={"GIT_AUTHOR_DATE": now_iso_value, "GIT_COMMITTER_DATE": now_iso_value},
                            )
                            self.append_output(f"✓ Resolved with theirs for {commit[:7]}")
                            self.append_output(GitOperations.run_git(["show", "-s", "--date=iso", "--pretty=format:  ✔ %h  %ad  %an <%ae>"], cwd=repo) + "\n")
                            processed.append(commit)
                            continue

                        if choice == "skip":
                            GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                            self.append_output(f"⊘ Skipping commit {commit[:7]} after conflicts")
                            continue

                        # Abort / manual resolution
                        GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                        raise GitManagerError("Cherry-pick aborted for manual resolution")
                    status = GitOperations.run_git(["status"], cwd=repo)
                    if "nothing to commit" in status:
                        self.append_output(f"⊘ Skipping empty commit {commit[:7]}\n")
                        GitOperations.run_git(["cherry-pick", "--skip"], cwd=repo)
                        continue
                    raise

                # Check if there are any staged changes to commit (ignore untracked files)
                has_staged_changes = not GitOperations.git_ok(["diff", "--cached", "--quiet"], cwd=repo)
                if not has_staged_changes:
                    self.append_output(f"⊘ Skipping empty commit {commit[:7]} (already applied)\n")
                    continue

                message = GitOperations.run_git(["show", "-s", "--format=%B", commit], cwd=repo)
                GitOperations.run_git_env(
                    ["commit", "-m", message, "--date", now_iso_value],
                    cwd=repo,
                    extra_env={"GIT_AUTHOR_DATE": now_iso_value, "GIT_COMMITTER_DATE": now_iso_value},
                )
                processed.append(commit)
                self.append_output(GitOperations.run_git(["show", "-s", "--date=iso", "--pretty=format:  ✔ %h  %ad  %an <%ae>"], cwd=repo) + "\n")

            processed_count = len(processed)
            if processed_count == 0:
                self.append_output("No commits were applied; aborting move.")
                BranchManager.checkout(repo, original_branch)
                if stashed:
                    try:
                        WorkingTreeManager.pop_stash(repo)
                    except GitManagerError as exc:
                        self.append_output(f"⚠️ Stash pop failed: {str(exc)}\nResolve manually with 'git stash pop'\n")
                return

            self.append_output(f"📜 Latest moved commits on {base_branch} (with author info):\n")
            latest_log = GitOperations.run_git(["log", "-n", str(processed_count), temp_branch, "--no-decorate", "--date=iso", "--pretty=format:  %h  %ad  %an <%ae>"], cwd=repo)
            self.append_output(latest_log + "\n")

            # ===== Pre-push validation =====
            self.append_output("🔍 Validating commits before push...\n")
            # 1) Ensure remote default branch matches target base branch
            if GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "origin/HEAD"], cwd=repo):
                remote_head = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo).strip().removeprefix("origin/")
                if remote_head and remote_head != base_branch:
                    raise GitManagerError(
                        f"Remote default branch is '{remote_head}', but target is '{base_branch}'."
                    )

            # 2) Ensure author date day equals today's day for all moved commits
            dates = GitOperations.run_git(["log", "-n", str(processed_count), temp_branch, "--date=short", "--pretty=format:%ad"], cwd=repo).splitlines()
            today_str = now_iso()[:10]
            bad_dates = [d for d in dates if d and d != today_str]
            if bad_dates:
                raise GitManagerError(f"Found {len(bad_dates)} commit(s) with author date not equal to today")

            # 3) Ensure author email matches local git config (so GitHub can attribute contributions)
            emails = GitOperations.run_git(["log", "-n", str(processed_count), temp_branch, "--pretty=format:%ae"], cwd=repo).splitlines()
            names = GitOperations.run_git(["log", "-n", str(processed_count), temp_branch, "--pretty=format:%an"], cwd=repo).splitlines()
            if any(e and e != expected_email for e in emails):
                raise GitManagerError(f"Found commit(s) with author email not matching '{expected_email}'")
            if any(n and n != expected_name for n in names):
                raise GitManagerError(f"Found commit(s) with author name not matching '{expected_name}'")

            self.append_output(f"✅ All {processed_count} commits have correct author info (will be attributed to {expected_name} <{expected_email}>)\n")
            self.append_output(f"🚀 Pushing to origin {base_branch}...\n")
            GitOperations.run_git(["push", "origin", f"{temp_branch}:{base_branch}"], cwd=repo)
            self.append_output(f"✅ Done! {processed_count} commits moved with date/time {now_iso_value}\n")

            BranchManager.checkout(repo, base_branch)
            GitOperations.run_git(["reset", "--hard", temp_branch], cwd=repo)

            # ===== Clean up local_commit ONLY AFTER successful push =====
            backup_branch = self._backup_local_commit(repo)
            
            # Check if we moved all commits or only some
            if processed_count < pending:
                # Some commits remain on local_commit - need to rewrite it
                # Get the remaining commits BEFORE any changes (using original SHAs)
                remaining_original = all_commits[processed_count:]  # The commits we didn't process
                
                self.append_output(f"⚠️  You moved {processed_count} of {pending} commits.\n")
                self.append_output(f"🔄 Rewriting local_commit to keep only {len(remaining_original)} remaining commits...\n")
                BranchManager.checkout(repo, "local_commit")
                GitOperations.run_git(["reset", "--hard", base_branch], cwd=repo)
                
                for commit in remaining_original:
                    try:
                        GitOperations.run_git(["cherry-pick", commit], cwd=repo)
                    except GitManagerError:
                        # Check if it's an empty commit (already applied)
                        status = GitOperations.run_git(["status"], cwd=repo)
                        if "nothing to commit" in status:
                            self.append_output(f"⊘ Skipping empty commit {commit[:7]} (already on {base_branch})\n")
                            GitOperations.run_git(["cherry-pick", "--skip"], cwd=repo)
                            continue
                        # Otherwise abort and raise error
                        GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                        raise GitManagerError(
                            f"Cherry-pick failed while rewriting local_commit for commit {commit}. Resolve manually."
                        )
                self.append_output("✅ local_commit updated to reflect remaining commits.\n")
            else:
                # All commits were moved - simply sync local_commit to base
                self.append_output(f"🔄 Syncing local_commit to {base_branch}...\n")
                BranchManager.checkout(repo, "local_commit")
                GitOperations.run_git(["reset", "--hard", base_branch], cwd=repo)
                self.append_output(f"✅ local_commit is now aligned with {base_branch}\n")

            if stashed:
                self.append_output(f"🔧 Restoring stashed changes to {original_branch}...\n")
                BranchManager.checkout(repo, original_branch)
                try:
                    WorkingTreeManager.pop_stash(repo)
                except GitManagerError as exc:
                    self.append_output(f"⚠️ Stash pop failed: {str(exc)}\nResolve manually with 'git stash pop'\n")

            if temp_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{temp_branch}"], cwd=repo):
                GitOperations.run_git(["branch", "-D", temp_branch], cwd=repo)
                temp_branch = None
            self.refresh_repos()
            self.append_output("✅ Move complete. local_commit and the base branch are now updated.\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            if temp_branch or base_before or local_before:
                self.append_output("↩️ Rolling back to previous state...\n")
                try:
                    self._abort_in_progress_ops(repo)
                except GitManagerError:
                    pass
                if base_before and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
                    try:
                        BranchManager.checkout(repo, base_branch)
                        GitOperations.run_git(["reset", "--hard", base_before], cwd=repo)
                    except GitManagerError:
                        pass
                if local_before and GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=repo):
                    try:
                        BranchManager.checkout(repo, "local_commit")
                        GitOperations.run_git(["reset", "--hard", local_before], cwd=repo)
                    except GitManagerError:
                        pass
                if temp_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{temp_branch}"], cwd=repo):
                    try:
                        GitOperations.run_git(["branch", "-D", temp_branch], cwd=repo)
                    except GitManagerError:
                        pass
                if stashed:
                    try:
                        BranchManager.checkout(repo, original_branch)
                        WorkingTreeManager.pop_stash(repo)
                    except GitManagerError:
                        self.append_output("⚠️ Rollback stash pop failed. Resolve manually with 'git stash pop'\n")
            messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")
        finally:
            self._end_operation()

def _enable_windows_dpi_awareness() -> None:
    if platform.system() != "Windows":
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except OSError:
            pass


def main() -> None:
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    
    # Get screen dimensions and maximize
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{screen_width}x{screen_height}+0+0")
    try:
        root.attributes('-zoomed', True)  # Maximize window with controls
    except tk.TclError:
        try:
            root.state('zoomed')
        except tk.TclError:
            # Some Tk builds do not support zoomed state or -zoomed attribute.
            pass

    def _toggle_fullscreen(event: tk.Event | None = None) -> None:
        is_fullscreen = bool(root.attributes('-fullscreen'))
        root.attributes('-fullscreen', not is_fullscreen)

    root.bind('<F11>', _toggle_fullscreen)
    root.bind('<Escape>', lambda e: root.attributes('-fullscreen', False))

    gui = GitManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
