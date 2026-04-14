from __future__ import annotations

import site
from pathlib import Path


def get_psycopg2():
    try:
        import psycopg2  # type: ignore

        return psycopg2
    except ImportError:
        _maybe_add_repo_venv_site_packages()
        import psycopg2  # type: ignore

        return psycopg2


def _maybe_add_repo_venv_site_packages() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    candidates = sorted((repo_root / ".venv" / "lib").glob("python*/site-packages"))
    for candidate in candidates:
        if candidate.is_dir():
            site.addsitedir(str(candidate))
