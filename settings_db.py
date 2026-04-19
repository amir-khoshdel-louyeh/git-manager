"""Settings file for persisting user preferences."""
import json
from pathlib import Path
from typing import Any, Dict, Optional


class SettingsDB:
    """Manage application settings using a JSON file."""

    def __init__(self, file_path: Path | None = None) -> None:
        """Initialize settings storage.

        Args:
            file_path: Path to settings JSON file. Defaults to ~/.git-manager/settings.json
        """
        if file_path is None:
            file_path = Path.home() / ".git-manager" / "settings.json"

        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_settings()

    def _load_settings(self) -> None:
        """Load settings from the JSON file."""
        if self.file_path.exists():
            try:
                with self.file_path.open("r", encoding="utf-8") as handle:
                    self.settings = json.load(handle)
            except (json.JSONDecodeError, OSError):
                self.settings = {}
        else:
            self.settings: Dict[str, Any] = {}
            self._save_settings()

    def _save_settings(self) -> None:
        """Persist settings to the JSON file."""
        with self.file_path.open("w", encoding="utf-8") as handle:
            json.dump(self.settings, handle, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value."""
        value = self.settings.get(key, default)
        return str(value) if value is not None else default

    def set(self, key: str, value: str) -> None:
        """Set a setting value."""
        self.settings[key] = value
        self._save_settings()

    def get_base_directory(self) -> Optional[str]:
        """Get the saved base directory."""
        return self.get("base_directory")

    def set_base_directory(self, path: str) -> None:
        """Save the base directory."""
        self.set("base_directory", path)

    def get_auto_switch_local_commit(self) -> bool:
        """Return whether local_commit should be selected on startup."""
        return self.get("auto_switch_local_commit", default="1") == "1"

    def set_auto_switch_local_commit(self, enabled: bool) -> None:
        """Save auto-switch-on-startup preference."""
        self.set("auto_switch_local_commit", "1" if enabled else "0")

    def get_auto_refresh_enabled(self) -> bool:
        """Return whether auto-refresh is enabled."""
        return self.get("auto_refresh_enabled", default="0") == "1"

    def set_auto_refresh_enabled(self, enabled: bool) -> None:
        """Save the auto-refresh enabled state."""
        self.set("auto_refresh_enabled", "1" if enabled else "0")

    def get_refresh_interval(self) -> int:
        """Return the auto-refresh interval in minutes."""
        value = self.get("refresh_interval", default="5")
        try:
            return max(1, int(value))
        except ValueError:
            return 5

    def set_refresh_interval(self, minutes: int) -> None:
        """Save the auto-refresh interval in minutes."""
        self.set("refresh_interval", str(minutes))

    def get_int(self, key: str, default: int) -> int:
        """Return an integer setting value, or the provided default."""
        value = self.settings.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_theme_mode(self) -> str:
        """Return the saved theme mode."""
        return self.get("theme_mode", default="light")

    def set_theme_mode(self, mode: str) -> None:
        """Save the UI theme mode."""
        self.set("theme_mode", mode)

    def get_output_font_size(self) -> int:
        """Return the saved terminal output font size."""
        return self.get_int("output_font_size", 10)

    def set_output_font_size(self, size: int) -> None:
        """Save the terminal output font size."""
        self.set("output_font_size", str(size))

    def get_table_font_size(self) -> int:
        """Return the saved repo table font size."""
        return self.get_int("table_font_size", 10)

    def set_table_font_size(self, size: int) -> None:
        """Save the repo table font size."""
        self.set("table_font_size", str(size))
