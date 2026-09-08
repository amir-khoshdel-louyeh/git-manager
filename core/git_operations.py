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


# Commands that require internet connectivity
_NETWORK_GIT_COMMANDS = {"fetch", "push", "pull", "clone", "ls-remote"}


def _requires_internet(args: Sequence[str]) -> bool:
    return bool(args) and args[0] in _NETWORK_GIT_COMMANDS


def _check_internet_before_network_command(args: Sequence[str]) -> None:
    # Proactive socket check removed per user request - only check git error after command fails
    return


def _maybe_translate_network_error(stderr: str) -> str:
    """If stderr looks like a network failure, prepend message."""
    from utils.network import NO_INTERNET_MSG, is_network_error_message

    if is_network_error_message(stderr):
        return f"{NO_INTERNET_MSG} — {stderr}"
    return stderr


class GitOperations:
    """Thin wrappers around git invocations."""

    @staticmethod
    def run_git(args: Sequence[str], *, cwd: Path) -> str:
        """Run a git command and return stdout; raise on failure."""
        _check_internet_before_network_command(args)
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            stderr = _maybe_translate_network_error(stderr)
            quoted = " ".join(shlex.quote(a) for a in args)
            raise GitManagerError(f"git {quoted} failed in {cwd}: {stderr}")
        return result.stdout

    @staticmethod
    def run_git_env(args: Sequence[str], *, cwd: Path, extra_env: dict[str, str]) -> str:
        """Run git with additional environment variables."""
        _check_internet_before_network_command(args)
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
