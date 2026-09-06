#!/usr/bin/env python3
"""Working tree utilities."""
from __future__ import annotations

from pathlib import Path

from core.git_operations import GitOperations


class WorkingTreeManager:
    """Helpers for stashing and cleanliness checks."""

    @staticmethod
    def is_clean(repo: Path) -> bool:
        # Use porcelain status so untracked files are also considered dirty
        # (previous diff --quiet checks missed untracked files).
        try:
            status = GitOperations.run_git(["status", "--porcelain"], cwd=repo)
        except Exception:
            # If git status fails, treat as dirty to be safe (conservative)
            return False
        return not bool(status.strip())

    @staticmethod
    def stash(repo: Path, message: str) -> None:
        GitOperations.run_git(["stash", "push", "-u", "-m", message], cwd=repo)

    @staticmethod
    def pop_stash(repo: Path) -> None:
        GitOperations.run_git(["stash", "pop"], cwd=repo)
