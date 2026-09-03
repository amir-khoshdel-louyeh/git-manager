"""Application bootstrap for Git Manager."""

from __future__ import annotations

import tkinter as tk

from ui.main_window import GitManagerGUI
from utils.platform import enable_windows_dpi_awareness


def main() -> None:
    enable_windows_dpi_awareness()
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

    gui = GitManagerGUI(root)  # noqa: F841
    root.mainloop()


if __name__ == "__main__":
    main()
