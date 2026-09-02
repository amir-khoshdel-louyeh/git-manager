#!/usr/bin/env python3
"""Git command helpers for GUI and CLI tools."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Sequence


class GitManagerError(Exception):
    """Raised for recoverable git-manager errors."""


class GitOperations:
    """Thin wrappers around git invocations."""

    @staticmethod
    def run_git(args: Sequence[str], *, cwd: Path) -> str:
        """Run a git command and return stdout; raise on failure."""
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

    @staticmethod
    def run_git_env(args: Sequence[str], *, cwd: Path, extra_env: dict[str, str]) -> str:
        """Run git with additional environment variables."""
        env = os.environ.copy()
        env.update(extra_env)
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            text=True,
            capture_output=True,
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise GitManagerError(f"git {' '.join(args)} failed in {cwd}: {stderr}")
        return result.stdout

    @staticmethod
    def git_ok(args: Sequence[str], *, cwd: Path) -> bool:
        """Return True when git exits with status 0."""
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
