"""Theme handling for Git Manager GUI.

The palettes and ttk styles live here. All paddings, row heights and widget
metrics are expressed in logical pixels and passed through
:func:`ui.scaling.px`, while point-sized fonts follow ``tk scaling`` set in
:func:`ui.scaling.init`. That is what keeps the interface identical on a 13"
laptop and a 24" monitor.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from ui.scaling import px

FONT_FAMILY = "Helvetica"
MONO_FAMILY = "Courier"

THEMES = {
    "dark": {
        "bg": "#0f1318",
        "header_bg": "#151b22",
        "sidebar_bg": "#151b22",
        "frame_bg": "#1a2129",
        "text_bg": "#11171d",
        "fg": "#e6eaf0",
        "muted_fg": "#8d99a8",
        "border": "#2a3540",
        "button_bg": "#232c36",
        "button_active": "#2f3b48",
        "primary": "#2f6fed",
        "primary_active": "#255cc9",
        "primary_fg": "#ffffff",
        "danger": "#7f2a2a",
        "danger_active": "#9b3434",
        "danger_fg": "#ffdada",
        "heading_bg": "#202832",
        "heading_fg": "#eef2f7",
        "entry_bg": "#121920",
        "entry_fg": "#e6eaf0",
        "status_fg": "#8ab4f8",
        "ok_fg": "#7ee2a8",
        "err_fg": "#ff8f8f",
        "warn_fg": "#ffcf70",
        "tree_tag_has": "#2a2618",
        "tree_tag_clean": "#171e25",
        "selected_bg": "#2b4b7c",
        "selected_fg": "#ffffff",
        "canvas_bg": "#0d1117",
    },
    "light": {
        "bg": "#eef1f5",
        "header_bg": "#ffffff",
        "sidebar_bg": "#ffffff",
        "frame_bg": "#ffffff",
        "text_bg": "#ffffff",
        "fg": "#1f2937",
        "muted_fg": "#64748b",
        "border": "#dbe2ea",
        "button_bg": "#f1f5f9",
        "button_active": "#e2e8f0",
        "primary": "#2563eb",
        "primary_active": "#1d4ed8",
        "primary_fg": "#ffffff",
        "danger": "#dc2626",
        "danger_active": "#b91c1c",
        "danger_fg": "#ffffff",
        "heading_bg": "#f4f7fa",
        "heading_fg": "#0f172a",
        "entry_bg": "#f8fafc",
        "entry_fg": "#111827",
        "status_fg": "#1d4ed8",
        "ok_fg": "#15803d",
        "err_fg": "#b91c1c",
        "warn_fg": "#b45309",
        "tree_tag_has": "#fff8e1",
        "tree_tag_clean": "#ffffff",
        "selected_bg": "#dbeafe",
        "selected_fg": "#0f172a",
        "canvas_bg": "#ffffff",
    },
}


def get_theme(mode: str) -> dict[str, str]:
    """Return theme dict for mode, defaulting to light."""
    return THEMES.get(mode, THEMES["light"])


def _configure_named_fonts(body_size: int, heading_size: int) -> None:
    """Keep Tk's built-in fonts (menus, message boxes) in step with the app."""
    specs = {
        "TkDefaultFont": (body_size, "normal"),
        "TkTextFont": (body_size, "normal"),
        "TkMenuFont": (body_size, "normal"),
        "TkHeadingFont": (heading_size, "bold"),
    }
    for name, (size, weight) in specs.items():
        try:
            font = tkfont.nametofont(name)
            font.configure(family=FONT_FAMILY, size=max(1, size), weight=weight)
        except (tk.TclError, ValueError):
            pass


