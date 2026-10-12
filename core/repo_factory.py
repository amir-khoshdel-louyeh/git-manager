#!/usr/bin/env python3
"""Factory for creating and onboarding new repositories.

Two entry points used by the New Repository dialog:

- clone_repo(): clone a remote URL into the base directory, then ensure
  the base branch and local_commit exist.
- setup_new_repo(): onboard a repo that already exists on disk (e.g. the
  user cloned it manually via terminal) but has no base / local_commit yet.
- find_pending_setups(): scan the base directory and return the repos
  that need onboarding (the "suggestions" list).
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.branch_manager import BranchManager
from core.git_operations import GitManagerError, GitOperations
from core.repo_scanner import RepoScanner


@dataclass
class PendingSetup:
    name: str
    path: Path
    current_branch: str
    base_branch: str
    reason: str


def derive_folder_name(url: str) -> str:
    """Derive a folder name from a git URL (strip trailing slash/.git)."""
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    # Take last path segment (handles https://, ssh, scp-like git@host:path)
    last = re.split(r"[:/]", cleaned)[-1]
    name = last.strip()
    if not name:
        raise GitManagerError("Could not derive a folder name from the URL – please enter one manually.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise GitManagerError(f"Derived folder name '{name}' looks invalid – please enter one manually.")
    return name


def _has_commits(repo: Path) -> bool:
    return GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=repo)


def _has_any_commits(repo: Path) -> bool:
    """True if the repo has commits anywhere (HEAD or any remote branch).

    A fresh clone whose remote HEAD points elsewhere can have an unborn
    local HEAD while origin/main already has commits – that repo IS usable.
    """
    try:
        out = GitOperations.run_git(["rev-list", "--all", "--count"], cwd=repo).strip()
        return int(out or "0") > 0
    except (GitManagerError, ValueError):
        return _has_commits(repo)


def _ensure_base_branch(repo: Path, base_branch: str) -> str:
    """Make sure a local base branch exists; return its name.

    Order: local base wins → origin/<base> → origin/HEAD target →
    current branch (renamed/copied to base) → error.
    """
    if not base_branch:
        raise GitManagerError("Base branch name is empty.")

    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
        return base_branch

    if GitOperations.git_ok(
        ["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo
    ):
        GitOperations.run_git(["checkout", "-b", base_branch, f"origin/{base_branch}"], cwd=repo)
        return base_branch

    # origin/HEAD may point at the real default (e.g. main vs master mismatch)
    try:
        remote_head = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo).strip()
    except GitManagerError:
        remote_head = ""
    if remote_head and remote_head != "HEAD" and remote_head.startswith("origin/"):
        remote_branch = remote_head.removeprefix("origin/")
        if GitOperations.git_ok(
            ["show-ref", "--verify", "--quiet", f"refs/remotes/{remote_head}"], cwd=repo
        ):
            GitOperations.run_git(["checkout", "-b", base_branch, remote_head], cwd=repo)
            return base_branch

    # Last resort for repos with no remote: adopt the single current branch.
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "-q", "HEAD"],
        cwd=str(repo), text=True, capture_output=True, check=False,
    )
    current = result.stdout.strip()
    if current and current not in {"HEAD", "local_commit"} and GitOperations.git_ok(
        ["show-ref", "--verify", "--quiet", f"refs/heads/{current}"], cwd=repo
    ):
        if current == base_branch:
            return base_branch
        GitOperations.run_git(["branch", base_branch, current], cwd=repo)
        return base_branch

    raise GitManagerError(
        f"Cannot establish base branch '{base_branch}' – not found locally or on origin."
    )


def setup_new_repo(repo: Path, base_branch: str = "main") -> str:
    """Onboard an existing repo: ensure base + local_commit. Return base name."""
    if not (repo / ".git").is_dir():
        raise GitManagerError(f"'{repo}' is not a git repository.")

    if not _has_any_commits(repo):
        raise GitManagerError(
            f"'{repo.name}' has no commits yet – make an initial commit first, "
            "then set it up (branches cannot exist without a commit)."
        )

    base = _ensure_base_branch(repo, base_branch)
    # BranchManager is strict: creates local_commit only from a real base,
    # materializing the local base from origin if needed.
    BranchManager.switch_to_local_commit(repo, base)
    return base


def clone_repo(base_dir: Path, url: str, folder_name: str | None = None, base_branch: str = "main") -> Path:
    """Clone url into base_dir and onboard it. Return the new repo path."""
    base_dir = base_dir.expanduser()
    if not base_dir.is_dir():
        raise GitManagerError(f"Base directory '{base_dir}' not found.")
    url = url.strip()
    if not url:
        raise GitManagerError("Please enter a repository URL.")
    name = (folder_name or "").strip() or derive_folder_name(url)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise GitManagerError(f"Folder name '{name}' is invalid (use letters, digits, . _ -).")
    dest = base_dir / name
    if dest.exists():
        raise GitManagerError(f"'{dest}' already exists – pick another folder name or remove it.")

    GitOperations.run_git(["clone", url, str(dest)], cwd=base_dir, timeout=300)
    try:
        setup_new_repo(dest, base_branch)
    except GitManagerError as exc:
        # Keep the clone so the user can fix it manually, but explain.
        raise GitManagerError(f"Cloned to '{name}' but setup failed: {exc}") from exc
    return dest


def find_pending_setups(base_dir: Path) -> list[PendingSetup]:
    """Return repos under base_dir that miss a base branch or local_commit.

    These are the "did you mean this one?" suggestions shown when the user
    cloned something manually via terminal.
    """
    base_dir = base_dir.expanduser()
    if not base_dir.is_dir():
        return []
    try:
        states = RepoScanner.scan(base_dir)
    except GitManagerError:
        return []

    pending: list[PendingSetup] = []
    for state in states:
        if state.local_exists and state.base_branch:
            continue
        if not state.base_branch:
            reason = "no base branch (main/master missing)"
        elif not state.local_exists:
            reason = f"no local_commit (base: {state.base_branch})"
        else:
            reason = "needs setup"
        pending.append(
            PendingSetup(
                name=state.name,
                path=state.path,
                current_branch=state.current_branch,
                base_branch=state.base_branch,
                reason=reason,
            )
        )
    return pending
