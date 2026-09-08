"""Main window for Git Manager GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from core.branch_manager import BranchManager
from core.git_config import GitConfig
from core.git_operations import GitManagerError, GitOperations
from core.repo_scanner import RepoScanner
from core.repo_state import RepoState
from core.settings_db import SettingsDB
from core.working_tree_manager import WorkingTreeManager
from ui.dialogs import CommitDialog, ManageCommitsDialog, NumericKeypadDialog, PreviewModeDialog, ResetDialog, SettingsDialog
from ui.theme import apply_theme as apply_theme_style
from utils.network import NO_INTERNET_MSG, has_internet_connection, is_network_error_message
from utils.time_utils import is_future, now_display, now_iso


DEFAULT_BASE_DIR = Path.home() / "GitHub"


class GitManagerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Git Manager - Repository Management Tool")
        self.root.configure(bg="#f0f0f0")

        # Initialize settings database
        self.db = SettingsDB()
        saved_base = self.db.get_base_directory()
        initial_base = saved_base if saved_base else str(DEFAULT_BASE_DIR)
        self.auto_switch_to_local_commit = self.db.get_auto_switch_local_commit()
        self.auto_refresh_enabled = self.db.get_auto_refresh_enabled()
        self.refresh_interval = self.db.get_refresh_interval()
        self.theme_mode = self.db.get_theme_mode()

        self.base_var = tk.StringVar(value=initial_base)
        self.output_font_size = self.db.get_output_font_size()
        self.table_font_size = self.db.get_table_font_size()
        self.button_font_size = self.db.get_button_font_size()
        self.states: List[RepoState] = []
        self.auto_refresh_job: Optional[str] = None
        self.operation_in_progress = False
        # Debounce job ids for layout persistence
        self._geometry_save_job: Optional[str] = None
        self._paned_save_job: Optional[str] = None
        self._column_save_job: Optional[str] = None

        self._build_layout()
        self.apply_theme(self.theme_mode)
        self._restore_layout()
        self.refresh_repos()
        if self.auto_switch_to_local_commit:
            self.switch_all_to_local_commit(skip_busy_check=True)
        self._update_auto_refresh()
        
        # Register cleanup on window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _start_operation(self, description: str) -> bool:
        if self.operation_in_progress:
            messagebox.showerror(
                "Operation in progress",
                f"Another operation is already running. Please wait for it to finish before {description}.",
                parent=self.root,
            )
            return False
        self.operation_in_progress = True
        self.status_var.set(f"⏳ {description.capitalize()}... Please wait.")
        self.root.update_idletasks()
        return True

    def _end_operation(self) -> None:
        self.operation_in_progress = False
        self.status_var.set("✓ Ready")
        self.root.update_idletasks()

    def _confirm_exit_during_operation(self) -> bool:
        return messagebox.askyesno(
            "Operation in progress",
            "An operation is currently running. Do you want to exit anyway?\n"
            "This may interrupt the current task.",
            parent=self.root,
        )

    # --- network helpers -------------------------------------------------
    def _is_no_internet_error(self, exc: Exception) -> bool:
        msg = str(exc)
        return NO_INTERNET_MSG in msg or is_network_error_message(msg)

    def _show_no_internet_error(self, exc: Exception | None = None) -> None:
        detail = str(exc) if exc else ""
        # Always show the requested Persian message prominently
        messagebox.showerror(
            "عدم اتصال به اینترنت",
            f"{NO_INTERNET_MSG}!\nلطفاً اتصال اینترنت خود را بررسی کنید.\n{detail}",
            parent=self.root,
        )
        self.append_output(f"\n❌ {NO_INTERNET_MSG}! لطفاً اتصال اینترنت را بررسی کنید.\n")
        if detail:
            self.append_output(f"   جزئیات: {detail}\n")

    def _check_internet_or_notify(self) -> bool:
        """Return True if online, else show error and return False."""
        if not has_internet_connection(timeout=3.0):
            self._show_no_internet_error()
            return False
        return True

    def apply_theme(self, mode: str) -> None:
        self.theme_mode = mode
        # Delegate to centralized theme module; preserve exact previous behavior
        colors = apply_theme_style(
            self.root,
            mode,
            self.button_font_size,
            self.table_font_size,
            self.output_font_size,
            getattr(self, "output", None),
            getattr(self, "status_label", None),
            getattr(self, "tree", None),
        )
        # Keep status_var refresh behavior
        if hasattr(self, "status_var"):
            self.status_var.set(self.status_var.get())
        self._theme_tree_tags(colors["tree_tag_has"], colors["tree_tag_clean"])

    def _theme_tree_tags(self, has_color: str, clean_color: str) -> None:
        if hasattr(self, "tree"):
            self.tree.tag_configure("has_commits", background=has_color)
            self.tree.tag_configure("clean", background=clean_color)

    # --- layout persistence helpers --------------------------------------
    def _restore_layout(self) -> None:
        """Restore saved window geometry, column widths and paned sash position."""
        # Restore tree column widths immediately (widget already exists)
        widths = self.db.get_tree_column_widths()
        if widths:
            for col, w in widths.items():
                try:
                    # Clamp to sensible range to avoid broken layout
                    w = max(20, min(800, int(w)))
                    self.tree.column(col, width=w)
                except Exception:
                    continue
        # Restore window geometry / maximized state
        try:
            maximized = self.db.get_window_maximized()
            geom = self.db.get_window_geometry()
            if maximized:
                try:
                    self.root.state("zoomed")
                except tk.TclError:
                    try:
                        self.root.attributes("-zoomed", True)
                    except tk.TclError:
                        if geom:
                            self.root.geometry(geom)
            elif geom:
                try:
                    self.root.geometry(geom)
                except tk.TclError:
                    pass
        except Exception:
            pass
        # Restore paned sash position after geometry is applied (needs idle)
        sash = self.db.get_paned_sash_pos()
        if sash is not None:
            def _apply_sash() -> None:
                try:
                    # Only apply if pane exists and height is realized
                    if hasattr(self, "paned") and self.paned.winfo_height() > 1:
                        # Clamp sash to 15%-85% of pane height for safety
                        h = self.paned.winfo_height()
                        sash_clamped = max(int(h * 0.15), min(int(h * 0.85), int(sash)))
                        self.paned.sashpos(0, sash_clamped)
                    else:
                        # Retry shortly if not yet mapped
                        self.root.after(150, _apply_sash)
                except Exception:
                    pass
            self.root.after(150, _apply_sash)

        # Bind persistence events (debounced)
        try:
            self.root.bind("<Configure>", self._on_window_configure)
            self.tree.bind("<ButtonRelease-1>", self._on_tree_column_resize)
            # Catch separator drag on tree headings (motion then release)
            self.tree.bind("<B1-Motion>", self._on_tree_column_motion)
            if hasattr(self, "paned"):
                self.paned.bind("<ButtonRelease-1>", self._on_paned_sash_release)
                self.paned.bind("<B1-Motion>", self._on_paned_sash_motion)
        except Exception:
            pass

    def _is_window_maximized(self) -> bool:
        try:
            if self.root.state() == "zoomed":
                return True
        except Exception:
            pass
        try:
            return bool(self.root.attributes("-zoomed"))
        except Exception:
            return False

    def _save_window_geometry(self) -> None:
        try:
            if self._is_window_maximized():
                self.db.set_window_maximized(True)
            else:
                self.db.set_window_maximized(False)
                geom = self.root.geometry()
                # Ignore spurious tiny geometries (e.g. withdrawn 1x1)
                if geom:
                    try:
                        wh = geom.split("+")[0]
                        w_str, h_str = wh.split("x")
                        w, h = int(w_str), int(h_str)
                        if w < 200 or h < 200:
                            return
                    except Exception:
                        pass
                    self.db.set_window_geometry(geom)
        except Exception:
            pass

    def _save_tree_column_widths(self) -> None:
        try:
            widths: dict[str, int] = {}
            for col in ("#0", "name", "commits", "pushed", "branch", "base"):
                try:
                    widths[col] = int(self.tree.column(col, option="width"))
                except Exception:
                    continue
            if widths:
                self.db.set_tree_column_widths(widths)
        except Exception:
            pass

    def _save_paned_sash(self) -> None:
        try:
            if hasattr(self, "paned"):
                pos = int(self.paned.sashpos(0))
                self.db.set_paned_sash_pos(pos)
        except Exception:
            pass

    def _on_window_configure(self, event: tk.Event) -> None:  # type: ignore
        if event.widget is not self.root:
            return
        # Debounce: wait 800ms after last resize before saving
        if self._geometry_save_job is not None:
            try:
                self.root.after_cancel(self._geometry_save_job)
            except Exception:
                pass
        self._geometry_save_job = self.root.after(800, self._save_window_geometry)

    def _on_tree_column_resize(self, event: tk.Event | None = None) -> None:  # type: ignore
        if self._column_save_job is not None:
            try:
                self.root.after_cancel(self._column_save_job)
            except Exception:
                pass
        self._column_save_job = self.root.after(400, self._save_tree_column_widths)

    def _on_tree_column_motion(self, event: tk.Event | None = None) -> None:  # type: ignore
        # Motion handler is intentionally lightweight; actual save on release
        pass

    def _on_paned_sash_release(self, event: tk.Event | None = None) -> None:  # type: ignore
        if self._paned_save_job is not None:
            try:
                self.root.after_cancel(self._paned_save_job)
            except Exception:
                pass
        self._paned_save_job = self.root.after(400, self._save_paned_sash)

    def _on_paned_sash_motion(self, event: tk.Event | None = None) -> None:  # type: ignore
        pass

    def _build_layout(self) -> None:
        # Action buttons with better styling
        buttons = ttk.Frame(self.root, padding=8)
        buttons.pack(fill=tk.X, padx=12, pady=12)
        
        style = ttk.Style()
        style.configure("Action.TButton", font=("Helvetica", 10, "bold"), padding=8)
        
        ttk.Button(buttons, text="🔄 Refresh", command=self.refresh_repos, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="🔀 Switch Branch", command=self.action_switch, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="👁 Preview Commits", command=self.action_preview, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="📝 Make a Commit", command=self.action_make_commit, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="🚀 Move Commits", command=self.action_move, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="🔁 Reset / Delete", command=self.action_reset, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(buttons, text="⚙️ Settings", command=self.action_settings, style="Action.TButton").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Split main content into resizable panes
        self.paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        paned = self.paned  # keep local alias for readability

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
            columns=("name", "commits", "pushed", "branch", "base"),
            show="tree headings",
            selectmode="browse",
            height=12,
        )
        self.tree.heading("#0", text="")
        self.tree.heading("name", text="Repository")
        self.tree.heading("commits", text="Pending")
        self.tree.heading("pushed", text="Pushed")
        self.tree.heading("branch", text="Current Branch")
        self.tree.heading("base", text="Base Branch")
        self.tree.column("#0", width=60, stretch=False)
        self.tree.column("name", width=250, anchor=tk.W)
        self.tree.column("commits", width=90, anchor=tk.CENTER)
        self.tree.column("pushed", width=90, anchor=tk.CENTER)
        self.tree.column("branch", width=170, anchor=tk.CENTER)
        self.tree.column("base", width=140, anchor=tk.CENTER)
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
        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(12, 8))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_var = tk.StringVar(value="✓ Ready")
        self.status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            anchor=tk.W,
            font=("Helvetica", 10, "bold"),
        )
        self.status_label.pack(fill=tk.X, ipady=2)

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
            # Add visual indicators: icon + dirty marker in the first tree column
            icon = "📦" if state.local_exists else "📁"
            tag = "has_commits" if state.commit_count > 0 else "clean"
            first_col_text = f"{icon}{' ★' if state.dirty else ''}"
            repo_name = state.name
            
            self.tree.insert(
                "",
                tk.END,
                iid=str(idx - 1),
                values=(
                    repo_name,
                    state.commit_count,
                    state.pushed_count,
                    state.current_branch,
                    state.base_branch,
                ),
                text=first_col_text,
                tags=(tag,)
            )
        
        # Configure tag colors
        if self.theme_mode == "dark":
            self.tree.tag_configure("has_commits", background="#333333")
            self.tree.tag_configure("clean", background="#2b2b2b")
        else:
            self.tree.tag_configure("has_commits", background="#fff9e6")
            self.tree.tag_configure("clean", background="#f0f8ff")
        
        self.status_var.set(f"✓ Loaded {len(states)} repositories from {base_dir}")

    def _has_origin_main(self, repo: Path) -> bool:
        """Check strict prerequisite: origin/main must exist as remote-tracking branch."""
        return GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/remotes/origin/main"], cwd=repo)

    def _has_local_commit(self, repo: Path) -> bool:
        """Check if local_commit branch exists locally."""
        return GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=repo)

    def switch_all_to_local_commit(self, skip_busy_check: bool = False) -> None:
        """Switch all repositories to local_commit branch.

        Strict workflow (new repo):
        1) Prerequisite origin/main must exist first before any automation.
        2) If local_commit does NOT exist → create it ONLY upon open/close if origin/main exists.
        3) If local_commit already exists → do not re-create, just proceed (checkout if needed).
        Under no circumstances will we attempt to trigger/create local_commit during
        open/close until origin/main is confirmed for newly created repositories.
        """
        if not self.states:
            return
        if not skip_busy_check and not self._start_operation("switch all repositories to local_commit"):
            return

        try:
            self.append_output("🔄 Ensuring all repositories are on local_commit branch...\n")
            for state in self.states:
                try:
                    # Live checks (state may be stale)
                    local_exists = self._has_local_commit(state.path)
                    has_origin_main = self._has_origin_main(state.path)

                    # Key Rule: never attempt to create local_commit during open/close
                    # until origin/main is confirmed for this repo.
                    if not local_exists and not has_origin_main:
                        self.append_output(
                            f"  ⏭ {state.name}: origin/main not found — skipping local_commit creation (prerequisite)\n"
                        )
                        continue

                    if state.current_branch != "local_commit":
                        if local_exists:
                            # Conditional logic: already exists → just checkout, do not re-create
                            BranchManager.checkout(state.path, "local_commit")
                            self.append_output(f"  ✓ {state.name}: switched to local_commit\n")
                        else:
                            # local_commit does NOT exist → create upon open/close (prerequisite already ensured)
                            BranchManager.switch_to_local_commit(state.path, state.base_branch)
                            self.append_output(f"  ✓ {state.name}: created and switched to local_commit\n")
                    else:
                        self.append_output(f"  ✓ {state.name}: already on local_commit\n")
                except GitManagerError as exc:
                    self.append_output(f"  ⚠️  {state.name}: {str(exc)}\n")
            self.append_output("✅ Branch check complete\n\n")
            self.refresh_repos()
        finally:
            if not skip_busy_check:
                self._end_operation()

    def on_closing(self) -> None:
        """Handle window close event."""
        if self.operation_in_progress:
            if not self._confirm_exit_during_operation():
                return
        # Persist layout before exit (geometry, columns, sash)
        try:
            self._save_window_geometry()
            self._save_tree_column_widths()
            self._save_paned_sash()
        except Exception:
            pass
        self._cancel_auto_refresh()
        self.switch_all_to_local_commit(skip_busy_check=True)
        self.root.destroy()

    def append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        # Avoid double newlines – callers historically pass text with trailing \n
        if text.endswith("\n"):
            to_insert = text
        else:
            to_insert = text + "\n"
        self.output.insert(tk.END, to_insert)
        self.output.configure(state="disabled")
        self.output.see(tk.END)
        self.root.update_idletasks()  # avoid re-entrant event handling during operations

    def _schedule_auto_refresh(self) -> None:
        self._cancel_auto_refresh()
        if not self.auto_refresh_enabled:
            return

        interval_ms = max(1, self.refresh_interval) * 60_000
        self.auto_refresh_job = self.root.after(interval_ms, self._auto_refresh_callback)

    def _cancel_auto_refresh(self) -> None:
        if getattr(self, "auto_refresh_job", None) is not None:
            try:
                self.root.after_cancel(self.auto_refresh_job)
            except Exception:
                pass
            self.auto_refresh_job = None

    def _update_auto_refresh(self) -> None:
        if self.auto_refresh_enabled:
            self._schedule_auto_refresh()
        else:
            self._cancel_auto_refresh()

    def _auto_refresh_callback(self) -> None:
        if self.operation_in_progress:
            # Defer refresh while a move/commit/etc. is running to avoid interleaving git ops
            self._schedule_auto_refresh()
            return
        self.refresh_repos()
        self._schedule_auto_refresh()

    # --- helpers ---------------------------------------------------------
    def _abort_in_progress_ops(self, repo: Path) -> None:
        git_dir = repo / ".git"
        if (git_dir / "MERGE_HEAD").exists():
            try:
                GitOperations.run_git(["merge", "--abort"], cwd=repo)
            except GitManagerError as exc:
                self.append_output(f"⚠️  Could not abort merge cleanly: {str(exc)}\n")
        if (git_dir / "CHERRY_PICK_HEAD").exists():
            try:
                GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
            except GitManagerError as exc:
                self.append_output(f"⚠️  Could not abort cherry-pick cleanly: {str(exc)}\n")
        if (git_dir / "rebase-merge").exists():
            try:
                GitOperations.run_git(["rebase", "--abort"], cwd=repo)
            except GitManagerError as exc:
                self.append_output(f"⚠️  Could not abort rebase cleanly: {str(exc)}\n")

    def _choose_conflict_resolution(self, commit: str, conflicts: str) -> str:
        dialog = tk.Toplevel(self.root)
        dialog.title("Resolve cherry-pick conflict")
        dialog.resizable(True, True)
        dialog.minsize(520, 360)
        dialog.transient(self.root)
        dialog.grab_set()

        colors = apply_theme_style(
            dialog,
            self.theme_mode,
            self.button_font_size,
            self.table_font_size,
            self.output_font_size,
        )
        result: list[Optional[str]] = [None]

        content = ttk.Frame(dialog, style="Dialog.TFrame", padding=20)
        content.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            content,
            text="Cherry-pick conflict requires a decision",
            font=("Helvetica", 13, "bold"),
            style="Dialog.TLabel",
        ).pack(anchor=tk.W)
        ttk.Label(
            content,
            text=f"Commit {commit[:7]} has changes that overlap with the target branch.",
            style="Dialog.TLabel",
        ).pack(anchor=tk.W, pady=(5, 14))

        files_frame = ttk.LabelFrame(
            content,
            text=f"Conflicted files ({len(conflicts.splitlines())})",
            style="Dialog.TLabelframe",
            padding=8,
        )
        files_frame.pack(fill=tk.BOTH, expand=True)
        file_list = tk.Listbox(
            files_frame,
            activestyle="none",
            bg=colors["text_bg"],
            fg=colors["fg"],
            selectbackground=colors["selected_bg"],
            selectforeground=colors["selected_fg"],
            relief=tk.FLAT,
            highlightthickness=0,
            font=("Courier", max(9, self.output_font_size)),
        )
        scrollbar = ttk.Scrollbar(files_frame, orient=tk.VERTICAL, command=file_list.yview)
        file_list.configure(yscrollcommand=scrollbar.set)
        file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        for filename in conflicts.splitlines():
            file_list.insert(tk.END, filename)

        ttk.Label(
            content,
            text="Keep base preserves the target branch. Use incoming to apply the selected commit’s version.",
            style="Dialog.TLabel",
            wraplength=700,
        ).pack(anchor=tk.W, pady=(12, 4))

        buttons = ttk.Frame(content, style="Dialog.TFrame")
        buttons.pack(fill=tk.X, pady=(12, 0))

        def finish(choice: str) -> None:
            result[0] = choice
            dialog.destroy()

        ttk.Button(buttons, text="Keep base", command=lambda: finish("ours"), style="Dialog.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(buttons, text="Use incoming", command=lambda: finish("theirs"), style="Dialog.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="Skip commit", command=lambda: finish("skip"), style="Dialog.TButton").pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(buttons, text="Abort", command=lambda: finish("abort"), style="Dialog.TButton").pack(side=tk.RIGHT, padx=6)

        dialog.protocol("WM_DELETE_WINDOW", lambda: finish("abort"))
        dialog.bind("<Escape>", lambda event: finish("abort"))
        dialog.bind("<KeyPress-1>", lambda event: finish("ours"))
        dialog.bind("<KeyPress-2>", lambda event: finish("theirs"))
        dialog.bind("<KeyPress-3>", lambda event: finish("abort"))
        dialog.bind("<KeyPress-4>", lambda event: finish("skip"))
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        dialog.focus_set()
        self.root.wait_window(dialog)

        if result[0] is None:
            raise GitManagerError("Conflict resolution cancelled")
        return result[0]

    def _backup_local_commit(self, repo: Path) -> str:
        backup_name = f"backup_local_commit_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            GitOperations.run_git(["branch", backup_name, "local_commit"], cwd=repo)
            self.append_output(f"🛟 Created {backup_name} from local_commit before rewrite")
        except GitManagerError as exc:
            self.append_output(f"⚠️  Failed to create backup branch: {str(exc)}\n")
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

    def action_change_base_directory(self) -> None:
        if not self._start_operation("change the base directory"):
            return
        try:
            new_dir = filedialog.askdirectory(
                parent=self.root,
                title="Select Base Directory",
                initialdir=self.base_var.get(),
            )
            if not new_dir:
                return
            self.base_var.set(new_dir)
            self.db.set_base_directory(new_dir)
            self.append_output(f"💾 Saved base directory: {new_dir}\n")
            self.refresh_repos()
            self.append_output("✅ Base directory updated. You may continue or close the app.\n")
        finally:
            self._end_operation()

    def action_settings(self) -> None:
        if self.operation_in_progress:
            messagebox.showerror(
                "Operation in progress",
                "Another operation is currently running. Please wait for it to finish before opening settings.",
                parent=self.root,
            )
            return
        dialog = SettingsDialog(
            self.root,
            self.base_var.get(),
            self.auto_switch_to_local_commit,
            self.theme_mode,
            self.auto_refresh_enabled,
            self.refresh_interval,
            self.output_font_size,
            self.table_font_size,
            self.button_font_size,
        )
        self.root.wait_window(dialog)
        if dialog.result is None:
            return

        new_base, auto_switch, theme_mode, auto_refresh_enabled, refresh_interval, output_font_size, table_font_size, button_font_size = dialog.result
        self.base_var.set(new_base)
        self.auto_switch_to_local_commit = auto_switch
        self.auto_refresh_enabled = auto_refresh_enabled
        self.refresh_interval = refresh_interval
        self.theme_mode = theme_mode
        self.output_font_size = output_font_size
        self.table_font_size = table_font_size
        self.button_font_size = button_font_size
        self.db.set_base_directory(new_base)
        self.db.set_auto_switch_local_commit(auto_switch)
        self.db.set_theme_mode(theme_mode)
        self.db.set_auto_refresh_enabled(auto_refresh_enabled)
        self.db.set_refresh_interval(refresh_interval)
        self.db.set_output_font_size(output_font_size)
        self.db.set_table_font_size(table_font_size)
        self.db.set_button_font_size(button_font_size)

        self.append_output(f"💾 Settings saved. Base directory: {new_base}\n")
        self.apply_theme(self.theme_mode)
        self._update_auto_refresh()
        self.refresh_repos()
        if auto_switch:
            self.switch_all_to_local_commit()
        self.append_output("✅ Settings saved. You may continue or close the app.\n")

    def action_switch(self) -> None:
        if not self._start_operation("switch branches"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return
        stashed = False
        try:
            GitConfig.ensure_identity(state.path)
            # Handle dirty working tree (including untracked) like move does – avoid raw checkout errors
            if not WorkingTreeManager.is_clean(state.path):
                if not messagebox.askyesno(
                    "Uncommitted Changes",
                    "Working tree not clean (including untracked files). Stash (incl. untracked) and continue switching?\n"
                    "This will also abort any ongoing merge/cherry-pick/rebase first.",
                    parent=self.root,
                ):
                    self.append_output("⏭ Switch cancelled – working tree is dirty. Commit or stash first.\n")
                    return
                self._abort_in_progress_ops(state.path)
                WorkingTreeManager.stash(state.path, f"git-manager auto-stash before switch ({now_display()})")
                stashed = True
            if state.current_branch == "local_commit":
                if not state.base_branch:
                    raise GitManagerError("Base branch not detected – cannot switch back from local_commit")
                BranchManager.switch_to_base(state.path, state.base_branch)
                new_branch = state.base_branch
            else:
                # Pass current_branch so branch_manager can handle empty base_branch safely
                BranchManager.switch_to_local_commit(state.path, state.base_branch, state.current_branch)
                new_branch = "local_commit"
            # Restore stashed changes after successful checkout, if any
            if stashed:
                try:
                    WorkingTreeManager.pop_stash(state.path)
                    self.append_output("🔧 Restored stashed changes after switch.\n")
                except GitManagerError as exc:
                    self.append_output(f"⚠️ Stash pop failed after switch: {str(exc)}\nResolve manually with 'git stash pop'\n")
            self.append_output(f"Switched to {new_branch} in {state.name}")
            self.refresh_repos()
            self.append_output("✅ Operation complete. The branch switch is done.\n")
        except GitManagerError as exc:
            # If we stashed and checkout failed, try to restore stash
            if stashed:
                try:
                    WorkingTreeManager.pop_stash(state.path)
                except GitManagerError:
                    self.append_output("⚠️ Stash remains – resolve manually with 'git stash pop'\n")
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            if self._is_no_internet_error(exc):
                self._show_no_internet_error(exc)
            else:
                messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")
        finally:
            self._end_operation()

    def _resolve_upstream(self, repo: Path, branch: str, base_branch: str) -> Optional[str]:
        try:
            upstream = GitOperations.run_git(
                ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                cwd=repo,
            ).strip()
            if upstream:
                return upstream
        except GitManagerError:
            pass

        if branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], cwd=repo):
            return f"origin/{branch}"

        if branch == base_branch and base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
            return f"origin/{base_branch}"

        if GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "origin/HEAD"], cwd=repo):
            origin_head = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo).strip()
            if origin_head and origin_head != "HEAD":
                return origin_head

        return None

    def action_preview(self) -> None:
        if not self._start_operation("preview commits"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return

        try:
            dialog = PreviewModeDialog(self.root, self.theme_mode)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return

            mode = dialog.result
            branch = state.current_branch
            upstream = self._resolve_upstream(state.path, branch, state.base_branch)

            if mode == "unpushed":
                if branch == "local_commit":
                    if not state.base_branch:
                        raise GitManagerError("Cannot preview unpushed commits for local_commit without a configured base branch.")
                    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.base_branch}"], cwd=state.path):
                        remote_base = f"origin/{state.base_branch}"
                    elif GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "origin/HEAD"], cwd=state.path):
                        remote_base = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=state.path).strip()
                    else:
                        raise GitManagerError("No remote base branch found for local_commit preview.")
                    log_range = f"{remote_base}..local_commit"
                    title = f"Unpushed commits on local_commit relative to {remote_base}"
                else:
                    if upstream:
                        log_range = f"{upstream}..{branch}"
                    elif GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], cwd=state.path):
                        log_range = f"origin/{branch}..{branch}"
                    elif branch == state.base_branch and state.base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.base_branch}"], cwd=state.path):
                        log_range = f"origin/{state.base_branch}..{state.base_branch}"
                    else:
                        raise GitManagerError("Current branch has no upstream or remote tracking branch to compare for unpushed commits.")
                    title = f"Unpushed commits on {branch}"
            else:
                if upstream:
                    log_range = upstream
                elif branch == state.base_branch and state.base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.base_branch}"], cwd=state.path):
                    log_range = f"origin/{state.base_branch}"
                elif GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], cwd=state.path):
                    log_range = f"origin/{branch}"
                elif branch == "local_commit" and state.base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{state.base_branch}"], cwd=state.path):
                    log_range = f"origin/{state.base_branch}"
                else:
                    raise GitManagerError("Current branch has no upstream or remote branch to display pushed commits.")
                title = f"Pushed commits on {log_range}"

            log = GitOperations.run_git(
                [
                    "log",
                    "--reverse",
                    "--no-decorate",
                    "--date=short",
                    "--pretty=format:  %h  %ad  %s",
                    log_range,
                ],
                cwd=state.path,
            )
            if not log.strip():
                self.append_output(f"No {mode} commits found for {state.name}.\n")
                self.append_output("✅ Preview complete. No changes were made.\n")
                return
            self.append_output(f"{title} for {state.name}:\n{log}\n")
            self.append_output("✅ Preview complete. You may review the output and close this view.\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            if self._is_no_internet_error(exc):
                self._show_no_internet_error(exc)
            else:
                messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")
        finally:
            self._end_operation()

    def _confirm_hard_reset(self, repo: Path, target_desc: str, reset_type: str) -> bool:
        if reset_type != "hard":
            return True
        is_dirty = not WorkingTreeManager.is_clean(repo)
        if is_dirty:
            try:
                status = GitOperations.run_git(["status", "--porcelain"], cwd=repo).strip()
                preview = "\n".join(status.splitlines()[:10])
                if len(status.splitlines()) > 10:
                    preview += "\n..."
            except GitManagerError:
                preview = ""
            detail = f"\n\nDirty files:\n{preview}" if preview else ""
            return messagebox.askyesno(
                "Confirm Hard Reset",
                f"Hard reset will discard staged and unstaged tracked changes and move the branch to {target_desc}.\n"
                f"Working tree is dirty (including untracked files shown below) – tracked changes will be PERMANENTLY LOST. "
                f"Untracked files will remain on disk after reset.{detail}\n\nContinue?",
                parent=self.root,
            )
        return messagebox.askyesno(
            "Confirm Hard Reset",
            f"Hard reset will discard uncommitted changes and move the branch to {target_desc}. Continue?",
            parent=self.root,
        )

    def action_reset(self) -> None:
        if not self._start_operation("reset the repository"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return

        try:
            # Unified dialog: Reset + Delete (pushed & local_commit)
            dialog = ManageCommitsDialog(
                self.root,
                state.path,
                state.name,
                state.base_branch,
                state.current_branch,
                state.local_exists,
                state.commit_count,
                self.theme_mode,
            )
            self.root.wait_window(dialog)
            if dialog.result is None:
                return

            res = dialog.result
            repo = state.path

            # --- Common mode: classic reset to target ---
            if res.get("mode") == "reset":
                target = res["target"]
                reset_type = res["type"]
                if not self._confirm_hard_reset(repo, target, reset_type):
                    return
                self.append_output(f"🔁 Resetting {state.name} to {target} with --{reset_type}...\n")
                GitOperations.run_git(["reset", f"--{reset_type}", target], cwd=repo)
                self.append_output(f"✅ Reset {state.name} to {target} with --{reset_type}\n")
                self.refresh_repos()
                self.append_output("✅ Reset complete. The repository is now on the target branch.\n")
                return

            # --- Delete mode: delete last N commits from branch ---
            branch = res["branch"]
            count = int(res["count"])
            reset_type = res.get("type", "hard")
            force_push = bool(res.get("force_push"))

            # Verify internet if force push needed
            if force_push and not has_internet_connection(timeout=3):
                self._show_no_internet_error(GitManagerError(f"{NO_INTERNET_MSG} — force push needs internet"))
                return

            # Determine if branch is pushed (has remote) for warning
            is_pushed_branch = branch == state.base_branch
            is_local = branch == "local_commit"

            # Preview commits to be deleted for final confirmation
            try:
                preview_log = GitOperations.run_git(
                    ["log", f"{branch}", f"-n{count}", "--oneline", "--date=short", "--pretty=format:%h %ad %s"],
                    cwd=repo,
                )
                preview = preview_log.strip() if preview_log.strip() else "(no log)"
            except GitManagerError:
                preview = "(unable to preview)"

            confirm_msg = (
                f"Delete {count} last commit(s) from '{branch}' in {state.name} with --{reset_type}?\n\n"
                f"Commits to be removed:\n{preview}\n\n"
                f"{'⚠️ These commits are already pushed to origin — a force push will be required!' if is_pushed_branch and force_push else ''}\n"
                f"{'⚠️ This will also affect remote if force pushed.' if is_pushed_branch else ''}\n"
                f"Continue?"
            )
            if not messagebox.askyesno("Confirm Delete Commits", confirm_msg, parent=self.root):
                return

            if not self._confirm_hard_reset(repo, f"{branch}~{count}", reset_type):
                return

            # Handle dirty worktree: stash if needed (similar to switch)
            stashed = False
            try:
                if not WorkingTreeManager.is_clean(repo):
                    if not messagebox.askyesno(
                        "Uncommitted Changes",
                        "Working tree not clean. Stash (incl. untracked) and continue delete?\n"
                        "This will also abort any ongoing merge/cherry-pick/rebase first.",
                        parent=self.root,
                    ):
                        self.append_output("⏭ Delete cancelled – working tree is dirty.\n")
                        return
                    self._abort_in_progress_ops(repo)
                    WorkingTreeManager.stash(repo, f"git-manager auto-stash before delete ({now_display()})")
                    stashed = True

                # Ensure we are on target branch before reset
                current = GitOperations.run_git(["branch", "--show-current"], cwd=repo).strip() or "HEAD"
                if current != branch:
                    # If branch does not exist locally, try to create from origin or fail
                    if not GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo):
                        if branch == state.base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], cwd=repo):
                            GitOperations.run_git(["checkout", "-b", branch, f"origin/{branch}"], cwd=repo)
                        else:
                            raise GitManagerError(f"Branch '{branch}' not found locally")
                    else:
                        BranchManager.checkout(repo, branch)

                # Create backup
                backup_name = f"backup_{branch}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                try:
                    GitOperations.run_git(["branch", backup_name, branch], cwd=repo)
                    self.append_output(f"🛟 Created backup {backup_name} from {branch} before delete\n")
                except GitManagerError as exc:
                    self.append_output(f"⚠️ Failed to create backup: {str(exc)}\n")

                # Determine target ref
                target_ref: str
                if is_local and state.base_branch:
                    # If deleting all pending, reset to base_branch directly
                    try:
                        pending_now = int(
                            GitOperations.run_git(["rev-list", "--count", f"{state.base_branch}..{branch}"], cwd=repo).strip() or "0"
                        )
                    except GitManagerError:
                        pending_now = count
                    if count >= pending_now:
                        target_ref = state.base_branch
                    else:
                        target_ref = f"HEAD~{count}"
                else:
                    target_ref = f"HEAD~{count}"

                self.append_output(f"🔁 Deleting {count} commit(s) from {branch} -> resetting to {target_ref} with --{reset_type}...\n")
                GitOperations.run_git(["reset", f"--{reset_type}", target_ref], cwd=repo)
                self.append_output(f"✅ Deleted {count} commit(s) from {branch}\n")

                if is_pushed_branch and force_push:
                    if not has_internet_connection(timeout=3):
                        self.append_output("⚠️ Internet offline — local delete done but remote not updated. Push manually later.\n")
                    else:
                        self.append_output(f"🚀 Force pushing {branch} to origin (with lease)...\n")
                        try:
                            GitOperations.run_git(["push", "--force-with-lease", "origin", f"{branch}:{branch}"], cwd=repo)
                            self.append_output(f"✅ Force pushed {branch} to origin\n")
                        except GitManagerError as exc:
                            if self._is_no_internet_error(exc):
                                self.append_output(f"⚠️ Force push failed due to internet: {str(exc)}\n")
                                self._show_no_internet_error(exc)
                            else:
                                raise

                if stashed:
                    try:
                        WorkingTreeManager.pop_stash(repo)
                        self.append_output("🔧 Restored stashed changes.\n")
                    except GitManagerError as exc:
                        self.append_output(f"⚠️ Stash pop failed: {str(exc)}\nResolve manually with 'git stash pop'\n")

                self.refresh_repos()
                self.append_output("✅ Delete complete. You may continue.\n")

            except GitManagerError:
                if stashed:
                    try:
                        WorkingTreeManager.pop_stash(repo)
                    except GitManagerError:
                        self.append_output("⚠️ Stash remains – resolve manually with 'git stash pop'\n")
                raise

        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            if self._is_no_internet_error(exc):
                self._show_no_internet_error(exc)
            else:
                messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")
        finally:
            self._end_operation()

    def action_make_commit(self) -> None:
        if not self._start_operation("make a commit"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return

        repo = state.path
        try:
            GitConfig.ensure_identity(repo)

            if WorkingTreeManager.is_clean(repo):
                messagebox.showinfo("No changes", "There are no changes to commit in the selected repository.")
                return

            dialog = CommitDialog(self.root, state.name, self.theme_mode)
            self.root.wait_window(dialog)
            if dialog.result is None:
                return

            # Support both old (3-tuple) and new (5-tuple) result for backward compat
            if len(dialog.result) == 5:
                message, add_mode, pathspec, date_mode, custom_iso = dialog.result
            else:
                message, add_mode, pathspec = dialog.result  # type: ignore
                date_mode, custom_iso = "current", None
            # Determine commit date
            if date_mode == "custom" and custom_iso:
                iso_value = custom_iso
                self.append_output(f"📅 Using custom date/time: {iso_value}\n")
            else:
                iso_value = now_iso()
                self.append_output(f"📅 Using current date/time: {iso_value}\n")

            # Future warning (second layer, in case dialog warning was bypassed)
            if is_future(iso_value):
                if not messagebox.askyesno(
                    "Future commit warning",
                    f"هشدار: این کامیت برای آینده است!\n\nتاریخ: {iso_value}\nزمان فعلی: {now_display()}\n\nآیا می‌خواهید کامیت انجام شود؟",
                    parent=self.root,
                ):
                    self.append_output("⏭ Commit cancelled — future date not confirmed.\n")
                    return

            self.append_output(f"📝 Preparing commit in {state.name}...\n")

            if add_mode == "all":
                self.append_output("   • Staging all changes (tracked + untracked)\n")
                GitOperations.run_git(["add", "-A"], cwd=repo)
            elif add_mode == "tracked":
                self.append_output("   • Staging tracked changes only\n")
                GitOperations.run_git(["add", "-u"], cwd=repo)
            else:
                self.append_output(f"   • Staging specified paths: {pathspec}\n")
                import shlex

                try:
                    parts = shlex.split(pathspec, posix=True)
                except ValueError as exc:
                    raise GitManagerError(f"Invalid pathspec: {exc}") from exc
                if not parts:
                    raise GitManagerError("No valid pathspec provided")
                # Validate no empty and no dangerous patterns are silently ignored;
                # shlex already handles quoted spaces correctly.
                GitOperations.run_git(["add", *parts], cwd=repo)

            if GitOperations.git_ok(["diff", "--cached", "--quiet"], cwd=repo):
                messagebox.showinfo("Nothing staged", "No changes were staged for commit. Adjust the add scope and try again.")
                return

            if date_mode == "custom" and custom_iso:
                GitOperations.run_git_env(
                    ["commit", "-m", message.strip(), "--date", custom_iso],
                    cwd=repo,
                    extra_env={"GIT_AUTHOR_DATE": custom_iso, "GIT_COMMITTER_DATE": custom_iso},
                )
            else:
                # For current time also ensure is_future already warned; use normal commit
                # If current iso is future, use env to make explicit
                if is_future(iso_value):
                    GitOperations.run_git_env(
                        ["commit", "-m", message.strip(), "--date", iso_value],
                        cwd=repo,
                        extra_env={"GIT_AUTHOR_DATE": iso_value, "GIT_COMMITTER_DATE": iso_value},
                    )
                else:
                    GitOperations.run_git(["commit", "-m", message.strip()], cwd=repo)
            self.append_output(f"✅ Commit created in {state.name}: {message.strip()}")
            self.refresh_repos()
            self.append_output("✅ Commit complete. You may close the app or continue working.\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            if self._is_no_internet_error(exc):
                self._show_no_internet_error(exc)
            else:
                messagebox.showerror("Commit Failed", "An error occurred while committing. Check the output panel for details.")
        finally:
            self._end_operation()

    def action_move(self) -> None:
        if not self._start_operation("move commits"):
            return
        state = self.selected_state()
        if not state:
            self._end_operation()
            return
        repo = state.path
        base_branch = state.base_branch
        temp_branch: str | None = None
        base_before: str | None = None
        local_before: str | None = None
        stashed = False
        original_branch = "HEAD"
        try:
            GitConfig.ensure_identity(repo)
            if not GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "local_commit"], cwd=repo):
                raise GitManagerError("local_commit does not exist")

            if GitOperations.git_ok(["remote", "get-url", "origin"], cwd=repo):
                # Proactive internet check with Persian error before touching network
                if not has_internet_connection(timeout=3.0):
                    raise GitManagerError(f"{NO_INTERNET_MSG} — fetch متوقف شد چون اینترنت وصل نیست. لطفاً اتصال اینترنت را بررسی کنید.")
                try:
                    self.append_output("🔄 Fetching origin before move...\n")
                    GitOperations.run_git(["fetch", "--prune", "origin"], cwd=repo)
                except GitManagerError as exc:
                    if self._is_no_internet_error(exc):
                        raise GitManagerError(f"{NO_INTERNET_MSG} — fetch ناموفق بود: {str(exc)}") from exc
                    raise GitManagerError(
                        f"Failed to fetch origin before move. Remote is unavailable or access is denied: {str(exc)}"
                    ) from exc

            remote_base = f"origin/{base_branch}"
            if base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/{remote_base}"], cwd=repo):
                ahead = int(
                    GitOperations.run_git(["rev-list", "--count", f"{base_branch}..{remote_base}"], cwd=repo).strip() or "0"
                )
                behind = int(
                    GitOperations.run_git(["rev-list", "--count", f"{remote_base}..{base_branch}"], cwd=repo).strip() or "0"
                )
                if ahead > 0 and behind > 0:
                    raise GitManagerError(
                        f"Local {base_branch} diverges from {remote_base}. Sync or rebase before moving commits."
                    )
                if ahead > 0:
                    self.append_output(f"ℹ️ Local {base_branch} is behind {remote_base}; applying commits onto remote history.\n")
                    start_ref = remote_base
                elif behind > 0:
                    raise GitManagerError(
                        f"Local {base_branch} has unpushed commits. Push or rebase it before moving commits."
                    )
                else:
                    start_ref = base_branch
            else:
                start_ref = base_branch

            base_before = GitOperations.run_git(["rev-parse", "--verify", start_ref], cwd=repo).strip()
            local_before = GitOperations.run_git(["rev-parse", "--verify", "local_commit"], cwd=repo).strip()
            pending = int(GitOperations.run_git(["rev-list", "--count", f"{base_branch}..local_commit"], cwd=repo).strip() or "0")
            if pending == 0:
                messagebox.showinfo("No commits", "No commits to move.")
                return

            # Fetch last commit on base for date validation and display
            last_commit_info = None
            last_commit_iso = None
            try:
                if GitOperations.git_ok(["rev-parse", "--verify", "--quiet", start_ref], cwd=repo):
                    try:
                        last_commit_info = GitOperations.run_git(
                            ["log", "-1", "--date=iso", "--pretty=format:%h  %ad  %s", start_ref], cwd=repo
                        ).strip()
                        last_commit_iso = GitOperations.run_git(
                            ["log", "-1", "--pretty=format:%aI", start_ref], cwd=repo
                        ).strip()
                        if not last_commit_info:
                            last_commit_info = None
                            last_commit_iso = None
                    except GitManagerError:
                        last_commit_info = None
                        last_commit_iso = None
            except GitManagerError:
                pass

            dialog = NumericKeypadDialog(
                self.root,
                "Move commits",
                f"How many commits to move to {state.base_branch}?\n(1 to {pending})",
                minvalue=1,
                maxvalue=pending,
                theme_mode=self.theme_mode,
                show_date_options=True,
                last_commit_info=last_commit_info,
                last_commit_iso=last_commit_iso,
            )
            self.root.wait_window(dialog)
            num = dialog.result
            if num is None:
                return
            # Determine commit date/time to use
            if getattr(dialog, "date_mode", "current") == "custom" and getattr(dialog, "custom_iso", None):
                iso_value = dialog.custom_iso  # already validated to be after last commit
                self.append_output(f"📅 Using custom date/time: {iso_value} (after last commit {last_commit_iso or 'N/A'})\n")
            else:
                iso_value = now_iso()
                if last_commit_iso:
                    self.append_output(f"📅 Using current date/time: {iso_value}\n")
            # Extra safety: ensure chosen date is after last commit even if dialog validation was bypassed
            if last_commit_iso:
                try:
                    from utils.time_utils import is_after_last_commit as _is_after

                    if not _is_after(iso_value, last_commit_iso):
                        raise GitManagerError(
                            f"Chosen date/time {iso_value} must be after last commit on {base_branch} ({last_commit_iso}). "
                            f"Last commit info: {last_commit_info}"
                        )
                except GitManagerError:
                    raise
                except Exception:
                    pass

            # Future commit warning
            if is_future(iso_value):
                if not messagebox.askyesno(
                    "Future commit warning",
                    f"هشدار: این کامیت برای آینده است!\n\nتاریخ انتخابی: {iso_value}\nزمان فعلی: {now_display()}\n\nآیا می‌خواهید ادامه دهید؟",
                    parent=self.root,
                ):
                    self.append_output("⏭ Move cancelled — future date not confirmed.\n")
                    return

            original_branch = GitOperations.run_git(["branch", "--show-current"], cwd=repo).strip() or "HEAD"
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

            all_commits = GitOperations.run_git(["rev-list", "--reverse", f"{base_branch}..local_commit"], cwd=repo).strip().splitlines()
            if not all_commits:
                raise GitManagerError("No commits to process")
            commits = all_commits[:num]  # Only process the first num commits
            processed: list[str] = []

            self.append_output(f"🕒 Rewriting commits with current user info...\n")
            expected_email = GitOperations.run_git(["config", "user.email"], cwd=repo).strip()
            expected_name = GitOperations.run_git(["config", "user.name"], cwd=repo).strip()
            self.append_output(f"⚠️  All commits will be authored by: {expected_name} <{expected_email}>\n")

            temp_branch = f"tmp_git_manager_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            GitOperations.run_git(["branch", temp_branch, base_before], cwd=repo)
            BranchManager.checkout(repo, temp_branch)
            now_iso_value = iso_value  # current or custom, already validated
            for idx, commit in enumerate(commits):
                remaining = len(commits) - idx - 1
                subject = GitOperations.run_git(["show", "-s", "--format=%s", commit], cwd=repo).strip()
                self.append_output(f"📌 Processing {idx + 1}/{len(commits)}: {commit[:7]} '{subject}' ({remaining} remaining)...\n")
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

                # Check if there are any staged changes to commit (ignore untracked files)
                has_staged_changes = not GitOperations.git_ok(["diff", "--cached", "--quiet"], cwd=repo)
                if not has_staged_changes:
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
                BranchManager.checkout(repo, original_branch)
                if stashed:
                    try:
                        WorkingTreeManager.pop_stash(repo)
                    except GitManagerError as exc:
                        self.append_output(f"⚠️ Stash pop failed: {str(exc)}\nResolve manually with 'git stash pop'\n")
                return

            self.append_output(f"📜 Latest moved commits on {base_branch} (with author info):\n")
            latest_log = GitOperations.run_git(["log", "-n", str(processed_count), temp_branch, "--no-decorate", "--date=iso", "--pretty=format:  %h  %ad  %an <%ae>"], cwd=repo)
            self.append_output(latest_log + "\n")

            # ===== Pre-push validation =====
            self.append_output("🔍 Validating commits before push...\n")
            # 1) Ensure remote default branch matches target base branch
            if GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "origin/HEAD"], cwd=repo):
                remote_head = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo).strip().removeprefix("origin/")
                if remote_head and remote_head != base_branch:
                    raise GitManagerError(
                        f"Remote default branch is '{remote_head}', but target is '{base_branch}'."
                    )

            # 2) Ensure author date day equals chosen date's day for all moved commits
            dates = GitOperations.run_git(["log", "-n", str(processed_count), temp_branch, "--date=short", "--pretty=format:%ad"], cwd=repo).splitlines()
            expected_date_str = iso_value[:10]
            bad_dates = [d for d in dates if d and d != expected_date_str]
            if bad_dates:
                raise GitManagerError(f"Found {len(bad_dates)} commit(s) with author date not equal to {expected_date_str}")

            # 3) Ensure author email matches local git config (so GitHub can attribute contributions)
            emails = GitOperations.run_git(["log", "-n", str(processed_count), temp_branch, "--pretty=format:%ae"], cwd=repo).splitlines()
            names = GitOperations.run_git(["log", "-n", str(processed_count), temp_branch, "--pretty=format:%an"], cwd=repo).splitlines()
            if any(e and e != expected_email for e in emails):
                raise GitManagerError(f"Found commit(s) with author email not matching '{expected_email}'")
            if any(n and n != expected_name for n in names):
                raise GitManagerError(f"Found commit(s) with author name not matching '{expected_name}'")

            self.append_output(f"✅ All {processed_count} commits have correct author info (will be attributed to {expected_name} <{expected_email}>)\n")
            if not has_internet_connection(timeout=3.0):
                raise GitManagerError(f"{NO_INTERNET_MSG} — push متوقف شد چون اینترنت وصل نیست. لطفاً اتصال اینترنت را بررسی کنید.")
            self.append_output(f"🚀 Pushing to origin {base_branch}...\n")
            try:
                GitOperations.run_git(["push", "origin", f"{temp_branch}:{base_branch}"], cwd=repo)
            except GitManagerError as exc:
                if self._is_no_internet_error(exc):
                    raise GitManagerError(f"{NO_INTERNET_MSG} — push ناموفق بود: {str(exc)}") from exc
                raise
            self.append_output(f"✅ Done! {processed_count} commits moved with date/time {now_iso_value}\n")

            BranchManager.checkout(repo, base_branch)
            GitOperations.run_git(["reset", "--hard", temp_branch], cwd=repo)

            # ===== Clean up local_commit ONLY AFTER successful push =====
            backup_branch = self._backup_local_commit(repo)
            
            # Check if we moved all commits or only some
            if processed_count < pending:
                # Some commits remain on local_commit - need to rewrite it
                # Get the remaining commits BEFORE any changes (using original SHAs)
                remaining_original = all_commits[processed_count:]  # The commits we didn't process
                
                self.append_output(f"⚠️  You moved {processed_count} of {pending} commits.\n")
                self.append_output(f"🔄 Rewriting local_commit to keep only {len(remaining_original)} remaining commits...\n")
                BranchManager.checkout(repo, "local_commit")
                GitOperations.run_git(["reset", "--hard", base_branch], cwd=repo)
                
                for commit in remaining_original:
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
                                GitOperations.run_git(["commit", "-C", commit], cwd=repo)
                                self.append_output(f"✓ Resolved with ours for {commit[:7]}\n")
                                continue

                            if choice == "theirs":
                                GitOperations.run_git(["checkout", "--theirs", "."], cwd=repo)
                                GitOperations.run_git(["add", "."], cwd=repo)
                                GitOperations.run_git(["commit", "-C", commit], cwd=repo)
                                self.append_output(f"✓ Resolved with theirs for {commit[:7]}\n")
                                continue

                            if choice == "skip":
                                GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                                self.append_output(f"⊘ Skipping commit {commit[:7]} after conflicts\n")
                                continue

                            GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                            raise GitManagerError("Cherry-pick aborted for manual resolution")

                        # Consistent empty-check with first loop (staged, not working tree)
                        # Use --cached to detect staged changes after --no-commit
                        if GitOperations.git_ok(["diff", "--cached", "--quiet"], cwd=repo):
                            self.append_output(f"⊘ Skipping empty commit {commit[:7]} (already on {base_branch})\n")
                            GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                            continue
                        # Otherwise abort and raise error
                        GitOperations.run_git(["cherry-pick", "--abort"], cwd=repo)
                        raise GitManagerError(
                            f"Cherry-pick failed while rewriting local_commit for commit {commit}. Resolve manually."
                        )
                    else:
                        # Preserve original author/date for remaining commits (intentionally different from moved commits which use new date)
                        GitOperations.run_git(["commit", "-C", commit], cwd=repo)
                self.append_output("✅ local_commit updated to reflect remaining commits.\n")
            else:
                # All commits were moved - simply sync local_commit to base
                self.append_output(f"🔄 Syncing local_commit to {base_branch}...\n")
                BranchManager.checkout(repo, "local_commit")
                GitOperations.run_git(["reset", "--hard", base_branch], cwd=repo)
                self.append_output(f"✅ local_commit is now aligned with {base_branch}\n")

            if stashed:
                self.append_output(f"🔧 Restoring stashed changes to {original_branch}...\n")
                BranchManager.checkout(repo, original_branch)
                try:
                    WorkingTreeManager.pop_stash(repo)
                except GitManagerError as exc:
                    self.append_output(f"⚠️ Stash pop failed: {str(exc)}\nResolve manually with 'git stash pop'\n")
            else:
                # Restore original branch when no stash – previously stayed on local_commit
                if original_branch != "HEAD" and original_branch not in (base_branch, "local_commit"):
                    try:
                        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{original_branch}"], cwd=repo):
                            cur = GitOperations.run_git(["branch", "--show-current"], cwd=repo).strip()
                            if cur != original_branch:
                                BranchManager.checkout(repo, original_branch)
                    except GitManagerError:
                        pass
                elif original_branch == base_branch:
                    try:
                        cur = GitOperations.run_git(["branch", "--show-current"], cwd=repo).strip()
                        if cur != base_branch:
                            BranchManager.checkout(repo, base_branch)
                    except GitManagerError:
                        pass

            if temp_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{temp_branch}"], cwd=repo):
                try:
                    GitOperations.run_git(["branch", "-D", temp_branch], cwd=repo)
                except GitManagerError:
                    pass
                temp_branch = None
            self.refresh_repos()
            self.append_output("✅ Move complete. local_commit and the base branch are now updated.\n")
        except GitManagerError as exc:
            self.append_output(f"\n❌ Error: {str(exc)}\n")
            if temp_branch or base_before or local_before:
                self.append_output("↩️ Rolling back to previous state...\n")
                try:
                    self._abort_in_progress_ops(repo)
                except GitManagerError:
                    pass
                if base_before and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
                    try:
                        BranchManager.checkout(repo, base_branch)
                        GitOperations.run_git(["reset", "--hard", base_before], cwd=repo)
                    except GitManagerError:
                        pass
                if local_before and GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=repo):
                    try:
                        BranchManager.checkout(repo, "local_commit")
                        GitOperations.run_git(["reset", "--hard", local_before], cwd=repo)
                    except GitManagerError:
                        pass
                if temp_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{temp_branch}"], cwd=repo):
                    try:
                        GitOperations.run_git(["branch", "-D", temp_branch], cwd=repo)
                    except GitManagerError:
                        pass
                    temp_branch = None
                # Always restore original branch, not just when stashed
                if original_branch != "HEAD":
                    try:
                        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{original_branch}"], cwd=repo):
                            BranchManager.checkout(repo, original_branch)
                    except GitManagerError:
                        pass
                if stashed:
                    try:
                        WorkingTreeManager.pop_stash(repo)
                    except GitManagerError:
                        self.append_output("⚠️ Rollback stash pop failed. Resolve manually with 'git stash pop'\n")
            if self._is_no_internet_error(exc):
                self._show_no_internet_error(exc)
            else:
                messagebox.showerror("Operation Failed", "An error occurred. Check the output panel for details.")
        finally:
            # Guarantee temp_branch cleanup even if exception occurred before except block
            if temp_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{temp_branch}"], cwd=repo):
                try:
                    GitOperations.run_git(["branch", "-D", temp_branch], cwd=repo)
                except GitManagerError:
                    pass
            self._end_operation()
