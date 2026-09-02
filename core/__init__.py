"""Core domain package: git operations, repo scanning, settings."""

from core.branch_manager import BranchManager
from core.git_config import GitConfig
from core.git_operations import GitManagerError, GitOperations
from core.repo_scanner import RepoScanner
from core.repo_state import RepoState
from core.settings_db import SettingsDB
from core.working_tree_manager import WorkingTreeManager

__all__ = [
    "BranchManager",
    "GitConfig",
    "GitManagerError",
    "GitOperations",
    "RepoScanner",
    "RepoState",
    "SettingsDB",
    "WorkingTreeManager",
]
