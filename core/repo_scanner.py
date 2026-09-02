#!/usr/bin/env python3
"""Repository discovery and state computation."""
from __future__ import annotations

from pathlib import Path
from typing import List

from core.git_operations import GitManagerError, GitOperations
from core.repo_state import RepoState


def _detect_base_branch(repo: Path, current_branch: str) -> str:
    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/main"], cwd=repo):
        return "main"
    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/master"], cwd=repo):
        return "master"

    origin_head = (
        GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo).strip()
        if GitOperations.git_ok(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo)
        else ""
    )
    if origin_head and origin_head != "HEAD":
        return origin_head.removeprefix("origin/")

    # If no main/master/origin default exists yet, create a real main branch when safe.
    created_main = _ensure_main_branch(repo, current_branch)
    if created_main:
        return created_main

    if current_branch and current_branch not in {"HEAD", "local_commit"} and GitOperations.git_ok(
        ["show-ref", "--verify", "--quiet", f"refs/heads/{current_branch}"], cwd=repo
    ):
        return current_branch
    return ""


def _ensure_main_branch(repo: Path, current_branch: str) -> str:
    """Create a real main branch from a safe existing branch if needed."""
    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/main"], cwd=repo):
        return "main"

    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/master"], cwd=repo):
        try:
            GitOperations.run_git(["branch", "main", "master"], cwd=repo)
            return "main"
        except GitManagerError:
            return "master"

    if current_branch and current_branch not in {"HEAD", "local_commit"}:
        branch_list = GitOperations.run_git(
            ["for-each-ref", "--format=%(refname:short)", "refs/heads"],
            cwd=repo,
        ).splitlines()
        if len(branch_list) == 1 and branch_list[0] == current_branch:
            try:
                GitOperations.run_git(["branch", "main", current_branch], cwd=repo)
                return "main"
            except GitManagerError:
                pass
    return ""


def _current_branch(repo: Path) -> str:
    # Use subprocess directly to avoid raising when HEAD is detached.
    import subprocess

    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "-q", "HEAD"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    branch = result.stdout.strip()
    return branch or "HEAD"


def _pending_count(repo: Path, base_branch: str, current_branch: str) -> int:
    """Count commits ahead of base branch or remote on the current branch."""
    if not base_branch:
        return 0

    # If we're on local_commit, show commits between base..local_commit
    if current_branch == "local_commit":
        if not GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "local_commit"], cwd=repo):
            return 0
        if not GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
            return 0
        out = GitOperations.run_git(["rev-list", "--count", f"{base_branch}..local_commit"], cwd=repo)
        return int(out.strip() or "0")

    # If we're on the base branch (MAIN), show unpushed commits (ahead of origin)
    if current_branch == base_branch:
        if not GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
            return 0
        # Check if remote tracking branch exists
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
            out = GitOperations.run_git(["rev-list", "--count", f"origin/{base_branch}..{base_branch}"], cwd=repo)
            return int(out.strip() or "0")
        # If no remote, show total commits on the branch
        out = GitOperations.run_git(["rev-list", "--count", base_branch], cwd=repo)
        return int(out.strip() or "0")

    # For any other branch, show commits ahead of base
    if not GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
        return 0
    out = GitOperations.run_git(["rev-list", "--count", f"{base_branch}..{current_branch}"], cwd=repo)
    return int(out.strip() or "0")


def _has_uncommitted_changes(repo: Path) -> bool:
    """Return True if the repository has unstaged, staged, or untracked changes."""
    status = GitOperations.run_git(["status", "--porcelain"], cwd=repo)
    return bool(status.strip())


def _pushed_count(repo: Path, base_branch: str) -> int:
    """Return the number of commits pushed to the remote base branch, when available."""
    if base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
        out = GitOperations.run_git(["rev-list", "--count", f"origin/{base_branch}"], cwd=repo)
        return int(out.strip() or "0")

    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/remotes/origin/HEAD"], cwd=repo):
        out = GitOperations.run_git(["rev-list", "--count", "origin/HEAD"], cwd=repo)
        return int(out.strip() or "0")

    if GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "refs/remotes/origin"], cwd=repo):
        out = GitOperations.run_git(["rev-list", "--count", "--remotes=origin"], cwd=repo)
        return int(out.strip() or "0")

    return 0


class RepoScanner:
    """Scan a base directory for git repositories and compute their state."""

    @staticmethod
    def scan(base_dir: Path) -> List[RepoState]:
        base_dir = base_dir.expanduser()
        if not base_dir.is_dir():
            raise GitManagerError(f"Base directory '{base_dir}' not found")

        states: List[RepoState] = []
        for child in sorted(base_dir.iterdir()):
            if not child.is_dir() or not (child / ".git").is_dir():
                continue

            branch = _current_branch(child)
            base_branch = _detect_base_branch(child, branch)
            local_exists = branch == "local_commit" or GitOperations.git_ok(
                ["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=child
            )
            count = _pending_count(child, base_branch, branch)

            states.append(
                RepoState(
                    path=child,
                    name=child.name,
                    base_branch=base_branch,
                    current_branch=branch,
                    local_exists=local_exists,
                    commit_count=count,
                    pushed_count=_pushed_count(child, base_branch),
                    dirty=_has_uncommitted_changes(child),
                )
            )
        return states
