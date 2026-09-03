"""Commit dialog for message and add scope selection."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional


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
