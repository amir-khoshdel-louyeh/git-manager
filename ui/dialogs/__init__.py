"""Dialog package for Git Manager."""

from ui.dialogs.commit_dialog import CommitDialog
from ui.dialogs.manage_commits_dialog import ManageCommitsDialog
from ui.dialogs.numeric_keypad import NumericKeypadDialog
from ui.dialogs.preview_mode import PreviewModeDialog
from ui.dialogs.reset_dialog import ResetDialog
from ui.dialogs.settings_dialog import SettingsDialog

__all__ = [
    "CommitDialog",
    "ManageCommitsDialog",
    "NumericKeypadDialog",
    "PreviewModeDialog",
    "ResetDialog",
    "SettingsDialog",
]
