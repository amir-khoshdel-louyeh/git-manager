#!/usr/bin/env python3
"""Branch management helpers."""
from __future__ import annotations

from pathlib import Path

from core.git_operations import GitManagerError, GitOperations


class BranchManager:
    """Utilities for switching and creating branches."""

    @staticmethod
    def checkout(repo: Path, branch: str) -> None:
        GitOperations.run_git(["checkout", branch], cwd=repo)

    @staticmethod
    def switch_to_local_commit(repo: Path, base_branch: str, current_branch: str | None = None) -> str:
        """Switch to local_commit, creating it from the base branch if missing.

        Strict rule: never create local_commit when the repo has no real base
        branch. Fallbacks to current_branch/HEAD/origin-HEAD are intentionally
        NOT used anymore, because they produced a local_commit without main.
        """
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=repo):
            GitOperations.run_git(["checkout", "local_commit"], cwd=repo)
            return "local_commit"

        if not base_branch:
            raise GitManagerError(
                "Cannot create local_commit – base branch not detected (main/master missing). "
                "Create/push main first, then switch."
            )

        # Preferred: local base branch must exist.
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", "local_commit", base_branch], cwd=repo)
            return "local_commit"

        # Fallback: remote base exists but local base not yet created.
        # Materialize the local base first so local_commit always has a main.
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", base_branch, f"origin/{base_branch}"], cwd=repo)
            GitOperations.run_git(["checkout", "-b", "local_commit", base_branch], cwd=repo)
            return "local_commit"

        raise GitManagerError(
            f"Cannot create local_commit – base branch '{base_branch}' not found locally or on origin. "
            "Create/push it first."
        )

    @staticmethod
    def switch_to_base(repo: Path, base_branch: str) -> str:
        """Switch to the detected base branch, creating it from origin if needed."""
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{base_branch}"], cwd=repo):
            GitOperations.run_git(["checkout", base_branch], cwd=repo)
            return base_branch

        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", base_branch, f"origin/{base_branch}"], cwd=repo)
            return base_branch

        raise GitManagerError(f"Base branch '{base_branch}' not found locally or on origin")
