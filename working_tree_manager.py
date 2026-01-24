#!/usr/bin/env python3
"""Working tree utilities."""
from __future__ import annotations

from pathlib import Path

from git_operations import GitOperations


class WorkingTreeManager:
    """Helpers for stashing and cleanliness checks."""

    @staticmethod
    def is_clean(repo: Path) -> bool:
        return GitOperations.git_ok(["diff", "--quiet"], cwd=repo) and GitOperations.git_ok(["diff", "--cached", "--quiet"], cwd=repo)

    @staticmethod
    def stash(repo: Path, message: str) -> None:
        GitOperations.run_git(["stash", "push", "-u", "-m", message], cwd=repo)

    @staticmethod
    def pop_stash(repo: Path) -> None:
        GitOperations.run_git(["stash", "pop"], cwd=repo)
