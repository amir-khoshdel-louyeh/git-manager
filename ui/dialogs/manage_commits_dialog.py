"""Unified dialog for Reset and Delete commits (pushed + local_commit)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext
from pathlib import Path
from typing import Optional

from core.git_operations import GitManagerError, GitOperations


def _get_commit_log(repo: Path, ref: str, limit: int = 15) -> list[str]:
    """Return list of 'hash date subject' lines for preview."""
    try:
        out = GitOperations.run_git(
            ["log", ref, f"-n{limit}", "--date=short", "--pretty=format:%h %ad %s"],
            cwd=repo,
        )
        return [l for l in out.splitlines() if l.strip()]
    except GitManagerError:
        return []


def _get_commit_count(repo: Path, ref: str) -> int:
    try:
        out = GitOperations.run_git(["rev-list", "--count", ref], cwd=repo)
        return int(out.strip() or "0")
    except GitManagerError:
        return 0


class ManageCommitsDialog(tk.Toplevel):
    """Common box for Reset and Delete (pushed + local_commit)."""

    def __init__(
        self,
        parent: tk.Tk,
        repo_path: Path,
        repo_name: str,
        base_branch: str,
        current_branch: str,
        local_exists: bool,
        pending_count: int,
        theme_mode: str = "light",
    ) -> None:
        super().__init__(parent)
        self.repo_path = repo_path
        self.repo_name = repo_name
        self.base_branch = base_branch
        self.current_branch = current_branch
        self.local_exists = local_exists
        self.pending_count = pending_count
        self.theme_mode = theme_mode
        self.result: Optional[dict] = None

        self.title(f"Manage commits — {repo_name}")
        self.geometry("780x720")
        self.minsize(680, 580)
        self.transient(parent)
        self.grab_set()

        dialog_bg = "#1f242a" if theme_mode == "dark" else "#f0f0f0"
        self.configure(bg=dialog_bg)

        header = ttk.Frame(self, style="Dialog.TFrame", padding=(20, 12, 20, 8))
        header.pack(fill=tk.X)
        info = f"Base: {base_branch or '(none)'}  •  Current: {current_branch}  •  Pending: {pending_count}"
        ttk.Label(header, text=info, font=("Helvetica", 9, "bold"), style="Dialog.TLabel").pack(anchor=tk.W)
        if local_exists:
            ttk.Label(header, text="local_commit exists", font=("Helvetica", 8), style="Dialog.TLabel").pack(anchor=tk.W)
        ttk.Separator(self, orient="horizontal").pack(fill=tk.X, padx=20, pady=8)

        # Mode selection
        self.mode_var = tk.StringVar(value="reset")
        mode_frame = ttk.Frame(self, style="Dialog.TFrame", padding=(20, 0, 20, 8))
        mode_frame.pack(fill=tk.X)
        ttk.Label(mode_frame, text="Operation:", font=("Helvetica", 10, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, pady=(0, 6))
        ttk.Radiobutton(mode_frame, text="Reset to target (soft/mixed/hard)", variable=self.mode_var, value="reset", command=self._on_mode_change, style="Dialog.TRadiobutton").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="Delete commits (pushed + local_commit)", variable=self.mode_var, value="delete", command=self._on_mode_change, style="Dialog.TRadiobutton").pack(anchor=tk.W, pady=(4, 0))

        # Container for mode-specific UI
        self.container = ttk.Frame(self, style="Dialog.TFrame")
        self.container.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)

        # --- Reset mode frame ---
        self.reset_frame = ttk.Frame(self.container, style="Dialog.TFrame")
        ttk.Label(self.reset_frame, text="Reset target commit or ref:", font=("Helvetica", 10, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, pady=(4, 4))
        ttk.Label(self.reset_frame, text="Example: HEAD~2 , abc1234 , origin/main , main~5", font=("Helvetica", 8), style="Dialog.TLabel").pack(anchor=tk.W)
        self.target_var = tk.StringVar(value="")
        entry_row = ttk.Frame(self.reset_frame, style="Dialog.TFrame")
        entry_row.pack(fill=tk.X, pady=(6, 8))
        self.target_entry = ttk.Entry(entry_row, textvariable=self.target_var, style="Dialog.TEntry")
        self.target_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(entry_row, text="HEAD~1", width=8, command=lambda: self.target_var.set("HEAD~1")).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(self.reset_frame, text="Reset type:", font=("Helvetica", 10, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, pady=(8, 4))
        self.reset_type = tk.StringVar(value="hard")
        types_frame = ttk.Frame(self.reset_frame, style="Dialog.TFrame")
        types_frame.pack(fill=tk.X)
        for t in ("hard", "mixed", "soft"):
            ttk.Radiobutton(types_frame, text=t.capitalize(), variable=self.reset_type, value=t, style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=6)
        # Quick recent log preview for reset target help
        ttk.Label(self.reset_frame, text="Recent commits on current branch:", font=("Helvetica", 9), style="Dialog.TLabel").pack(anchor=tk.W, pady=(12, 4))
        self.recent_text = scrolledtext.ScrolledText(self.reset_frame, height=6, font=("Courier", 9), wrap=tk.NONE)
        self.recent_text.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self.recent_text.configure(state="disabled")
        self._load_recent()

        # --- Delete mode frame ---
        self.delete_frame = ttk.Frame(self.container, style="Dialog.TFrame")
        ttk.Label(self.delete_frame, text="Delete last N commits from a branch", font=("Helvetica", 10, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, pady=(4, 4))
        # Branch selector
        branch_row = ttk.Frame(self.delete_frame, style="Dialog.TFrame")
        branch_row.pack(fill=tk.X, pady=6)
        ttk.Label(branch_row, text="Branch:", style="Dialog.TLabel").pack(side=tk.LEFT)
        branches = []
        if base_branch:
            branches.append(base_branch)
        if local_exists:
            branches.append("local_commit")
        if current_branch not in branches and current_branch not in ("HEAD", ""):
            branches.append(current_branch)
        if not branches:
            branches = [current_branch or "HEAD"]
        self.delete_branch_var = tk.StringVar(value=branches[0])
        self.branch_combo = ttk.Combobox(branch_row, textvariable=self.delete_branch_var, values=branches, width=22, state="readonly")
        self.branch_combo.pack(side=tk.LEFT, padx=(8, 12))
        self.branch_combo.bind("<<ComboboxSelected>>", lambda e: self._update_delete_preview())
        # Count
        ttk.Label(branch_row, text="Count:", style="Dialog.TLabel").pack(side=tk.LEFT)
        self.delete_count_var = tk.StringVar(value="1")
        self.count_spin = ttk.Spinbox(branch_row, from_=1, to=20, textvariable=self.delete_count_var, width=5, command=self._update_delete_preview)
        self.count_spin.pack(side=tk.LEFT, padx=(8, 0))
        self.delete_count_var.trace_add("write", lambda *_: self._on_count_change())

        ttk.Label(self.delete_frame, text="Reset type:", font=("Helvetica", 9, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, pady=(8, 2))
        self.delete_type = tk.StringVar(value="hard")
        dtype_frame = ttk.Frame(self.delete_frame, style="Dialog.TFrame")
        dtype_frame.pack(fill=tk.X)
        for t in ("hard", "mixed", "soft"):
            ttk.Radiobutton(dtype_frame, text=t.capitalize(), variable=self.delete_type, value=t, style="Dialog.TRadiobutton").pack(side=tk.LEFT, padx=6)

        self.force_push_var = tk.BooleanVar(value=False)
        self.force_check = ttk.Checkbutton(self.delete_frame, text="Force push to origin after delete (for pushed commits)", variable=self.force_push_var, style="Dialog.TCheckbutton")
        self.force_check.pack(anchor=tk.W, pady=(8, 4))
        ttk.Label(self.delete_frame, text="• Pushed = already on origin (needs force push)\n• Local = pending on local_commit (no push)", font=("Helvetica", 8), style="Dialog.TLabel").pack(anchor=tk.W)

        # Preview area
        ttk.Label(self.delete_frame, text="Preview (will be deleted):", font=("Helvetica", 9, "bold"), style="Dialog.TLabel").pack(anchor=tk.W, pady=(8, 4))
        self.delete_preview = scrolledtext.ScrolledText(self.delete_frame, height=8, font=("Courier", 9), wrap=tk.NONE)
        self.delete_preview.pack(fill=tk.BOTH, expand=True)
        self.delete_preview.configure(state="disabled")
        self._update_delete_preview()

        # Show initial mode
        self._on_mode_change()

        # Buttons
        button_frame = ttk.Frame(self, style="Dialog.TFrame", padding=12)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(button_frame, text="Execute", command=self._on_ok, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel, style="Dialog.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview", command=self._on_preview).pack(side=tk.RIGHT, padx=5)

        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _load_recent(self) -> None:
        lines = _get_commit_log(self.repo_path, "HEAD", limit=10)
        self.recent_text.configure(state="normal")
        self.recent_text.delete("1.0", tk.END)
        if lines:
            self.recent_text.insert(tk.END, "\n".join(lines))
        else:
            self.recent_text.insert(tk.END, "(no commits)")
        self.recent_text.configure(state="disabled")

    def _on_mode_change(self) -> None:
        for w in self.container.winfo_children():
            w.pack_forget()
        if self.mode_var.get() == "reset":
            self.reset_frame.pack(fill=tk.BOTH, expand=True)
        else:
            self.delete_frame.pack(fill=tk.BOTH, expand=True)

    def _on_count_change(self) -> None:
        # Debounce preview
        self.after(300, self._update_delete_preview)

    def _update_delete_preview(self) -> None:
        branch = self.delete_branch_var.get().strip() or self.current_branch
        try:
            count = max(1, min(50, int(self.delete_count_var.get().strip() or "1")))
        except ValueError:
            count = 1
        # Update spinbox limit based on branch
        lines = _get_commit_log(self.repo_path, branch, limit=count)
        self.delete_preview.configure(state="normal")
        self.delete_preview.delete("1.0", tk.END)
        if lines:
            # Show exactly count commits that would be removed (most recent)
            preview_lines = lines[:count]
            self.delete_preview.insert(tk.END, f"Will delete {len(preview_lines)} commit(s) from {branch}:\n")
            self.delete_preview.insert(tk.END, "—" * 60 + "\n")
            for l in preview_lines:
                self.delete_preview.insert(tk.END, l + "\n")
            if len(lines) < count:
                self.delete_preview.insert(tk.END, f"\n⚠️ Only {len(lines)} commits available on {branch}\n")
        else:
            self.delete_preview.insert(tk.END, f"(no commits on {branch})")
        self.delete_preview.configure(state="disabled")
        # Auto-toggle force push hint
        if branch == self.base_branch:
            self.force_push_var.set(True)
        else:
            # local_commit deletion does not need push
            if branch == "local_commit":
                self.force_push_var.set(False)

    def _on_preview(self) -> None:
        if self.mode_var.get() == "reset":
            target = self.target_var.get().strip()
            if not target:
                messagebox.showerror("Target required", "Enter a target.", parent=self)
                return
            try:
                log = GitOperations.run_git(["log", "--oneline", "-n5", target], cwd=self.repo_path)
                messagebox.showinfo("Preview", f"Target {target} recent:\n{log}", parent=self)
            except GitManagerError as exc:
                messagebox.showerror("Preview failed", str(exc), parent=self)
        else:
            self._update_delete_preview()

    def _on_ok(self) -> None:
        if self.mode_var.get() == "reset":
            target = self.target_var.get().strip()
            if not target:
                messagebox.showerror("Target required", "Please enter a commit hash or ref to reset to.", parent=self)
                return
            self.result = {"mode": "reset", "target": target, "type": self.reset_type.get()}
            self.destroy()
        else:
            branch = self.delete_branch_var.get().strip()
            if not branch:
                messagebox.showerror("Branch required", "Select a branch.", parent=self)
                return
            try:
                count = int(self.delete_count_var.get().strip())
                if count < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid count", "Enter a valid number >=1.", parent=self)
                return
            # Verify count does not exceed available
            avail = _get_commit_count(self.repo_path, branch)
            if avail == 0:
                messagebox.showerror("No commits", f"Branch {branch} has no commits.", parent=self)
                return
            if count > avail:
                if not messagebox.askyesno("Count exceeds", f"Branch {branch} has only {avail} commits. Delete all {avail}?", parent=self):
                    return
                count = avail
            self.result = {
                "mode": "delete",
                "branch": branch,
                "count": count,
                "type": self.delete_type.get(),
                "force_push": bool(self.force_push_var.get()),
            }
            self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
