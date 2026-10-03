"""Pipeline support modules for the CrawlerNest runner."""
import sys as _sys
from pathlib import Path as _Path

# The commands import the crawler packages (crawlernest_ranking_crawler and the others) by their own names; they live in
# crawlernest/packages/. This package is also imported as a top-level `pipeline` by scripts that never import `crawlernest`.
_PACKAGES_DIR = _Path(__file__).resolve().parents[1] / "packages"
if _PACKAGES_DIR.is_dir() and str(_PACKAGES_DIR) not in _sys.path:
    _sys.path.append(str(_PACKAGES_DIR))
