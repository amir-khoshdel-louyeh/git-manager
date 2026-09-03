#!/usr/bin/env python3
"""Entry point for Git Manager.

This module is the canonical entry point for the application.
It delegates to :mod:`ui.app` which contains the GUI bootstrap
(``main()`` → ``GitManagerGUI``).

Run with:
    python main.py
    python -m main
    python push_gui.py  # legacy, still works via shim
"""
from __future__ import annotations

from ui.app import main


if __name__ == "__main__":
    main()
