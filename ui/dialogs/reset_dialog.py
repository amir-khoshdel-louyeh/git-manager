"""Reset dialog for selecting target and type."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional


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
