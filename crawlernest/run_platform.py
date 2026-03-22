#!/usr/bin/env python3
"""
CrawlerNest Platform Launcher

This script sets up the environment to run the modularized components
without requiring complex PYTHONPATH configuration.
"""

import sys
import os
import time
from pathlib import Path

# Identify project root
ROOT = Path(__file__).resolve().parent

# List of modules to add to sys.path
MODULES = [
    "crawlernest-core",
    "crawlernest-extractors",
    "crawlernest-jobs",
    "crawlernest-db-writer",
    "crawlernest-cli",
    "crawlernest-analytics",
]

# Add all modules to sys.path
for mod in MODULES:
    mod_path = ROOT / mod
    if mod_path.is_dir() and str(mod_path) not in sys.path:
        sys.path.insert(0, str(mod_path))

# Run the main crawler logic
if __name__ == "__main__":
    start_time = time.time()
    try:
        from clawer_main import run
        sys.exit(run())
    except ImportError as e:
        print(f"Error: Could not load CrawlerNest modules. {e}")
        print(f"Current sys.path: {sys.path}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
    finally:
        elapsed = time.time() - start_time
        print(f"\n--- Execution Finished in {elapsed:.2f} seconds ---")
