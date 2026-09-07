"""Theme handling for Git Manager GUI."""

from __future__ import annotations

import platform
import tkinter as tk
from tkinter import ttk


THEMES = {
    "dark": {
        "bg": "#141619",
        "frame_bg": "#1f242a",
        "text_bg": "#181c21",
        "fg": "#e4e6eb",
        "button_bg": "#2c3138",
        "button_active": "#3b4350",
        "heading_bg": "#232a33",
        "heading_fg": "#e8ebf0",
        "entry_bg": "#1e2228",
        "entry_fg": "#e8ebf0",
        "status_fg": "#8ab4f8",
        "tree_tag_has": "#2b3137",
        "tree_tag_clean": "#1e2228",
        "selected_bg": "#264a6c",
        "selected_fg": "#ffffff",
    },
    "light": {
        "bg": "#eef2f6",
        "frame_bg": "#f7f9fb",
        "text_bg": "#fafbff",
        "fg": "#1f2937",
        "button_bg": "#e2e8f0",
        "button_active": "#cbd5e1",
        "heading_bg": "#e6eef6",
        "heading_fg": "#111827",
        "entry_bg": "#f1f5f9",
        "entry_fg": "#111827",
        "status_fg": "#2563eb",
        "tree_tag_has": "#fdf2e9",
        "tree_tag_clean": "#eef4fb",
        "selected_bg": "#dbeafe",
        "selected_fg": "#0f172a",
    },
}


def get_theme(mode: str) -> dict[str, str]:
    """Return theme dict for mode, defaulting to light."""
    return THEMES.get(mode, THEMES["light"])


def apply_theme(
    root: tk.Tk,
    mode: str,
    button_font_size: int,
    table_font_size: int,
    output_font_size: int,
    output_widget: tk.Widget | None = None,
    status_label: ttk.Label | None = None,
    tree: ttk.Treeview | None = None,
) -> dict[str, str]:
    """Apply ttk theme and return computed colors."""
    style = ttk.Style()
    colors = get_theme(mode)

    bg = colors["bg"]
    frame_bg = colors["frame_bg"]
    text_bg = colors["text_bg"]
    fg = colors["fg"]
    button_bg = colors["button_bg"]
    button_active = colors["button_active"]
    heading_bg = colors["heading_bg"]
    heading_fg = colors["heading_fg"]
    entry_bg = colors["entry_bg"]
    entry_fg = colors["entry_fg"]
    status_fg = colors["status_fg"]
    tree_tag_has = colors["tree_tag_has"]
    tree_tag_clean = colors["tree_tag_clean"]
    selected_bg = colors["selected_bg"]
    selected_fg = colors["selected_fg"]

    root.configure(bg=bg)

    if platform.system() == "Windows":
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

    style.configure("TFrame", background=frame_bg)
    style.configure("TLabel", background=frame_bg, foreground=fg)
    style.configure("TCheckbutton", background=frame_bg, foreground=fg, font=("Helvetica", button_font_size))
    style.configure("TRadiobutton", background=frame_bg, foreground=fg, font=("Helvetica", button_font_size))
    style.configure("TEntry", fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg)
    style.configure("TSpinbox", fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg)
    style.configure(
        "TButton",
        font=("Helvetica", button_font_size),
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
    style.configure("Action.TButton", font=("Helvetica", button_font_size, "bold"), background=button_bg, foreground=fg, padding=max(6, button_font_size // 1))
    style.map("Action.TButton",
        background=[('active', button_active), ('pressed', button_active), ('!disabled', button_bg)],
        foreground=[('disabled', '#888888'), ('!disabled', fg)]
    )
    style.configure("Dialog.TFrame", background=frame_bg)
    style.configure("Dialog.TLabel", background=frame_bg, foreground=fg)
    style.configure("Dialog.TButton", font=("Helvetica", button_font_size), background=button_bg, foreground=fg)
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
    style.configure(
        "Treeview",
        background=text_bg,
        fieldbackground=text_bg,
        foreground=fg,
        font=("Helvetica", table_font_size),
        rowheight=max(24, int(table_font_size * 2.8)),
    )
    style.map("Treeview", background=[('selected', selected_bg)], foreground=[('selected', selected_fg)])
    style.configure(
        "Treeview.Heading",
        background=heading_bg,
        foreground=heading_fg,
        relief="raised",
        font=("Helvetica", table_font_size, "bold"),
        padding=(8, 10),
    )
    style.map("Treeview.Heading",
        background=[('active', heading_bg), ('pressed', heading_bg)],
        foreground=[('active', heading_fg), ('pressed', heading_fg)]
    )
    style.configure("Horizontal.TScrollbar", background=frame_bg)
    style.configure("Vertical.TScrollbar", background=frame_bg)

    if output_widget is not None:
        try:
            output_widget.configure(bg=text_bg, fg=fg, insertbackground=fg, font=("Courier", output_font_size))
        except tk.TclError:
            pass

    if status_label is not None:
        try:
            status_label.configure(background=frame_bg, foreground=status_fg)
        except tk.TclError:
            pass

    if tree is not None:
        try:
            tree.tag_configure("has_commits", background=tree_tag_has)
            tree.tag_configure("clean", background=tree_tag_clean)
        except tk.TclError:
            pass

    return colors
