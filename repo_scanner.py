#!/usr/bin/env python3
"""Repository discovery and state computation."""
from __future__ import annotations

from pathlib import Path
from typing import List

from git_operations import GitOperations, GitManagerError
from repo_state import RepoState


def _detect_base_branch(repo: Path) -> str:
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
    return "main"


def _ensure_main_branch(repo: Path) -> None:
    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/main"], cwd=repo):
        return
    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/master"], cwd=repo):
        try:
            GitOperations.run_git(["branch", "main", "master"], cwd=repo)
        except GitManagerError:
            pass
        return
    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/remotes/origin/main"], cwd=repo):
        try:
            GitOperations.run_git(["branch", "main", "origin/main"], cwd=repo)
        except GitManagerError:
            pass
        return
    if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/remotes/origin/master"], cwd=repo):
        try:
            GitOperations.run_git(["branch", "main", "origin/master"], cwd=repo)
        except GitManagerError:
            pass
        return
    try:
        GitOperations.run_git(["branch", "main"], cwd=repo)
    except GitManagerError:
        pass


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


def _pending_count(repo: Path, base_branch: str) -> int:
    if not GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "local_commit"], cwd=repo):
        return 0
    if not GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
        return 0
    out = GitOperations.run_git(["rev-list", "--count", f"{base_branch}..local_commit"], cwd=repo)
    return int(out.strip() or "0")


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

            # Ensure a main branch exists to make comparisons reliable
            _ensure_main_branch(child)
            base_branch = _detect_base_branch(child)
            branch = _current_branch(child)
            local_exists = branch == "local_commit" or GitOperations.git_ok(
                ["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=child
            )
            count = _pending_count(child, base_branch) if local_exists else 0

            states.append(
                RepoState(
                    path=child,
                    name=child.name,
                    base_branch=base_branch,
                    current_branch=branch,
                    local_exists=local_exists,
                    commit_count=count,
                )
            )
        return states
