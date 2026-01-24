"""Git configuration management."""
from __future__ import annotations

from pathlib import Path

from git_operations import GitOperations, GitManagerError


class GitConfig:
    """Handles git configuration operations."""
    
    @staticmethod
    def ensure_identity(repo: Path) -> tuple[str, str]:
        """Ensure git user is configured and return (name, email)."""
        name = GitOperations.run_git(["config", "user.name"], cwd=repo).strip()
        email = GitOperations.run_git(["config", "user.email"], cwd=repo).strip()
        
        if not name or not email:
            raise GitManagerError("Git user not configured. Set user.name and user.email first.")
        
        return name, email
