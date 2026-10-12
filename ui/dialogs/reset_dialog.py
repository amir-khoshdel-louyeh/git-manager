"""Reset dialog for selecting target and type."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from ui import scaling
from ui.theme import get_theme


class ResetDialog(tk.Toplevel):
    """Dialog to select a reset target commit and reset type."""

    def __init__(self, parent: tk.Tk, repo_name: str, theme_mode: str = "light") -> None:
        super().__init__(parent)
        self.title(f"Reset {repo_name}")
        self.resizable(True, True)
        self.result: Optional[tuple[str, str]] = None
        self.theme_mode = theme_mode

        colors = get_theme(theme_mode)
        self.configure(bg=colors["frame_bg"])

        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Reset target commit or ref:", font=("Helvetica", 10, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, padx=scaling.px(20), pady=(scaling.px(16), scaling.px(4)))
        self.target_var = tk.StringVar(value="")
        ttk.Entry(self, textvariable=self.target_var, width=44, style="Dialog.TEntry").pack(padx=scaling.px(20), pady=(0, scaling.px(12)), fill=tk.X)

        ttk.Label(self, text="Reset type:", font=("Helvetica", 10, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, padx=scaling.px(20), pady=(0, scaling.px(4)))
        self.reset_type = tk.StringVar(value="hard")
        types_frame = ttk.Frame(self, style="Dialog.TFrame")
        types_frame.pack(fill=tk.X, padx=scaling.px(20))
        ttk.Radiobutton(types_frame, text="Hard", variable=self.reset_type, value="hard", style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(types_frame, text="Mixed", variable=self.reset_type, value="mixed", style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(types_frame, text="Soft", variable=self.reset_type, value="soft", style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=4)

        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(pady=16)
        ttk.Button(button_frame, text="Reset", command=self._on_ok, style="Dialog.TButton", width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton", width=12).pack(side=tk.LEFT, padx=5)

        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        scaling.center_on_parent(self, parent)

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
