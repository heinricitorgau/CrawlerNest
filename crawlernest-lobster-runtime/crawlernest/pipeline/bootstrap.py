from __future__ import annotations

import sys
from pathlib import Path


def resolve_repo_paths(entry_file: str) -> tuple[Path, Path]:
    repo_root = Path(entry_file).resolve().parent
    module_root = repo_root if (repo_root / "crawlernest-core").is_dir() else repo_root / "crawlernest"
    return repo_root, module_root


def bootstrap_module_paths(module_root: Path) -> None:
    module_dirs = [
        module_root / "crawlernest-core",
        module_root / "crawlernest-extractors",
        module_root / "crawlernest-jobs",
        module_root / "crawlernest-db-writer",
        module_root / "crawlernest-analytics",
    ]
    for mod_dir in module_dirs:
        if mod_dir.is_dir() and str(mod_dir) not in sys.path:
            sys.path.insert(0, str(mod_dir))
