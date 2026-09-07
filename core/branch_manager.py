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
        """Switch to local_commit, creating it from a sensible start point if missing."""
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/heads/local_commit"], cwd=repo):
            GitOperations.run_git(["checkout", "local_commit"], cwd=repo)
            return "local_commit"

        # Guard empty strings to avoid malformed refs like refs/heads/
        start_ref: str | None = base_branch if base_branch else None
        if start_ref:
            if not GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{start_ref}"], cwd=repo):
                start_ref = current_branch if current_branch else None
        else:
            start_ref = current_branch if current_branch else None

        if start_ref and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{start_ref}"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", "local_commit", start_ref], cwd=repo)
            return "local_commit"

        if base_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{base_branch}"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", "local_commit", f"origin/{base_branch}"], cwd=repo)
            return "local_commit"

        # Try origin/HEAD as additional fallback before creating from HEAD
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/remotes/origin/HEAD"], cwd=repo):
            try:
                remote_head = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo).strip()
                if remote_head and remote_head != "HEAD" and GitOperations.git_ok(
                    ["show-ref", "--verify", "--quiet", f"refs/remotes/{remote_head}"], cwd=repo
                ):
                    GitOperations.run_git(["checkout", "-b", "local_commit", remote_head], cwd=repo)
                    return "local_commit"
            except GitManagerError:
                pass

        if current_branch and GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/heads/{current_branch}"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", "local_commit", current_branch], cwd=repo)
            return "local_commit"

        if GitOperations.git_ok(["rev-parse", "--verify", "--quiet", "HEAD"], cwd=repo):
            GitOperations.run_git(["checkout", "-b", "local_commit"], cwd=repo)
            return "local_commit"

        raise GitManagerError("Cannot create local_commit – no valid start point (base_branch empty and no local/remote branch)")

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
