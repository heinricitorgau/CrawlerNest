#!/usr/bin/env python3
"""Main entry point for the Clawer crawler system.

This module keeps startup logic minimal and routes execution into either:
1. CLI mode (when command-line arguments are provided), or
2. Interactive mode (when launched without arguments).
"""

from __future__ import annotations

import sys
from typing import NoReturn

from ui import fetch_rankings, main


def _run_cli_mode() -> int:
    """Run the command-line entry flow and normalize its return value."""
    result = main()
    return int(result) if result is not None else 0


def _run_interactive_mode() -> int:
    """Run the interactive UI flow."""
    fetch_rankings()
    return 0


def run(argv: list[str] | None = None) -> int:
    """Execute the appropriate startup mode and return an exit code."""
    args = sys.argv if argv is None else argv

    if len(args) > 1:
        return _run_cli_mode()

    return _run_interactive_mode()


def _exit_with_error(message: str, code: int) -> NoReturn:
    """Print a user-facing error message and terminate the process."""
    print(message)
    raise SystemExit(code)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        _exit_with_error("\n\nInterrupted by user", 130)
    except Exception as exc:
        _exit_with_error(f"\nError: {exc}", 1)