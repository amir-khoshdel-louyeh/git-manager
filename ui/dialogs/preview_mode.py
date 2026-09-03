"""Preview mode dialog: choose pushed vs unpushed commits."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional


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
