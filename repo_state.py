#!/usr/bin/env python3
"""Shared repository state model."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoState:
    path: Path
    name: str
    base_branch: str
    current_branch: str
    local_exists: bool
    commit_count: int
