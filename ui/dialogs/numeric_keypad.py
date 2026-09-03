"""Numeric keypad dialog for commit count selection."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional


class NumericKeypadDialog(tk.Toplevel):
    """Custom dialog with numeric keypad for entering number of commits."""

    def __init__(self, parent: tk.Tk, title: str, prompt: str, minvalue: int = 1, maxvalue: int = 100, theme_mode: str = "light") -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[int] = None
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.theme_mode = theme_mode

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        # Make it modal
        self.transient(parent)
        self.grab_set()

        # Prompt label
        ttk.Label(self, text=prompt, font=("Helvetica", 11), justify=tk.CENTER, style="Dialog.TLabel").pack(pady=10, padx=20)

        # Display value
        self.value_var = tk.StringVar(value="0")
        entry_bg = "#1e2228" if theme_mode == "dark" else "#f1f5f9"
        entry_fg = "#e8e8e8" if theme_mode == "dark" else "#111827"
        display = tk.Entry(
            self,
            textvariable=self.value_var,
            font=("Helvetica", 14, "bold"),
            width=15,
            justify=tk.CENTER,
            state="readonly",
            bg=entry_bg,
            fg=entry_fg,
            readonlybackground=entry_bg,
            disabledforeground=entry_fg,
            relief=tk.SOLID,
            bd=1,
        )
        display.pack(pady=10, padx=20)

        # Numeric keypad
        keypad_frame = ttk.Frame(self, style="Dialog.TFrame")
        keypad_frame.pack(pady=10, padx=20)

        buttons = [
            ["7", "8", "9"],
            ["4", "5", "6"],
            ["1", "2", "3"],
            ["0", "C", "⌫"],
        ]

        for row in buttons:
            row_frame = ttk.Frame(keypad_frame)
            row_frame.pack()
            for btn_text in row:
                btn = ttk.Button(row_frame, text=btn_text, width=5, command=lambda t=btn_text: self._on_key(t))
                btn.pack(side=tk.LEFT, padx=2, pady=2)

        # OK and Cancel buttons
        button_frame = ttk.Frame(self, style="Dialog.TFrame")
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="OK", command=self._on_ok, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)

        # Bind keyboard events
        self.bind("<Key-0>", lambda e: self._on_key("0"))
        self.bind("<Key-1>", lambda e: self._on_key("1"))
        self.bind("<Key-2>", lambda e: self._on_key("2"))
        self.bind("<Key-3>", lambda e: self._on_key("3"))
        self.bind("<Key-4>", lambda e: self._on_key("4"))
        self.bind("<Key-5>", lambda e: self._on_key("5"))
        self.bind("<Key-6>", lambda e: self._on_key("6"))
        self.bind("<Key-7>", lambda e: self._on_key("7"))
        self.bind("<Key-8>", lambda e: self._on_key("8"))
        self.bind("<Key-9>", lambda e: self._on_key("9"))
        self.bind("<BackSpace>", lambda e: self._on_key("⌫"))
        self.bind("<Delete>", lambda e: self._on_key("C"))
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _on_key(self, key: str) -> None:
        """Handle keypad button press."""
        current = self.value_var.get()

        if key == "C":  # Clear
            self.value_var.set("0")
        elif key == "⌫":  # Backspace
            if len(current) > 1:
                self.value_var.set(current[:-1])
            else:
                self.value_var.set("0")
        else:  # Digit
            if current == "0":
                self.value_var.set(key)
            else:
                new_val = current + key
                if int(new_val) <= self.maxvalue:
                    self.value_var.set(new_val)

    def _on_ok(self) -> None:
        """Handle OK button."""
        try:
            value = int(self.value_var.get())
            if self.minvalue <= value <= self.maxvalue:
                self.result = value
                self.destroy()
            else:
                messagebox.showerror("Invalid Input", f"Please enter a number between {self.minvalue} and {self.maxvalue}")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number")

    def _on_cancel(self) -> None:
        """Handle Cancel button."""
        self.result = None
        self.destroy()
