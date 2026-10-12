"""Preview mode dialog: choose pushed vs unpushed commits."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ui import scaling
from ui.theme import get_theme


class PreviewModeDialog(tk.Toplevel):
    """Dialog asking whether to preview pushed or unpushed commits."""

    def __init__(self, parent: tk.Tk, theme_mode: str = "light") -> None:
        super().__init__(parent)
        self.title("Preview Commits")
        self.resizable(True, True)
        self.result: Optional[str] = None
        self.theme_mode = theme_mode

        colors = get_theme(theme_mode)
        self.configure(bg=colors["frame_bg"])

        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="Which commits would you like to preview?", font=("Helvetica", 11, "bold"), wraplength=scaling.px(360), style="Dialog.TLabel").pack(padx=scaling.px(20), pady=(scaling.px(16), scaling.px(8)))

        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(padx=scaling.px(20), pady=(0, scaling.px(16)), fill=tk.X)

        ttk.Button(button_frame, text="Pushed commits", command=self._on_pushed, width=18, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Unpushed commits", command=self._on_unpushed, width=18, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)

        cancel_frame = ttk.Frame(self, style="Dialog.TFrame")
        cancel_frame.pack(padx=scaling.px(20), pady=(0, scaling.px(16)), fill=tk.X)
        ttk.Button(cancel_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton", width=12).pack(side=tk.RIGHT, padx=5)

        self.bind("<Escape>", lambda e: self._on_cancel())
        scaling.center_on_parent(self, parent)

    def _on_pushed(self) -> None:
        self.result = "pushed"
        self.destroy()

    def _on_unpushed(self) -> None:
        self.result = "unpushed"
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
