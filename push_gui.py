#!/usr/bin/env python3
"""Standalone GUI for managing git repositories with proper OOP structure."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from git_operations import GitOperations, GitManagerError
from repo_state import RepoState
from branch_manager import BranchManager
from working_tree_manager import WorkingTreeManager
from git_config import GitConfig
from repo_scanner import RepoScanner


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def now_iso() -> str:
    """Return current time in ISO 8601 format."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S%z")


def now_display() -> str:
    """Return current time in human-readable format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %z")


class NumericKeypadDialog(tk.Toplevel):
    """Custom dialog with numeric keypad for entering number of commits."""
    
    def __init__(self, parent: tk.Tk, title: str, prompt: str, minvalue: int = 1, maxvalue: int = 100) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[int] = None
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        
        # Make it modal
        self.transient(parent)
        self.grab_set()
        
        # Prompt label
        ttk.Label(self, text=prompt, font=("Helvetica", 11), justify=tk.CENTER).pack(pady=10, padx=20)
        
        # Display value
        self.value_var = tk.StringVar(value="0")
        display = ttk.Entry(
            self,
            textvariable=self.value_var,
            font=("Helvetica", 14, "bold"),
            width=15,
            justify=tk.CENTER,
            state="readonly"
        )
        display.pack(pady=10, padx=20)
        
        # Numeric keypad
        keypad_frame = ttk.Frame(self)
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
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=5)
        
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

# ============================================================================
# GUI APPLICATION
# ============================================================================
DEFAULT_BASE_DIR = Path("/home/amir/GitHub")


class GitManagerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Git Manager - Repository Management Tool")
        self.root.configure(bg="#f0f0f0")

        self.base_var = tk.StringVar(value=str(DEFAULT_BASE_DIR))
        self.states: List[RepoState] = []

        self._build_layout()
        self.refresh_repos()
        self.switch_all_to_local_commit()
        
        # Register cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_layout(self) -> None:
        # Header frame with better styling
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X, padx=12, pady=12)

        ttk.Label(top, text="📁 Base directory:", font=("Helvetica", 11, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        entry = ttk.Entry(top, textvariable=self.base_var, width=70, font=("Helvetica", 10))
        entry.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="🔄 Refresh", command=self.refresh_repos).pack(side=tk.LEFT, padx=8)

        # Action buttons with better styling
        buttons = ttk.Frame(self.root, padding=8)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        
        style = ttk.Style()
        style.configure("Action.TButton", font=("Helvetica", 10, "bold"), padding=8)
        
        ttk.Button(buttons, text="🔀 Switch Branch", command=self.action_switch, style="Action.TButton").pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="👁 Preview Commits", command=self.action_preview, style="Action.TButton").pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="🚀 Move Commits", command=self.action_move, style="Action.TButton").pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="♻️ Restore local_commit", command=self.action_restore, style="Action.TButton").pack(side=tk.LEFT, padx=4)

        # Split main content into resizable panes
        paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        # Repository tree with improved styling
        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=1)
        ttk.Label(tree_frame, text="📊 Repositories", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        style.configure("Treeview", font=("Helvetica", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))
        tree_container = ttk.Frame(tree_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_container,
            columns=("name", "local", "commits", "branch", "base"),
            show="tree headings",
            selectmode="browse",
            height=12,
        )
        self.tree.heading("#0", text="")
        self.tree.heading("name", text="Repository")
        self.tree.heading("local", text="local_commit")
        self.tree.heading("commits", text="Commits")
        self.tree.heading("branch", text="Current Branch")
        self.tree.heading("base", text="Base Branch")
        self.tree.column("#0", width=30, stretch=False)
        self.tree.column("name", width=250, anchor=tk.W)
        self.tree.column("local", width=120, anchor=tk.CENTER)
        self.tree.column("commits", width=100, anchor=tk.CENTER)
        self.tree.column("branch", width=200, anchor=tk.W)
        self.tree.column("base", width=150, anchor=tk.W)
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Output pane with better styling
        output_frame = ttk.Frame(paned)
        paned.add(output_frame, weight=1)
        ttk.Label(output_frame, text="📝 Output", font=("Helvetica", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))
        output_container = ttk.Frame(output_frame)
        output_container.pack(fill=tk.BOTH, expand=True)
        self.output = scrolledtext.ScrolledText(
            output_container,
            height=12,
            state="disabled",
            font=("Courier", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            wrap=tk.WORD,
        )
        self.output.pack(fill=tk.BOTH, expand=True)

        # Status bar with better styling
        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(8, 4))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_var = tk.StringVar(value="✓ Ready")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            anchor=tk.W,
            font=("Helvetica", 9),
            foreground="#0066cc"
        )
        status_label.pack(fill=tk.X)

    def refresh_repos(self) -> None:
        base_dir = Path(self.base_var.get()).expanduser()
        try:
            states = RepoScanner.scan(base_dir)
        except GitManagerError as exc:
            messagebox.showerror("Error", str(exc))
            return

        self.states = states
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, state in enumerate(states, start=1):
            # Add visual indicators
            icon = "📦" if state.local_exists else "📁"
            tag = "has_commits" if state.commit_count > 0 else "clean"
            
            self.tree.insert(
                "",
                tk.END,
                iid=str(idx - 1),
                values=(
                    state.name,
                    "✓" if state.local_exists else "✗",
                    state.commit_count,
                    state.current_branch,
                    state.base_branch,
                ),
                text=icon,
                tags=(tag,)
            )
        
        # Configure tag colors
        self.tree.tag_configure("has_commits", background="#fff9e6")
        self.tree.tag_configure("clean", background="#f0f8ff")
        
        self.status_var.set(f"✓ Loaded {len(states)} repositories from {base_dir}")

    def switch_all_to_local_commit(self) -> None:
        """Switch all repositories to local_commit branch."""
        if not self.states:
            return
        
        self.append_output("🔄 Ensuring all repositories are on local_commit branch...\n")
        for state in self.states:
            try:
                if state.current_branch != "local_commit":
                    if state.local_exists:
                        BranchManager.checkout(state.path, "local_commit")
                        self.append_output(f"  ✓ {state.name}: switched to local_commit\n")
                    else:
                        # Create local_commit from base branch
                        BranchManager.switch_to_local_commit(state.path, state.base_branch)
                        self.append_output(f"  ✓ {state.name}: created and switched to local_commit\n")
                else:
                    self.append_output(f"  ✓ {state.name}: already on local_commit\n")
            except GitManagerError as exc:
                self.append_output(f"  ⚠️  {state.name}: {str(exc)}\n")
        self.append_output("✅ Branch check complete\n\n")
        self.refresh_repos()

    def on_closing(self) -> None:
        """Handle window close event."""
        self.switch_all_to_local_commit()
        self.root.destroy()

    def append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert(tk.END, text + "\n")
        self.output.configure(state="disabled")
        self.output.see(tk.END)
        self.root.update()  # Force GUI refresh to show updates in real-time

    # --- helpers ---------------------------------------------------------
    def _abort_in_progress_ops(self, repo: Path) -> None:
        git_dir = repo / ".git"
        if (git_dir / "MERGE_HEAD").exists():
            try:
                GitOperations.run_git(["merge", "--abort"], cwd=repo)
            except GitManagerError:
                self.append_output("⚠️  Could not abort merge cleanly; please resolve manually.")
        if (git_dir / "CHERRY_PICK_HEAD").exists():
            try:
                GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
            except GitManagerError:
                self.append_output("⚠️  Could not abort cherry-pick cleanly; please resolve manually.")
        if (git_dir / "rebase-merge").exists():
            try:
                GitOperations.run_git(["rebase", "--abort"], cwd=repo)
            except GitManagerError:
                self.append_output("⚠️  Could not abort rebase cleanly; please resolve manually.")

    def _choose_conflict_resolution(self, commit: str, conflicts: str) -> str:
        prompt = (
            f"Cherry-pick conflicts for {commit[:7]}\n\n"
            f"Conflicted files:\n{conflicts}\n\n"
            "Choose: 1) Keep base (ours)  2) Incoming (theirs)  3) Abort  4) Skip"
        )
        choice = simpledialog.askstring("Conflicts", prompt, parent=self.root)
        if not choice:
            raise GitManagerError("Conflict resolution cancelled")
        choice = choice.strip()
        if choice == "1":
            return "ours"
        if choice == "2":
            return "theirs"
        if choice == "3":
            return "abort"
        if choice == "4":
            return "skip"
        raise GitManagerError("Invalid conflict resolution choice")

    def _backup_local_commit(self, repo: Path) -> str:
        backup_name = f"backup_local_commit_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            GitOperations.run_git(["branch", backup_name, "local_commit"], cwd=repo)
            self.append_output(f"🛟 Created {backup_name} from local_commit before rewrite")
        except GitManagerError:
            self.append_output("⚠️  Failed to create backup branch; proceeding without backup")
        return backup_name

    def selected_state(self) -> Optional[RepoState]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select repository", "Please select a repository first.")
            return None
        idx = int(sel[0])
        if idx < 0 or idx >= len(self.states):
            return None
        return self.states[idx]

    def action_switch(self) -> None:
        state = self.selected_state()
        if not state:
            return
        try:
            GitConfig.ensure_identity(state.path)
            if state.current_branch == "local_commit":
                BranchManager.switch_to_base(state.path, state.base_branch)
                new_branch = state.base_branch
            else:
                BranchManager.switch_to_local_commit(state.path, state.base_branch)
                new_branch = "local_commit"
            self.append_output(f"Switched to {new_branch} in {state.name}")
            self.refresh_repos()
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")

    def action_preview(self) -> None:
        state = self.selected_state()
        if not state:
            return
        try:
            log = GitOperations.run_git(
                [
                    "log",
                    "--reverse",
                    "--no-decorate",
                    "--date=short",
                    "--pretty=format:  %h  %ad  %s",
                    f"{state.base_branch}..local_commit",
                ],
                cwd=state.path,
            )
            self.append_output(f"Commits for {state.name}:\n{log}\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")

    def action_move(self) -> None:
        state = self.selected_state()
        if not state:
            return
        repo = state.path
        try:
            GitConfig.ensure_identity(repo)
            if not GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "local_commit"], cwd=repo):
                raise GitManagerError("local_commit does not exist")
            pending = int(GitOperations.run_git(["rev-list", "--count", f"{state.base_branch}..local_commit"], cwd=repo).strip() or "0")
            if pending == 0:
                messagebox.showinfo("No commits", "No commits to move.")
                return

            dialog = NumericKeypadDialog(
                self.root,
                "Move commits",
                f"How many commits to move to {state.base_branch}?\n(1 to {pending})",
                minvalue=1,
                maxvalue=pending,
            )
            self.root.wait_window(dialog)
            num = dialog.result
            if num is None:
                return

            step_mode = False
            if num > 1:
                step_mode = messagebox.askyesno(
                    "Step through commits",
                    "Apply commits one at a time with confirmation before each cherry-pick?",
                )

            stashed = False
            if not WorkingTreeManager.is_clean(repo):
                if not messagebox.askyesno(
                    "Uncommitted Changes",
                    "Working tree not clean. Stash (incl. untracked) and continue?\n"
                    "This will also abort any ongoing merge/cherry-pick/rebase first.",
                ):
                    return
                self._abort_in_progress_ops(repo)
                WorkingTreeManager.stash(repo, f"git-manager auto-stash before moving commits ({now_display()})")
                stashed = True

            commits = GitOperations.run_git(["rev-list", "--reverse", f"{state.base_branch}..local_commit"], cwd=repo).strip().splitlines()[:num]
            if not commits:
                raise GitManagerError("No commits to process")
            processed: list[str] = []

            self.append_output(f"🕒 Rewriting commits with current user info...\n")
            expected_email = GitOperations.run_git(["config", "user.email"], cwd=repo).strip()
            expected_name = GitOperations.run_git(["config", "user.name"], cwd=repo).strip()
            self.append_output(f"⚠️  All commits will be authored by: {expected_name} <{expected_email}>\n")

            BranchManager.checkout(repo, state.base_branch)
            now_iso_value = now_iso()
            for commit in commits:
                if step_mode:
                    subject = GitOperations.run_git(["show", "-s", "--format=%s", commit], cwd=repo).strip()
                    if not messagebox.askyesno(
                        "Move commit",
                        f"Move commit {commit[:7]}\n{subject}\n\nApply this commit?",
                    ):
                        break
                try:
                    GitOperations.run_git(["cherry-pick", "--no-commit", commit], cwd=repo)
                except GitManagerError:
                    conflict_names = GitOperations.run_git(["diff", "--name-only", "--diff-filter=U"], cwd=repo).strip()
                    if conflict_names:
                        try:
                            choice = self._choose_conflict_resolution(commit, conflict_names)
                        except GitManagerError as choice_err:
                            GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                            raise choice_err

                        if choice == "ours":
                            GitOperations.run_git(["checkout", "--ours", "."], cwd=repo)
                            GitOperations.run_git(["add", "."], cwd=repo)
                            msg = GitOperations.run_git(["show", "-s", "--format=%B", commit], cwd=repo)
                            GitOperations.run_git_env(
                                ["commit", "-m", msg, "--date", now_iso_value],
                                cwd=repo,
                                extra_env={"GIT_AUTHOR_DATE": now_iso_value, "GIT_COMMITTER_DATE": now_iso_value},
                            )
                            self.append_output(f"✓ Resolved with ours for {commit[:7]}")
                            self.append_output(GitOperations.run_git(["show", "-s", "--date=iso", "--pretty=format:  ✔ %h  %ad  %an <%ae>"], cwd=repo) + "\n")
                            processed.append(commit)
                            continue

                        if choice == "theirs":
                            GitOperations.run_git(["checkout", "--theirs", "."], cwd=repo)
                            GitOperations.run_git(["add", "."], cwd=repo)
                            msg = GitOperations.run_git(["show", "-s", "--format=%B", commit], cwd=repo)
                            GitOperations.run_git_env(
                                ["commit", "-m", msg, "--date", now_iso_value],
                                cwd=repo,
                                extra_env={"GIT_AUTHOR_DATE": now_iso_value, "GIT_COMMITTER_DATE": now_iso_value},
                            )
                            self.append_output(f"✓ Resolved with theirs for {commit[:7]}")
                            self.append_output(GitOperations.run_git(["show", "-s", "--date=iso", "--pretty=format:  ✔ %h  %ad  %an <%ae>"], cwd=repo) + "\n")
                            processed.append(commit)
                            continue

                        if choice == "skip":
                            GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                            self.append_output(f"⊘ Skipping commit {commit[:7]} after conflicts")
                            continue

                        # Abort / manual resolution
                        GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                        raise GitManagerError("Cherry-pick aborted for manual resolution")
                    status = GitOperations.run_git(["status"], cwd=repo)
                    if "nothing to commit" in status:
                        self.append_output(f"⊘ Skipping empty commit {commit[:7]}\n")
                        GitOperations.run_git(["cherry-pick", "--skip"], cwd=repo)
                        continue
                    raise

                # Check if there are any changes to commit (handle empty commits after successful --no-commit)
                status = GitOperations.run_git(["status", "--short"], cwd=repo).strip()
                if not status:
                    self.append_output(f"⊘ Skipping empty commit {commit[:7]} (already applied)\n")
                    continue

                message = GitOperations.run_git(["show", "-s", "--format=%B", commit], cwd=repo)
                GitOperations.run_git_env(
                    ["commit", "-m", message, "--date", now_iso_value],
                    cwd=repo,
                    extra_env={"GIT_AUTHOR_DATE": now_iso_value, "GIT_COMMITTER_DATE": now_iso_value},
                )
                processed.append(commit)
                self.append_output(GitOperations.run_git(["show", "-s", "--date=iso", "--pretty=format:  ✔ %h  %ad  %an <%ae>"], cwd=repo) + "\n")

            processed_count = len(processed)
            if processed_count == 0:
                self.append_output("No commits were applied; aborting move.")
                BranchManager.checkout(repo, state.current_branch)
                if stashed:
                    try:
                        WorkingTreeManager.pop_stash(repo)
                    except GitManagerError:
                        self.append_output("⚠️ Stash pop had conflicts or failed. Resolve manually.")
                return

            self.append_output(f"📜 Latest moved commits on {state.base_branch} (with author info):\n")
            latest_log = GitOperations.run_git(["log", "-n", str(processed_count), "--no-decorate", "--date=iso", "--pretty=format:  %h  %ad  %an <%ae>"], cwd=repo)
            self.append_output(latest_log + "\n")

            # ===== Pre-push validation =====
            self.append_output("🔍 Validating commits before push...\n")
            # 1) Ensure remote default branch matches target base branch
            default_head = GitOperations.run_git(["remote", "show", "origin"], cwd=repo)
            for line in default_head.splitlines():
                if "HEAD branch:" in line:
                    remote_head = line.split(":", 1)[1].strip()
                    if remote_head and remote_head != state.base_branch:
                        raise GitManagerError(
                            f"Remote default branch is '{remote_head}', but target is '{state.base_branch}'."
                        )
                    break

            # 2) Ensure author date day equals today's day for all moved commits
            dates = GitOperations.run_git(["log", "-n", str(processed_count), "--date=short", "--pretty=format:%ad"], cwd=repo).splitlines()
            today_str = now_iso()[:10]
            bad_dates = [d for d in dates if d and d != today_str]
            if bad_dates:
                raise GitManagerError(f"Found {len(bad_dates)} commit(s) with author date not equal to today")

            # 3) Ensure author email matches local git config (so GitHub can attribute contributions)
            emails = GitOperations.run_git(["log", "-n", str(processed_count), "--pretty=format:%ae"], cwd=repo).splitlines()
            names = GitOperations.run_git(["log", "-n", str(processed_count), "--pretty=format:%an"], cwd=repo).splitlines()
            if any(e and e != expected_email for e in emails):
                raise GitManagerError(f"Found commit(s) with author email not matching '{expected_email}'")
            if any(n and n != expected_name for n in names):
                raise GitManagerError(f"Found commit(s) with author name not matching '{expected_name}'")

            self.append_output(f"✅ All {processed_count} commits have correct author info (will be attributed to {expected_name} <{expected_email}>)\n")
            self.append_output(f"🚀 Pushing to origin {state.base_branch}...\n")
            GitOperations.run_git(["push", "origin", state.base_branch], cwd=repo)
            self.append_output(f"✅ Done! {processed_count} commits moved with date/time {now_iso_value}\n")

            # ===== Clean up local_commit ONLY AFTER successful push =====
            backup_branch = self._backup_local_commit(repo)
            remaining = GitOperations.run_git(["rev-list", "--reverse", f"{state.base_branch}..local_commit"], cwd=repo).strip().splitlines()
            if remaining:
                self.append_output(f"⚠️  You moved {processed_count} of {pending} commits.\n")
                self.append_output(f"🔄 Rewriting local_commit to keep only remaining commits...\n")
                BranchManager.checkout(repo, "local_commit")
                GitOperations.run_git(["reset", "--hard", state.base_branch], cwd=repo)
                for commit in remaining:
                    try:
                        GitOperations.run_git(["cherry-pick", commit], cwd=repo)
                    except GitManagerError:
                        # Check if it's an empty commit (already applied)
                        status = GitOperations.run_git(["status"], cwd=repo)
                        if "nothing to commit" in status:
                            self.append_output(f"⊘ Skipping empty commit {commit[:7]} (already on {state.base_branch})\n")
                            GitOperations.run_git(["cherry-pick", "--skip"], cwd=repo)
                            continue
                        # Otherwise abort and raise error
                        GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                        raise GitManagerError(
                            f"Cherry-pick failed while rewriting local_commit for commit {commit}. Resolve manually."
                        )
                self.append_output("✅ local_commit updated to reflect remaining commits.\n")
            else:
                self.append_output(f"🔄 Syncing local_commit to {state.base_branch}...\n")
                BranchManager.checkout(repo, "local_commit")
                GitOperations.run_git(["reset", "--hard", state.base_branch], cwd=repo)
                self.append_output(f"✅ local_commit is now aligned with {state.base_branch}\n")

            if stashed:
                self.append_output(f"🔧 Restoring stashed changes to {state.current_branch}...\n")
                BranchManager.checkout(repo, state.current_branch)
                try:
                    WorkingTreeManager.pop_stash(repo)
                except GitManagerError:
                    self.append_output("⚠️ Stash pop had conflicts or failed. Resolve manually.")

            self.refresh_repos()
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")

    def action_restore(self) -> None:
        state = self.selected_state()
        if not state:
            return
        repo = state.path
        try:
            if not messagebox.askyesno(
                "Restore local_commit",
                "This will restore local_commit to the last known good state from reflog.\n\nContinue?"
            ):
                return

            self.append_output(f"♻️ Restoring local_commit from reflog...\n")
            
            # Get branch-specific reflog entries to find the last good local_commit state
            # Use 'git reflog show local_commit' to get the branch's history
            reflog = GitOperations.run_git(["reflog", "show", "local_commit", "-20"], cwd=repo)
            local_commit_sha = None
            
            for line in reflog.splitlines():
                # Look for entries that are NOT "branch: Created from" or "reset: moving to main"
                if ("branch: Created from" not in line and 
                    "reset: moving to main" not in line and
                    "reset: moving to " + state.base_branch not in line):
                    # Extract SHA from the line (format: SHA local_commit@{N}: action: message)
                    parts = line.split()
                    if parts:
                        local_commit_sha = parts[0]
                        break
            
            if not local_commit_sha:
                raise GitManagerError("Could not find a valid local_commit state in reflog")
            
            # Restore local_commit
            BranchManager.checkout(repo, "local_commit")
            GitOperations.run_git(["reset", "--hard", local_commit_sha], cwd=repo)
            
            # Show how many commits we have
            count = int(GitOperations.run_git(["rev-list", "--count", f"{state.base_branch}..local_commit"], cwd=repo).strip() or "0")
            self.append_output(f"✅ Restored local_commit to {local_commit_sha[:7]}\n")
            self.append_output(f"📊 Found {count} commits ahead of {state.base_branch}\n")
            self.append_output(f"📜 Commits:\n")
            log = GitOperations.run_git([
                "log",
                "--reverse",
                "--no-decorate",
                "--date=short",
                "--pretty=format:  %h  %ad  %s",
                f"{state.base_branch}..local_commit",
            ], cwd=repo)
            self.append_output(log + "\n")
            
            self.refresh_repos()
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")


def main() -> None:
    root = tk.Tk()
    root.attributes('-zoomed', True)  # Fullscreen on Linux
    gui = GitManagerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
