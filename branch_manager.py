#!/usr/bin/env python3
"""Branch management helpers."""
from __future__ import annotations

from pathlib import Path

from git_operations import GitOperations, GitManagerError


class BranchManager:
    """Utilities for switching and creating branches."""

    @staticmethod
    def checkout(repo: Path, branch: str) -> None:
        GitOperations.run_git(["checkout", branch], cwd=repo)

    @staticmethod
    def switch_to_local_commit(repo: Path, base_branch: str, current_branch: str | None = None) -> str:
        """Switch to local_commit, creating it from a sensible start point if missing."""
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=repo):
            GitOperations.run_git(["checkout", "local_commit"], cwd=repo)
            return "local_commit"

        start_ref = base_branch
        if not GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{start_ref}"], cwd=repo):
            start_ref = current_branch or start_ref

        if start_ref and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{start_ref}"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", "local_commit", start_ref], cwd=repo)
            return "local_commit"

        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", "local_commit", f"origin/{base_branch}"], cwd=repo)
            return "local_commit"

        GitOperations.run_git(["checkout", "-b", "local_commit"], cwd=repo)
        return "local_commit"

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
