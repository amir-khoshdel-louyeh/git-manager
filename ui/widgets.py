"""Small reusable widgets shared by the dialogs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    """A vertically scrollable container.

    Dialogs that hold many settings need to work on a 768px-tall laptop just
    as well as on a large monitor. Put the content in :attr:`inner`; the
    scrollbar appears automatically only when the content is taller than the
    viewport.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        style: str = "Dialog.TFrame",
        background: str = "#ffffff",
        padding: int = 0,
    ) -> None:
        super().__init__(parent, style=style)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            background=background,
            highlightthickness=0,
            borderwidth=0,
            takefocus=0,
        )
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.inner = ttk.Frame(self.canvas, style=style, padding=padding)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Wheel events bubble to the toplevel bindtag, which covers children
        # too (unlike binding only the canvas). The handler only acts when
        # the pointer is over this scroll area.
        try:
            toplevel = self.winfo_toplevel()
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                toplevel.bind(sequence, self._on_wheel, add="+")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ size
    def _on_inner_configure(self, event: tk.Event | None = None) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            return
        self._sync_scrollbar()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        try:
            self.canvas.itemconfigure(self._window, width=event.width)
        except tk.TclError:
            return
        self._sync_scrollbar()

    def _sync_scrollbar(self) -> None:
        try:
            needed = self.inner.winfo_reqheight() > self.canvas.winfo_height() + 1
        except tk.TclError:
            return
        try:
            if needed:
                self.scrollbar.grid()
            else:
                self.scrollbar.grid_remove()
        except tk.TclError:
            pass

    # ----------------------------------------------------------------- wheel
    def _is_inside(self, event: tk.Event) -> bool:
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, AttributeError):
            return False
        if widget is None:
            return False
        try:
            path = str(widget)
            root_path = str(self)
        except tk.TclError:
            return False
        return path == root_path or path.startswith(root_path + ".")

    def _on_wheel(self, event: tk.Event) -> str | None:
        if not self._is_inside(event):
            return None
        num = getattr(event, "num", None)
        if num == 4:
            delta = -1
        elif num == 5:
            delta = 1
        else:
            raw = getattr(event, "delta", 0)
            delta = -1 if raw and raw > 0 else 1
        try:
            self.canvas.yview_scroll(delta, "units")
        except tk.TclError:
            return None
        return "break"
