#!/usr/bin/env python3
"""Git command helpers for GUI and CLI tools."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Sequence


class GitManagerError(Exception):
    """Raised for recoverable git-manager errors."""


# Default timeout to avoid hanging forever on slow network commands.
GIT_TIMEOUT = 60


def _maybe_translate_network_error(stderr: str) -> str:
    """If stderr looks like a network failure, prepend message."""
    from utils.network import NO_INTERNET_MSG, is_network_error_message

    if is_network_error_message(stderr):
        return f"{NO_INTERNET_MSG} — {stderr}"
    return stderr


class GitOperations:
    """Thin wrappers around git invocations."""

    @staticmethod
    def run_git(args: Sequence[str], *, cwd: Path, timeout: int = GIT_TIMEOUT) -> str:
        """Run a git command and return stdout; raise on failure."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                check=False,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            quoted = " ".join(shlex.quote(a) for a in args)
            raise GitManagerError(f"git {quoted} timed out after {timeout}s in {cwd}") from exc
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            stderr = _maybe_translate_network_error(stderr)
            quoted = " ".join(shlex.quote(a) for a in args)
            raise GitManagerError(f"git {quoted} failed in {cwd}: {stderr}")
        return result.stdout

    @staticmethod
    def run_git_env(args: Sequence[str], *, cwd: Path, extra_env: dict[str, str], timeout: int = GIT_TIMEOUT) -> str:
        """Run git with additional environment variables."""
        env = os.environ.copy()
        env.update(extra_env)
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                check=False,
                text=True,
                capture_output=True,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            quoted = " ".join(shlex.quote(a) for a in args)
            raise GitManagerError(f"git {quoted} timed out after {timeout}s in {cwd}") from exc
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            stderr = _maybe_translate_network_error(stderr)
            quoted = " ".join(shlex.quote(a) for a in args)
            raise GitManagerError(f"git {quoted} failed in {cwd}: {stderr}")
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
