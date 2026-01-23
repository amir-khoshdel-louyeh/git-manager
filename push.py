#!/usr/bin/env python3
"""Python equivalent of push.sh with interactive multi-repo management."""
from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


class GitManagerError(Exception):
    """Raised for recoverable git-manager errors."""


def run_git(args: Sequence[str], *, cwd: Path) -> str:
    """Run a git command and return stdout as text."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise GitManagerError(f"git {' '.join(args)} failed in {cwd}: {stderr}")
    return result.stdout


def git_ok(args: Sequence[str], *, cwd: Path) -> bool:
    """Return True if git command exits with 0, suppressing output."""
    result = subprocess.run(["git", *args], cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


@dataclass
class RepoState:
    path: Path
    name: str
    base_branch: str
    current_branch: str
    local_commit_exists: bool
    pending_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage multiple git repositories under a base directory.")
    parser.add_argument(
        "base_dir",
        nargs="?",
        default=os.environ.get("BASE_DIR"),
        help="Base directory containing git repositories (default: $BASE_DIR or /home/amir/GitHub)",
    )
    return parser.parse_args()


def resolve_base_dir(arg_base: str | None) -> Path:
    base_dir = Path(arg_base or "/home/amir/GitHub").expanduser().resolve()
    if not base_dir.is_dir():
        raise GitManagerError(f"Base directory '{base_dir}' not found")
    return base_dir


def main() -> None:
    args = parse_args()
    base_dir = resolve_base_dir(args.base_dir)
    print(f"Scanning repositories in: {base_dir}")
    # TODO: implement scanning and interactive loop


if __name__ == "__main__":
    try:
        main()
    except GitManagerError as exc:
        print(f"Error: {exc}")
