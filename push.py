#!/usr/bin/env python3
"""Python equivalent of push.sh with interactive multi-repo management."""
from __future__ import annotations

import argparse
import os
from pathlib import Path


class GitManagerError(Exception):
    """Raised for recoverable git-manager errors."""


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
