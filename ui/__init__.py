"""UI package for Git Manager."""

from ui.main_window import DEFAULT_BASE_DIR, GitManagerGUI
from ui.theme import THEMES, apply_theme, get_theme

__all__ = ["GitManagerGUI", "DEFAULT_BASE_DIR", "THEMES", "apply_theme", "get_theme"]
