"""Time formatting helpers."""

from __future__ import annotations

from datetime import datetime


def now_iso() -> str:
    """Return current time in ISO 8601 format."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S%z")


def now_display() -> str:
    """Return current time in human-readable format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %z")
