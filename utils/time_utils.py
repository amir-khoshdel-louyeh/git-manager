"""Time formatting helpers."""

from __future__ import annotations

import re
from datetime import datetime, timezone


def now_iso() -> str:
    """Return current time in ISO 8601 format with timezone."""
    # Use timezone-aware UTC so %z is populated (+0000), valid for GIT_AUTHOR_DATE.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def now_display() -> str:
    """Return current time in human-readable format."""
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def now_date_str() -> str:
    """Return current date as YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def now_time_str() -> str:
    """Return current time as HH:MM:SS."""
    return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Custom datetime helpers
# ---------------------------------------------------------------------------
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def build_custom_iso(date_str: str, time_str: str) -> str:
    """Build ISO datetime string from date and time components.

    Validates ``YYYY-MM-DD`` and ``HH:MM:SS`` formats and returns
    ``YYYY-MM-DDTHH:MM:SS`` which is compatible with ``now_iso()`` output
    (without trailing timezone).
    """
    date_str = date_str.strip()
    time_str = time_str.strip()
    if not _DATE_RE.match(date_str):
        raise ValueError(f"Invalid date '{date_str}'. Expected YYYY-MM-DD")
    if not _TIME_RE.match(time_str):
        raise ValueError(f"Invalid time '{time_str}'. Expected HH:MM:SS")
    # Validate actual calendar values
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_iso_to_dt(iso_str: str) -> datetime:
    """Parse ISO-like strings to datetime for comparison.

    Supports:
    - ``YYYY-MM-DDTHH:MM:SS`` (from ``now_iso`` / custom)
    - ``YYYY-MM-DDTHH:MM:SS+00:00`` (from ``%aI``)
    - ``YYYY-MM-DD HH:MM:SS +0000`` (from ``%ad`` iso)
    """
    iso_str = iso_str.strip()
    # Try ISO with T separator and optional timezone
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            # Handle colon in tz like +00:00 → +0000 for strptime
            cleaned = iso_str
            if iso_str and iso_str[-3] == ":" and iso_str[-6] in "+-":
                cleaned = iso_str[:-3] + iso_str[-2:]
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    # Fallback: Python's fromisoformat (handles +00:00)
    try:
        return datetime.fromisoformat(iso_str)
    except ValueError as exc:
        raise ValueError(f"Cannot parse datetime '{iso_str}'") from exc


def is_after_last_commit(custom_iso: str, last_commit_iso: str | None) -> bool:
    """Return True if custom datetime is strictly after last commit datetime.

    If ``last_commit_iso`` is None/empty (no prior commits), returns True.
    """
    if not last_commit_iso:
        return True
    try:
        custom_dt = parse_iso_to_dt(custom_iso)
        last_dt = parse_iso_to_dt(last_commit_iso)
        # Normalize: compare naive datetimes (strip timezone) to avoid
        # offset-naive vs offset-aware comparison errors. Git log may return
        # aware (+00:00) while custom is naive.
        if custom_dt.tzinfo is not None:
            custom_dt = custom_dt.replace(tzinfo=None)
        if last_dt.tzinfo is not None:
            last_dt = last_dt.replace(tzinfo=None)
        return custom_dt > last_dt
    except ValueError:
        # If parsing fails, be conservative and allow; caller should have validated
        return True


def is_future(iso_str: str) -> bool:
    """Return True if iso datetime is strictly in the future relative to now."""
    if not iso_str:
        return False
    try:
        dt = parse_iso_to_dt(iso_str)
        now = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
        # Normalize both to naive for comparison
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        if now.tzinfo is not None:
            now = now.replace(tzinfo=None)
        return dt > now
    except ValueError:
        return False
