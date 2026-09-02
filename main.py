#!/usr/bin/env python3
"""Entry point for Git Manager.

This module is the canonical entry point for the application.
It delegates to :mod:`push_gui` which contains the GUI implementation
(`GitManagerGUI` and ``main()``).

Run with:
    python main.py
    python -m main
    python push_gui.py  # legacy, still works
"""
from __future__ import annotations

from push_gui import main


if __name__ == "__main__":
    main()
