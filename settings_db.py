"""Settings database for persisting user preferences."""
import sqlite3
from pathlib import Path
from typing import Optional


class SettingsDB:
    """Manage application settings using SQLite."""
    
    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize settings database.
        
        Args:
            db_path: Path to database file. Defaults to ~/.git-manager/settings.db
        """
        if db_path is None:
            db_path = Path.home() / ".git-manager" / "settings.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
    
    def set(self, key: str, value: str) -> None:
        """Set a setting value.
        
        Args:
            key: Setting key
            value: Setting value
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (key, value))
            conn.commit()
    
    def get_base_directory(self) -> Optional[str]:
        """Get the saved base directory."""
        return self.get("base_directory")
    
    def set_base_directory(self, path: str) -> None:
        """Save the base directory."""
        self.set("base_directory", path)
