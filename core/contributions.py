"""Contribution-graph data (GitHub-style) computed from local git history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


# GitHub contribution colors (light / dark).
COLORS_LIGHT = ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39")
COLORS_DARK = ("#161b22", "#0e4429", "#006d32", "#26a641", "#39d353")

#: Weeks shown (GitHub shows ~53 columns, Sunday on top).
WEEKS = 53


@dataclass(frozen=True)
class ContributionCell:
    """One day cell in the graph (None count means out of range/blank)."""

    day: date
    in_range: bool
    count: int = 0
    level: int = 0


def level_for(count: int, max_count: int) -> int:
    """Map a commit count to GitHub-style intensity 0..4 (max-relative)."""
    if count <= 0 or max_count <= 0:
        return 0
    ratio = count / max_count
    if ratio < 0.25:
        return 1
    if ratio < 0.50:
        return 2
    if ratio < 0.75:
        return 3
    return 4


def grid_bounds(today: date | None = None) -> tuple[date, date]:
    """Return (first_sunday, today) covering WEEKS week columns."""
    today = today or date.today()
    # Sunday of the current week (GitHub rows run Sun..Sat).
    last_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    first_sunday = last_sunday - timedelta(days=7 * (WEEKS - 1))
    return first_sunday, today


def build_grid(
    counts: dict[str, int],
    today: date | None = None,
) -> list[list[ContributionCell]]:
    """Build week columns (oldest first) of day cells from {YYYY-MM-DD: n}.

    Each column has 7 cells (Sunday..Saturday). Cells outside
    [first_sunday, today] are marked blank (in_range=False).
    """
    today = today or date.today()
    first_sunday, end = grid_bounds(today)
    max_count = max(counts.values(), default=0)
    columns: list[list[ContributionCell]] = []
    for week in range(WEEKS):
        column: list[ContributionCell] = []
        for weekday in range(7):
            day = first_sunday + timedelta(days=week * 7 + weekday)
            in_range = first_sunday <= day <= end
            count = counts.get(day.isoformat(), 0) if in_range else 0
            column.append(
                ContributionCell(
                    day=day,
                    in_range=in_range,
                    count=count,
                    level=level_for(count, max_count) if in_range else 0,
                )
            )
        columns.append(column)
    return columns


def _contrib_ref(repo: Path) -> str | None:
    """Pick the ref to count, GitHub-style: remote default branch first.

    GitHub attributes contributions to what is actually pushed on the default
    branch — never local work branches, backups, or rewritten copies. Fall
    back to the local base branch when the repo has no remote yet.
    """
    from core.git_operations import GitOperations

    candidates: list[str] = []
    try:
        if GitOperations.git_ok(["show-ref", "--verify", "--quiet", "refs/remotes/origin/HEAD"], cwd=repo):
            head = GitOperations.run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], cwd=repo).strip()
            if head and head != "HEAD" and head.startswith("origin/"):
                candidates.append(head)
    except Exception:
        pass
    candidates += ["origin/main", "origin/master", "main", "master"]
    for ref in candidates:
        try:
            if GitOperations.git_ok(["show-ref", "--verify", "--quiet", f"refs/remotes/{ref}" if ref.startswith("origin/") else f"refs/heads/{ref}"], cwd=repo):
                return ref
        except Exception:
            continue
    return None


def collect_counts(
    repo_paths: list[Path],
    author_email: str | None = None,
    days: int = 371,
) -> dict[str, int]:
    """Count commits per day (author date) across repos, deduped by SHA.

    Counts what GitHub would show: pushed history on each repo's default
    branch (merge commits excluded, like GitHub). Local work branches,
    backup branches and rewritten copies never count. When ``author_email``
    is None/empty, all authors count.
    """
    since = (date.today() - timedelta(days=days)).isoformat()
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for repo in repo_paths:
        if not (Path(repo) / ".git").is_dir():
            continue
        ref = _contrib_ref(repo)
        if ref is None:
            continue
        cmd = [
            "git",
            "log",
            ref,
            "--no-merges",
            "--pretty=format:%H %ad",
            "--date=short",
            f"--since={since}",
        ]
        if author_email:
            cmd.append(f"--author={author_email}")
        try:
            import subprocess

            result = subprocess.run(
                cmd,
                cwd=str(repo),
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            sha, day_str = parts
            if sha in seen:
                continue
            seen.add(sha)
            counts[day_str] = counts.get(day_str, 0) + 1
    return counts
