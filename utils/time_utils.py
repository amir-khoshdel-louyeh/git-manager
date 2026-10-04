"""Time formatting helpers."""

from __future__ import annotations

import random
import re
from datetime import datetime, timedelta, timezone


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
        # Custom dates omit an offset and are entered as local time. Attach the
        # local timezone before comparing with Git's timezone-aware timestamp.
        local_tz = datetime.now().astimezone().tzinfo
        if custom_dt.tzinfo is None:
            custom_dt = custom_dt.replace(tzinfo=local_tz)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=local_tz)
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


# ---------------------------------------------------------------------------
# Commit distribution helpers (used by Move Commits)
# ---------------------------------------------------------------------------
_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?$")


def format_git_iso(dt: datetime) -> str:
    """Format a datetime as ``YYYY-MM-DDTHH:MM:SS`` (naive, git-compatible)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_hhmm(value: str) -> tuple[int, int, int]:
    """Parse ``HH:MM`` (or ``HH:MM:SS``) into (hour, minute, second)."""
    m = _HHMM_RE.match(value.strip())
    if not m:
        raise ValueError(f"Invalid time '{value}'. Expected HH:MM (00:00 to 23:59)")
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or "0")


def distribute_in_window(start_iso: str, end_iso: str, n: int) -> list[str]:
    """Return ``n`` random ISO datetimes uniformly spread in [start, end].

    Results are sorted ascending so commit order is preserved, and duplicates
    are avoided whenever the window holds enough distinct seconds. If the
    window is smaller than ``n`` seconds, values may repeat but stay ordered
    (non-decreasing).
    """
    if n <= 0:
        return []
    start_dt = parse_iso_to_dt(start_iso).replace(tzinfo=None)
    end_dt = parse_iso_to_dt(end_iso).replace(tzinfo=None)
    if end_dt < start_dt:
        raise ValueError(f"Invalid window: {start_iso} is after {end_iso}")
    total = int((end_dt - start_dt).total_seconds())
    if total <= 0 or n == 1:
        if n == 1:
            # Single commit: random point inside the window (or the point itself)
            offset = random.randint(0, total) if total > 0 else 0
            return [format_git_iso(start_dt + timedelta(seconds=offset))]
        # Degenerate window with multiple commits: all identical (unavoidable)
        return [format_git_iso(start_dt) for _ in range(n)]
    if total >= n:
        # Distinct seconds, sorted → strictly increasing, order preserved
        offsets = sorted(random.sample(range(total + 1), n))
    else:
        # Window too small for distinct seconds: allow repeats, still sorted
        offsets = sorted(random.randint(0, total) for _ in range(n))
    return [format_git_iso(start_dt + timedelta(seconds=o)) for o in offsets]


def distribute_across_days(
    start_date: str,
    end_date: str,
    work_start: str,
    work_end: str,
    n: int,
    min_per_day: int = 0,
    max_per_day: int | None = None,
    busy_workdays: bool = False,
    workday_weight: float = 3.0,
) -> list[str]:
    """Distribute ``n`` commits across each day in [start_date, end_date].

    Each day gets at least ``min_per_day`` and at most ``max_per_day``
    commits. The remainder above the minimum is split proportionally
    (largest-remainder), giving workdays (Mon–Fri) ``workday_weight`` times
    the share of weekends (Sat–Sun) when ``busy_workdays`` is enabled.
    Within each day commits get random times inside working hours
    (``HH:MM``), sorted ascending. The whole result is chronological.
    """
    if n <= 0:
        return []
    try:
        d0 = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        d1 = datetime.strptime(end_date.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid date range '{start_date}' to '{end_date}': {exc}") from exc
    if d1 < d0:
        raise ValueError(f"Invalid date range: {start_date} is after {end_date}")
    sh, sm, ss = parse_hhmm(work_start)
    eh, em, es = parse_hhmm(work_end)
    if (eh, em, es) <= (sh, sm, ss):
        raise ValueError(
            f"Invalid working hours: start ({work_start}) must be before end ({work_end})"
        )
    lo = max(0, int(min_per_day))
    hi = n if max_per_day is None else max(1, int(max_per_day))
    if lo > hi:
        raise ValueError(
            f"Invalid daily limits: min ({lo}) must not exceed max ({hi})"
        )
    days = [(d0 + timedelta(days=i)) for i in range((d1 - d0).days + 1)]
    count_days = len(days)
    if count_days * hi < n:
        raise ValueError(
            f"Cannot fit {n} commits in {count_days} day(s) with max {hi} per day. "
            f"Raise max commits per day or extend the range."
        )
    if count_days * lo > n:
        # Not enough commits to satisfy the minimum everywhere: relax it.
        lo = n // count_days
    weights = [
        (workday_weight if day.weekday() < 5 else 1.0) if busy_workdays else 1.0
        for day in days
    ]
    counts = [lo] * count_days
    remaining = n - count_days * lo
    # Largest-remainder allocation of the remainder, respecting the cap.
    guard = 0
    while remaining > 0:
        guard += 1
        if guard > count_days + 5:
            raise ValueError("Internal error while distributing commits across days")
        eligible = [i for i in range(count_days) if counts[i] < hi]
        if not eligible:
            raise ValueError(
                f"Cannot fit {n} commits in {count_days} day(s) with max {hi} per day."
            )
        total_w = sum(weights[i] for i in eligible)
        quotas = [(remaining * weights[i] / total_w, i) for i in eligible]
        # Whole part first (clamped to remaining headroom)
        for quota, i in quotas:
            give = min(int(quota), hi - counts[i])
            counts[i] += give
            remaining -= give
        if remaining <= 0:
            break
        # Leftover goes to the largest fractional parts (heavier days first)
        ordered = sorted(
            quotas, key=lambda q: (q[0] - int(q[0]), weights[q[1]], -q[1]), reverse=True
        )
        progressed = False
        for _, i in ordered:
            if remaining <= 0:
                break
            if counts[i] < hi:
                counts[i] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            continue  # eligible set will shrink next iteration
    result: list[str] = []
    for day, count in zip(days, counts):
        if count == 0:
            continue
        day_start = datetime(day.year, day.month, day.day, sh, sm, ss)
        day_end = datetime(day.year, day.month, day.day, eh, em, es)
        result.extend(
            distribute_in_window(format_git_iso(day_start), format_git_iso(day_end), count)
        )
    return result
