"""Application bootstrap for Git Manager."""

from __future__ import annotations

import tkinter as tk

from ui.main_window import GitManagerGUI
from utils.platform import enable_windows_dpi_awareness


def main() -> None:
    enable_windows_dpi_awareness()
    root = tk.Tk()

    # Restore saved geometry / maximized state if available; otherwise maximize.
    try:
        from core.settings_db import SettingsDB

        db = SettingsDB()
        geom = db.get_window_geometry()
        maximized = db.get_window_maximized()
        if maximized is True:
            # User last closed maximized -> restore maximized
            try:
                root.attributes("-zoomed", True)
            except tk.TclError:
                try:
                    root.state("zoomed")
                except tk.TclError:
                    pass
            # Fallback geometry if attributes/state unsupported
            if geom:
                try:
                    root.geometry(geom)
                except tk.TclError:
                    pass
        elif maximized is False and geom:
            try:
                root.geometry(geom)
            except tk.TclError:
                # Fallback to maximizing if saved geometry invalid
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.geometry(f"{screen_width}x{screen_height}+0+0")
        else:
            # No history -> default maximized (preserve original behavior)
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.geometry(f"{screen_width}x{screen_height}+0+0")
            try:
                root.attributes("-zoomed", True)
            except tk.TclError:
                try:
                    root.state("zoomed")
                except tk.TclError:
                    pass
    except Exception:
        # On any error keep original maximizing behavior
        try:
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.geometry(f"{screen_width}x{screen_height}+0+0")
            try:
                root.attributes("-zoomed", True)
            except tk.TclError:
                try:
                    root.state("zoomed")
                except tk.TclError:
                    pass
        except Exception:
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
