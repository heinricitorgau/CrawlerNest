"""Refuse to overwrite a committed ranking snapshot with a degraded one.

Every crawler writes its snapshot over the previous one. Nothing compared the
two, so a crawl that read less than before replaced good data without a sound:

- 2026-11-03, ARWU: the payload stopped parsing, the crawl fell back to the
  rendered table, and 30 rows replaced the 1,000-row edition.
- 2026-11-08, QS global: one row came back with an empty country and the crawl
  still reported live_ok.

``check_snapshot_regression`` runs before the write and raises when the new
rows are a clear step down from what is on disk. It only compares against the
file being replaced, so a first crawl, or one into a fresh output directory,
always passes. An intentional shrink (a corrected edition, a source dropping
institutions) goes through with ``allow=True`` or CRAWLERNEST_ALLOW_SNAPSHOT_REGRESSION=1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Sequence

ALLOW_ENV = "CRAWLERNEST_ALLOW_SNAPSHOT_REGRESSION"
DEFAULT_FIELDS: tuple[str, ...] = ("name", "rank", "country")
# A whole edition does not lose 5% of its rows between two crawls of the same
# year. Small moves (a merged institution, a tie resolved) stay under it.
DEFAULT_MAX_ROW_DROP = 0.05
_MAX_LISTED = 5


class SnapshotRegressionError(RuntimeError):
    """The new rows are fewer, or emptier, than the snapshot they would replace."""


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _env_allows() -> bool:
    return os.environ.get(ALLOW_ENV, "").strip().lower() in {"1", "true", "yes"}


def _load_rows(path: Path) -> list[Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return None


def _by_identity(rows: Iterable[Any], id_field: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and not _is_blank(row.get(id_field)):
            out[str(row[id_field])] = row
    return out


def find_regressions(
    old_rows: Sequence[Any],
    new_rows: Sequence[Any],
    *,
    id_field: str = "id",
    fields: Sequence[str] = DEFAULT_FIELDS,
    max_row_drop: float = DEFAULT_MAX_ROW_DROP,
) -> list[str]:
    """Return one line per problem; empty when the new rows are no worse."""
    problems: list[str] = []

    old_n, new_n = len(old_rows), len(new_rows)
    if old_n and new_n < old_n * (1 - max_row_drop):
        problems.append(
            f"row count fell from {old_n} to {new_n} "
            f"({(old_n - new_n) / old_n:.0%} drop, limit {max_row_drop:.0%})"
        )

    old_by_id = _by_identity(old_rows, id_field)
    new_by_id = _by_identity(new_rows, id_field)
    lost: list[str] = []
    for key, new in new_by_id.items():
        old = old_by_id.get(key)
        if old is None:
            continue
        for field in fields:
            if not _is_blank(old.get(field)) and _is_blank(new.get(field)):
                label = old.get("name") or old.get("university_name") or key
                lost.append(f"{label}: {field} {old.get(field)!r} -> {new.get(field)!r}")
    if lost:
        shown = "; ".join(lost[:_MAX_LISTED])
        more = f" (+{len(lost) - _MAX_LISTED} more)" if len(lost) > _MAX_LISTED else ""
        problems.append(f"{len(lost)} field(s) that had a value are now empty: {shown}{more}")

    return problems


def check_snapshot_regression(
    path: Path,
    new_rows: Sequence[Any],
    *,
    label: str,
    id_field: str = "id",
    fields: Sequence[str] = DEFAULT_FIELDS,
    max_row_drop: float = DEFAULT_MAX_ROW_DROP,
    allow: bool = False,
) -> None:
    """Raise SnapshotRegressionError if writing *new_rows* to *path* loses data."""
    if not path.exists():
        return
    old_rows = _load_rows(path)
    if old_rows is None:
        return
    problems = find_regressions(
        old_rows, new_rows, id_field=id_field, fields=fields, max_row_drop=max_row_drop
    )
    if not problems:
        return
    if allow or _env_allows():
        for problem in problems:
            print(f"[guard] {label}: overriding regression: {problem}")
        return
    raise SnapshotRegressionError(
        f"{label}: not overwriting {path.name}: " + " | ".join(problems)
        + f". If this is intended, rerun with {ALLOW_ENV}=1."
    )