def _flat_button(style: ttk.Style, name: str, bg: str, fg: str, active: str,
                 *, bold: bool = False, size: int = 10) -> None:
    """Configure a flat, full-width-friendly button style."""
    style.configure(
        name,
        background=bg,
        foreground=fg,
        font=(FONT_FAMILY, size, "bold") if bold else (FONT_FAMILY, size),
        borderwidth=0,
        relief="flat",
        focusthickness=0,
        padding=(px(12), px(7)),
        anchor=tk.W,
    )
    style.map(
        name,
        background=[("pressed", active), ("active", active), ("!disabled", bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", fg)],
        relief=[("pressed", "flat"), ("!disabled", "flat")],
    )


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
    header_bg = colors["header_bg"]
    sidebar_bg = colors["sidebar_bg"]
    frame_bg = colors["frame_bg"]
    text_bg = colors["text_bg"]
    fg = colors["fg"]
    muted = colors["muted_fg"]
    border = colors["border"]
    button_bg = colors["button_bg"]
    button_active = colors["button_active"]
    primary = colors["primary"]
    primary_active = colors["primary_active"]
    primary_fg = colors["primary_fg"]
    danger = colors["danger"]
    danger_active = colors["danger_active"]
    danger_fg = colors["danger_fg"]
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

    # One theme everywhere keeps the widgets identical across platforms.
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    body_size = max(9, int(button_font_size))
    _configure_named_fonts(body_size, max(10, int(table_font_size) + 1))

    # --- base widget styles ------------------------------------------------
    style.configure("TFrame", background=frame_bg)
    style.configure("TLabel", background=frame_bg, foreground=fg, font=(FONT_FAMILY, body_size))
    style.configure("TCheckbutton", background=frame_bg, foreground=fg, font=(FONT_FAMILY, body_size))
    style.configure("TRadiobutton", background=frame_bg, foreground=fg, font=(FONT_FAMILY, body_size))
    style.configure("TEntry", fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg,
                    insertcolor=fg, padding=(px(6), px(4)))
    style.configure("TSpinbox", fieldbackground=entry_bg, foreground=entry_fg, background=entry_bg,
                    insertcolor=fg, arrowcolor=fg, padding=(px(6), px(4)))
    style.configure(
        "TButton",
        font=(FONT_FAMILY, body_size),
        background=button_bg,
        foreground=fg,
        borderwidth=max(1, px(1)),
        relief="flat",
        focusthickness=px(2),
        focuscolor=primary,
        padding=(px(12), px(6)),
    )
    style.map(
        "TButton",
        background=[("pressed", button_active), ("active", button_active), ("!disabled", button_bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", fg)],
        relief=[("pressed", "flat"), ("!disabled", "flat")],
    )

    # --- app chrome --------------------------------------------------------
    style.configure("App.TFrame", background=bg)
    style.configure("Header.TFrame", background=header_bg)
    style.configure("Sidebar.TFrame", background=sidebar_bg)
    style.configure("Card.TFrame", background=frame_bg, relief="solid", borderwidth=max(1, px(1)))
    style.configure("CardHeader.TFrame", background=frame_bg)
    style.configure("CardBody.TFrame", background=frame_bg)
    style.configure("Status.TFrame", background=header_bg)
    style.configure("Footer.TFrame", background=sidebar_bg)

    style.configure("Title.TLabel", background=header_bg, foreground=fg,
                    font=(FONT_FAMILY, max(body_size + 7, 15), "bold"))
    style.configure("Subtitle.TLabel", background=header_bg, foreground=muted,
                    font=(FONT_FAMILY, max(body_size - 1, 8)))
    style.configure("Chip.TLabel", background=button_bg, foreground=muted,
                    font=(FONT_FAMILY, max(body_size - 1, 8), "bold"),
                    padding=(px(10), px(4)))
    style.configure("CardTitle.TLabel", background=frame_bg, foreground=fg,
                    font=(FONT_FAMILY, max(body_size + 1, 11), "bold"))
    style.configure("CardMuted.TLabel", background=frame_bg, foreground=muted,
                    font=(FONT_FAMILY, max(body_size - 1, 8)))
    style.configure("Card.TLabel", background=frame_bg, foreground=fg,
                    font=(FONT_FAMILY, body_size))
    style.configure("SidebarSection.TLabel", background=sidebar_bg, foreground=muted,
                    font=(FONT_FAMILY, max(body_size - 3, 7), "bold"), padding=(px(10), 0))
    style.configure("SidebarFooter.TLabel", background=sidebar_bg, foreground=muted,
                    font=(FONT_FAMILY, max(body_size - 2, 8)))
    style.configure("Status.TLabel", background=header_bg, foreground=status_fg,
                    font=(FONT_FAMILY, max(body_size - 1, 8), "bold"))
    style.configure("StatusMuted.TLabel", background=header_bg, foreground=muted,
                    font=(FONT_FAMILY, max(body_size - 2, 8)))

    # Sidebar navigation buttons: flat, roomy, left aligned, full width.
    _flat_button(style, "Sidebar.TButton", sidebar_bg, fg, button_bg, size=body_size)
    style.configure("Sidebar.TButton", padding=(px(10), px(8)))
    _flat_button(style, "SidebarPrimary.TButton", primary, primary_fg, primary_active,
                 bold=True, size=body_size)
    style.configure("SidebarPrimary.TButton", padding=(px(10), px(8)))
    _flat_button(style, "Primary.TButton", primary, primary_fg, primary_active,
                 bold=True, size=body_size)
    _flat_button(style, "Danger.TButton", danger, danger_fg, danger_active,
                 bold=True, size=body_size)
    _flat_button(style, "Ghost.TButton", button_bg, fg, button_active, size=body_size)

    # --- dialog styles -----------------------------------------------------
    style.configure("Dialog.TFrame", background=frame_bg)
    style.configure("Dialog.TLabel", background=frame_bg, foreground=fg, font=(FONT_FAMILY, body_size))
    style.configure("DialogMuted.TLabel", background=frame_bg, foreground=muted,
                    font=(FONT_FAMILY, max(body_size - 1, 8)))
    style.configure("Dialog.TButton", font=(FONT_FAMILY, body_size, "bold"),
                    background=button_bg, foreground=fg, padding=(px(14), px(7)),
                    borderwidth=max(1, px(1)), relief="flat")
    style.map(
        "Dialog.TButton",
        background=[("pressed", button_active), ("active", button_active), ("!disabled", button_bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", fg)],
    )
    style.configure("DialogPrimary.TButton", font=(FONT_FAMILY, body_size, "bold"),
                    background=primary, foreground=primary_fg, padding=(px(14), px(7)),
                    borderwidth=0, relief="flat")
    style.map(
        "DialogPrimary.TButton",
        background=[("pressed", primary_active), ("active", primary_active), ("!disabled", primary)],
        foreground=[("disabled", "#c7d2fe"), ("!disabled", primary_fg)],
    )
    style.configure("Dialog.TEntry", fieldbackground=entry_bg, foreground=entry_fg,
                    background=entry_bg, insertcolor=fg, padding=(px(6), px(4)))
    style.configure("Dialog.TSpinbox", fieldbackground=entry_bg, foreground=entry_fg,
                    background=entry_bg, insertcolor=fg, arrowcolor=fg, padding=(px(6), px(4)))
    style.configure("Dialog.TLabelframe", background=frame_bg, foreground=fg,
                    borderwidth=max(1, px(1)), relief="solid", padding=px(8))
    style.configure("Dialog.TLabelframe.Label", background=frame_bg, foreground=muted,
                    font=(FONT_FAMILY, max(body_size - 1, 8), "bold"))
    style.configure("Dialog.TRadiobutton", background=frame_bg, foreground=fg,
                    font=(FONT_FAMILY, body_size))
    style.configure("Dialog.TCheckbutton", background=frame_bg, foreground=fg,
                    font=(FONT_FAMILY, body_size))

    for name in ("TCheckbutton", "TRadiobutton", "Dialog.TRadiobutton", "Dialog.TCheckbutton"):
        style.map(
            name,
            background=[("active", frame_bg), ("pressed", frame_bg), ("!disabled", frame_bg)],
            foreground=[("disabled", "#8a8f98"), ("!disabled", fg)],
            indicatorbackground=[("!disabled", entry_bg)],
            indicatorforeground=[("!disabled", fg)],
        )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", entry_bg), ("readonly", entry_bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", entry_fg)],
    )
    style.map(
        "Dialog.TEntry",
        fieldbackground=[("disabled", entry_bg), ("readonly", entry_bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", entry_fg)],
    )
    style.map(
        "TSpinbox",
        fieldbackground=[("disabled", entry_bg), ("readonly", entry_bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", entry_fg)],
    )
    style.map(
        "Dialog.TSpinbox",
        fieldbackground=[("disabled", entry_bg), ("readonly", entry_bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", entry_fg)],
    )

    style.configure("TCombobox", fieldbackground=entry_bg, foreground=entry_fg, background=button_bg,
                    arrowcolor=fg, selectbackground=selected_bg, selectforeground=selected_fg,
                    padding=(px(6), px(4)))
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", entry_bg), ("disabled", entry_bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", entry_fg)],
        background=[("active", button_active), ("pressed", button_active), ("!disabled", button_bg)],
        arrowcolor=[("disabled", "#8a8f98"), ("!disabled", fg)],
    )
    style.configure("TMenubutton", background=button_bg, foreground=fg, arrowcolor=fg,
                    padding=(px(10), px(5)))
    style.map(
        "TMenubutton",
        background=[("active", button_active), ("pressed", button_active), ("!disabled", button_bg)],
        foreground=[("disabled", "#8a8f98"), ("!disabled", fg)],
        arrowcolor=[("disabled", "#8a8f98"), ("!disabled", fg)],
    )
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", background=button_bg, foreground=fg,
                    font=(FONT_FAMILY, body_size), padding=(px(12), px(6)))
    style.map("TNotebook.Tab",
              background=[("selected", frame_bg), ("active", button_active)],
              foreground=[("selected", fg), ("!disabled", fg)])
    style.configure("TSeparator", background=border)
    style.configure("TPanedwindow", background=bg)
    style.configure("Sash", sashthickness=px(6), gripcount=0, background=bg)

    # --- repository table --------------------------------------------------
    style.configure(
        "Treeview",
        background=text_bg,
        fieldbackground=text_bg,
        foreground=fg,
        font=(FONT_FAMILY, table_font_size),
        rowheight=max(px(26), int(px(table_font_size * 2.5))),
        borderwidth=0,
        relief="flat",
    )
    style.map("Treeview", background=[("selected", selected_bg)], foreground=[("selected", selected_fg)])
    style.configure(
        "Treeview.Heading",
        background=heading_bg,
        foreground=heading_fg,
        relief="flat",
        font=(FONT_FAMILY, max(table_font_size - 1, 8), "bold"),
        padding=(px(8), px(7)),
        borderwidth=0,
    )
    style.map(
        "Treeview.Heading",
        background=[("active", button_active), ("pressed", button_active), ("!disabled", heading_bg)],
        foreground=[("active", heading_fg), ("pressed", heading_fg), ("!disabled", heading_fg)],
    )
    style.configure("Vertical.TScrollbar", background=button_bg, troughcolor=text_bg,
                    bordercolor=border, arrowcolor=muted, width=px(12))
    style.configure("Horizontal.TScrollbar", background=button_bg, troughcolor=text_bg,
                    bordercolor=border, arrowcolor=muted, width=px(12))
    style.map("Vertical.TScrollbar", background=[("active", button_active)])
    style.map("Horizontal.TScrollbar", background=[("active", button_active)])

    # Popup menus (OptionMenu) and combobox dropdown lists follow the theme too.
    try:
        root.option_add("*Menu.background", frame_bg)
        root.option_add("*Menu.foreground", fg)
        root.option_add("*Menu.font", (FONT_FAMILY, body_size))
        root.option_add("*Menu.activeBackground", selected_bg)
        root.option_add("*Menu.activeForeground", selected_fg)
        root.option_add("*Menu.disabledForeground", "#8a8f98")
        root.option_add("*Menu.selectColor", fg)
        root.option_add("*TCombobox*Listbox.background", entry_bg)
        root.option_add("*TCombobox*Listbox.foreground", entry_fg)
        root.option_add("*TCombobox*Listbox.font", (FONT_FAMILY, body_size))
        root.option_add("*TCombobox*Listbox.selectBackground", selected_bg)
        root.option_add("*TCombobox*Listbox.selectForeground", selected_fg)
        root.option_add("*Tooltip.background", heading_bg)
        root.option_add("*Tooltip.foreground", fg)
    except tk.TclError:
        pass

    if output_widget is not None:
        try:
            output_widget.configure(
                bg=text_bg,
                fg=fg,
                insertbackground=fg,
                selectbackground=selected_bg,
                selectforeground=selected_fg,
                font=(MONO_FAMILY, output_font_size),
                padx=px(10),
                pady=px(8),
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
            )
            output_widget.tag_configure("success", foreground=colors["ok_fg"])
            output_widget.tag_configure("error", foreground=colors["err_fg"])
            output_widget.tag_configure("warning", foreground=colors["warn_fg"])
            output_widget.tag_configure("muted", foreground=muted)
        except tk.TclError:
            pass

    if status_label is not None:
        try:
            status_label.configure(style="Status.TLabel", background=header_bg, foreground=status_fg)
        except tk.TclError:
            pass

    if tree is not None:
        try:
            tree.tag_configure("has_commits", background=tree_tag_has)
            tree.tag_configure("clean", background=tree_tag_clean)
        except tk.TclError:
            pass

    return colors
