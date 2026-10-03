"""The crawlernest package.

The crawler packages -- ``crawlernest_ranking_crawler``, ``crawlernest_admission_crawler``, ``crawlernest_crawler_core`` and
the archived ``legacy`` -- live in ``crawlernest/packages/`` and are imported by their own top-level names, as they always were.
Importing ``crawlernest`` puts that directory on ``sys.path`` (last, so it can shadow nothing), which is enough for every entry
point that imports ``crawlernest`` first. An entry point that imports one of them before anything from ``crawlernest`` must add
``PACKAGES_DIR`` itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGES_DIR = Path(__file__).resolve().parent / "packages"

if PACKAGES_DIR.is_dir() and str(PACKAGES_DIR) not in sys.path:
    sys.path.append(str(PACKAGES_DIR))
