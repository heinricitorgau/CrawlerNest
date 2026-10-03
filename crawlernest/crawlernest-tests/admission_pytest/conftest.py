"""Make the crawler packages importable for these pytest-style tests.

They import ``crawlernest_admission_crawler`` directly, before anything from ``crawlernest``, so the shim in
``crawlernest/__init__.py`` has not run yet. They used to be found because the repository root was the working directory.
"""
import sys
from pathlib import Path

PACKAGES_DIR = Path(__file__).resolve().parents[2] / "packages"
if str(PACKAGES_DIR) not in sys.path:
    sys.path.append(str(PACKAGES_DIR))
