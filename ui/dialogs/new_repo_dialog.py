"""New Repository dialog: clone from URL + setup suggestions.

Opened from Settings ("New repositories" → "Open…") so the Settings
dialog itself stays compact. Creates repos inside the base directory and
onboards them (base branch + local_commit) via core.repo_factory.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

from core.git_operations import GitManagerError
from core.repo_factory import clone_repo, derive_folder_name, find_pending_setups, setup_new_repo


class NewRepoDialog(tk.Toplevel):
    """Separate window for adding/onboarding repositories."""

    def __init__(
        self,
        parent: tk.Misc,
        base_directory: str,
        default_branch: str = "main",
        theme_mode: str = "light",
    ) -> None:
        super().__init__(parent)
        self.title("New Repository")
        self.resizable(True, True)
        self.minsize(560, 480)
        self.theme_mode = theme_mode
        self.base_dir = base_directory
        self.changed = False  # True when something was cloned/set up

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        self.transient(parent)
        self.grab_set()

        # --- Clone section -------------------------------------------------
        clone_frame = ttk.LabelFrame(self, text="Clone from URL", style="Dialog.TLabelframe")
        clone_frame.pack(fill=tk.X, padx=20, pady=(16, 8))

        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar()
        self.branch_var = tk.StringVar(value=default_branch or "main")

        url_row = ttk.Frame(clone_frame, style="Dialog.TFrame")
        url_row.pack(fill=tk.X, padx=12, pady=(12, 4))
        ttk.Label(url_row, text="URL:", style="Dialog.TLabel").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_row, textvariable=self.url_var, width=52, style="Dialog.TEntry")
        self.url_entry.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)
        self.url_entry.bind("<KeyRelease>", self._on_url_changed)

        folder_row = ttk.Frame(clone_frame, style="Dialog.TFrame")
        folder_row.pack(fill=tk.X, padx=12, pady=4)
        ttk.Label(folder_row, text="Folder:", style="Dialog.TLabel").pack(side=tk.LEFT)
        ttk.Entry(folder_row, textvariable=self.folder_var, width=30, style="Dialog.TEntry").pack(
            side=tk.LEFT, padx=(8, 16)
        )
        ttk.Label(folder_row, text="Base:", style="Dialog.TLabel").pack(side=tk.LEFT)
        ttk.Entry(folder_row, textvariable=self.branch_var, width=12, style="Dialog.TEntry").pack(
            side=tk.LEFT, padx=(8, 0)
        )

        btn_row = ttk.Frame(clone_frame, style="Dialog.TFrame")
        btn_row.pack(fill=tk.X, padx=12, pady=(4, 12))
        ttk.Label(
            btn_row,
            text=f"Clones into: {base_directory}",
            font=("Helvetica", 8, "italic"),
            style="Dialog.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Clone", command=self._on_clone, style="Dialog.TButton", width=12).pack(
            side=tk.RIGHT
        )

        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, style="Dialog.TLabel").pack(
            anchor=tk.W, padx=20
        )

        # --- Suggestions section -------------------------------------------
        sugg_frame = ttk.LabelFrame(
            self, text="Suggestions – repos you added manually", style="Dialog.TLabelframe"
        )
        sugg_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)
        ttk.Label(
            sugg_frame,
            text="If you cloned something via terminal, it shows up here. Pick it to set up base + local_commit:",
            font=("Helvetica", 9, "italic"),
            style="Dialog.TLabel",
            wraplength=500,
        ).pack(anchor=tk.W, padx=12, pady=(8, 4))

        list_container = ttk.Frame(sugg_frame, style="Dialog.TFrame")
        list_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        self.sugg_tree = ttk.Treeview(
            list_container, columns=("info",), show="tree headings", selectmode="browse", height=8
        )
        self.sugg_tree.heading("#0", text="Repository")
        self.sugg_tree.heading("info", text="Status")
        self.sugg_tree.column("#0", width=180)
        self.sugg_tree.column("info", width=320, anchor=tk.W)
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.sugg_tree.yview)
        self.sugg_tree.configure(yscrollcommand=scrollbar.set)
        self.sugg_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        sugg_btns = ttk.Frame(sugg_frame, style="Dialog.TFrame")
        sugg_btns.pack(fill=tk.X, padx=12, pady=(4, 12))
        ttk.Button(sugg_btns, text="Refresh", command=self._reload, style="Dialog.TButton").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(
            sugg_btns, text="Setup selected", command=self._on_setup_selected, style="Dialog.TButton"
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(sugg_btns, text="Setup all", command=self._on_setup_all, style="Dialog.TButton").pack(
            side=tk.LEFT, padx=6
        )

        bottom = ttk.Frame(self, style="Dialog.TFrame")
        bottom.pack(pady=(0, 16))
        ttk.Button(bottom, text="Close", command=self._on_close, style="Dialog.TButton", width=12).pack()

        self.bind("<Escape>", lambda e: self._on_close())

        self._pending: list = []
        self._reload()

        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
        try:
            self.url_entry.focus_set()
        except tk.TclError:
            pass

    # --- helpers ---------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.update_idletasks()

    def _on_url_changed(self, event: Optional[tk.Event] = None) -> None:  # type: ignore
        if self.folder_var.get().strip():
            return  # user typed a custom folder name; don't overwrite
        try:
            self.folder_var.set(derive_folder_name(self.url_var.get()))
        except GitManagerError:
            pass

    def _on_clone(self) -> None:
        url = self.url_var.get().strip()
        folder = self.folder_var.get().strip()
        branch = self.branch_var.get().strip() or "main"
        if not url:
            messagebox.showerror("URL required", "Please enter a repository URL.", parent=self)
            return
        self._set_status(f"⏳ Cloning {url} …")
        try:
            dest = clone_repo(Path(self.base_dir), url, folder or None, branch)
        except GitManagerError as exc:
            self._set_status("")
            messagebox.showerror("Clone failed", str(exc), parent=self)
            return
        self.changed = True
        self._set_status(f"✅ Cloned to {dest.name} with base '{branch}' + local_commit.")
        self.url_var.set("")
        self.folder_var.set("")
        self._reload()

    def _reload(self) -> None:
        for item in self.sugg_tree.get_children():
            self.sugg_tree.delete(item)
        try:
            self._pending = find_pending_setups(Path(self.base_dir))
        except Exception:
            self._pending = []
        if not self._pending:
            self.sugg_tree.insert("", tk.END, text="(all set — nothing to suggest)", values=("",))
            return
        for item in self._pending:
            detail = f"{item.reason} — on {item.current_branch}"
            self.sugg_tree.insert("", tk.END, iid=item.name, text=item.name, values=(detail,))

    def _on_setup_selected(self) -> None:
        sel = self.sugg_tree.selection()
        if not sel or not self._pending:
            messagebox.showinfo("Select repository", "Please select a repository first.", parent=self)
            return
        name = sel[0]
        item = next((p for p in self._pending if p.name == name), None)
        if item is None:
            return
        branch = self.branch_var.get().strip() or item.base_branch or "main"
        if item.base_branch and item.base_branch in {"main", "master"}:
            branch = item.base_branch  # respect detected real base
        try:
            base = setup_new_repo(item.path, branch)
        except GitManagerError as exc:
            messagebox.showerror("Setup failed", str(exc), parent=self)
            return
        self.changed = True
        self._set_status(f"✅ {item.name}: base '{base}' + local_commit ready.")
        self._reload()

    def _on_setup_all(self) -> None:
        if not self._pending:
            return
        done, failed = 0, 0
        branch_default = self.branch_var.get().strip() or "main"
        for item in list(self._pending):
            branch = item.base_branch if item.base_branch in {"main", "master"} else branch_default
            try:
                setup_new_repo(item.path, branch)
                done += 1
            except GitManagerError:
                failed += 1
        if done:
            self.changed = True
        self._set_status(f"✅ Setup complete: {done} ok, {failed} failed.")
        self._reload()

    def _on_close(self) -> None:
        self.destroy()
