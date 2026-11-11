"""What every ranking source shares: the run status rule, the failure vocabulary, the snapshot health
check and the ``run_status.json`` a crawl leaves behind.

QS wrote a ``run_status.json`` per universe from the start. THE and ARWU did not: a failed crawl left
last week's snapshot on disk with nothing next to it saying so. A source in this package crawls through
``RankingSource.run``, which writes the same status file whether the crawl worked or not.

This module imports no crawler. Exceptions are classified by class name, so it stays importable where
``crawlernest-jobs`` is not on ``sys.path``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_EMPTY = "empty"
STATUS_FAILED = "failed"

STATUS_FILE_NAME = "run_status.json"
STATUS_DIR_NAME = "source_runs"

# The classifications a run_status may carry. QS sets the first group itself (run_pipeline.py); the
# second group is what THE and ARWU raise as exceptions.
NETWORK_ERROR = "network_error"
EDITION_MISMATCH = "edition_mismatch"
TRUNCATED_TABLE = "truncated_table"
SNAPSHOT_REGRESSION = "snapshot_regression"
HEALTH_CHECK_FAILED = "health_check_failed"
INGEST_FAILED = "ingest_failed"
CRAWL_FAILED = "crawl_failed"
# Raised by the crawlers with an explicit failure_class (transport.SourceBlockedError and the
# ranking_edition subclasses of EditionMismatchError); listed here so the vocabulary is in one place.
BLOCKED = "blocked"
LAYOUT_CHANGED = "layout_changed"
EMPTY_TABLE = "empty_table"
HTTP_ERROR = "http_error"

#: Every source's own failure codes, grouped into the families a report compares across sources. QS kept its
#: vocabulary (the fallback logic reads "upstream_blocked"); THE and ARWU use the family names directly. A code not
#: here reports as "other", never as a guess at a family.
FAILURE_FAMILIES = {
    NETWORK_ERROR: NETWORK_ERROR,
    BLOCKED: BLOCKED,
    "upstream_blocked": BLOCKED,
    "resolve_blocked": BLOCKED,
    "upstream_maintenance": "source_unavailable",
    "source_unavailable": "source_unavailable",
    HTTP_ERROR: HTTP_ERROR,
    "fetch_failed": HTTP_ERROR,
    LAYOUT_CHANGED: LAYOUT_CHANGED,
    "resolve_not_found": LAYOUT_CHANGED,
    "normalize_failed": LAYOUT_CHANGED,
    EDITION_MISMATCH: EDITION_MISMATCH,
    EMPTY_TABLE: EMPTY_TABLE,
    TRUNCATED_TABLE: TRUNCATED_TABLE,
    SNAPSHOT_REGRESSION: SNAPSHOT_REGRESSION,
    HEALTH_CHECK_FAILED: HEALTH_CHECK_FAILED,
    INGEST_FAILED: INGEST_FAILED,
    CRAWL_FAILED: CRAWL_FAILED,
}


def failure_family(classification: Any) -> str:
    """The cross-source family of a failure code: "" for none, "other" for a code no family claims."""
    code = str(classification or "").strip()
    if not code:
        return ""
    return FAILURE_FAMILIES.get(code, "other")


class SourceFailure(RuntimeError):
    """A run that ended with a classified failure, raised with the source's own code as ``failure_class``.

    QS's universe pipeline reports its failure in crawl_meta instead of raising. Its scheduled-refresh runner
    raises this, so the refresh records "upstream_blocked" rather than "RuntimeError".
    """

    def __init__(self, source: str, classification: str, message: str = ""):
        super().__init__(f"{source}: {classification}{': ' + message if message else ''}")
        self.source = source
        self.failure_class = classification
        self.family = failure_family(classification)


_CLASSIFICATION_BY_EXCEPTION_NAME = {
    "NetworkError": NETWORK_ERROR,
    "EditionMismatchError": EDITION_MISMATCH,
    "TruncatedTableError": TRUNCATED_TABLE,
    "SnapshotRegressionError": SNAPSHOT_REGRESSION,
}


def run_status_for(*, failure_classification: str, standardized_count: int, run_backing: str = "live") -> str:
    """The one rule for a run's status: failed or empty with no rows, degraded when rows came with a
    failure or from anything but a live fetch, otherwise ok."""
    classification = str(failure_classification or "").strip()
    backing = str(run_backing or "").strip()
    if standardized_count <= 0:
        return STATUS_FAILED if classification else STATUS_EMPTY
    if classification or backing not in ("", "live"):
        return STATUS_DEGRADED
    return STATUS_OK


def classify_failure(exc: BaseException) -> str:
    """The failure classification for an exception a crawl raised.

    An exception that names its own ``failure_class`` (``transport.NetworkError``) wins. The crawlers'
    typed errors map by class name, subclasses included. Anything else is ``crawl_failed``: unknown is
    reported as unknown, never guessed into a network failure, because only network failures are rerun.
    """
    explicit = str(getattr(exc, "failure_class", "") or "").strip()
    if explicit:
        return explicit
    for klass in type(exc).__mro__:
        classification = _CLASSIFICATION_BY_EXCEPTION_NAME.get(klass.__name__)
        if classification:
            return classification
    return CRAWL_FAILED


def check_snapshot_rows(rows: Any, *, ranking_year: int) -> list[str]:
    """Problems in a crawl snapshot's rows; an empty list is healthy.

    These are checks on the file as a whole. A row with no rank is not a problem (THE lists unranked
    "reporter" institutions); a snapshot where no row has a rank is.
    """
    if not isinstance(rows, list) or not rows:
        return ["snapshot has no rows"]
    problems: list[str] = []
    not_objects = sum(1 for row in rows if not isinstance(row, dict))
    if not_objects:
        problems.append(f"{not_objects} row(s) are not objects")
    records = [row for row in rows if isinstance(row, dict)]
    if not records:
        return problems

    blank_names = sum(1 for row in records if not str(row.get("name") or "").strip())
    if blank_names:
        problems.append(f"{blank_names} row(s) have no name")

    ids = [str(row.get("id") or "").strip() for row in records]
    missing_ids = sum(1 for value in ids if not value)
    if missing_ids:
        problems.append(f"{missing_ids} row(s) have no id")
    present_ids = [value for value in ids if value]
    duplicate_ids = len(present_ids) - len(set(present_ids))
    if duplicate_ids:
        problems.append(f"{duplicate_ids} row(s) repeat an id another row already has")

    if not any(row.get("rank") not in (None, "") for row in records):
        problems.append("no row has a rank")

    other_years = sorted({str(row.get("year")) for row in records if _as_int(row.get("year")) != int(ranking_year)})
    if other_years:
        problems.append(f"rows carry year(s) {', '.join(other_years[:5])}, not {int(ranking_year)}")
    return problems


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def status_path_for(status_dir: Path, *, source: str, ranking_year: int) -> Path:
    return Path(status_dir) / str(source).upper() / str(int(ranking_year)) / STATUS_FILE_NAME


def read_run_status(path: Path) -> Optional[dict[str, Any]]:
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_run_status(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _last_success(previous: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """What a failed run keeps from the status it overwrites, so the file still says which run the
    snapshot on disk came from."""
    if not previous:
        return None
    if previous.get("status") in (STATUS_OK, STATUS_DEGRADED) and previous.get("failure_classification") != INGEST_FAILED:
        return {
            key: previous.get(key)
            for key in ("run_id", "status", "finished_at", "standardized_count", "snapshot_file", "crawl_meta")
            if key in previous
        }
    kept = previous.get("last_success")
    return kept if isinstance(kept, dict) else None


@dataclass
class SourceRun:
    """One crawl of one edition, and the status file that describes it."""

    source: str
    ranking_year: int
    status_path: Path
    record: dict[str, Any] = field(default_factory=dict)
    snapshot_path: Optional[Path] = None

    @property
    def status(self) -> str:
        return str(self.record.get("status") or "")

    def record_ingest(self, *, matched_count: int, unresolved_count: int, aggregated_rows: int) -> None:
        self.record.update(
            matched_count=int(matched_count),
            unresolved_count=int(unresolved_count),
            aggregated_rows=int(aggregated_rows),
            ingested=True,
        )
        _write_run_status(self.status_path, self.record)

    def record_ingest_failure(self, exc: BaseException) -> None:
        """The snapshot is good and the warehouse did not take it. QS reports this as failed too."""
        self.record.update(
            status=STATUS_FAILED,
            failure_classification=INGEST_FAILED,
            failure_family=failure_family(INGEST_FAILED),
            message=str(exc),
            ingested=False,
        )
        _write_run_status(self.status_path, self.record)

    def summary(self) -> dict[str, Any]:
        """The part of the status a caller's own summary repeats."""
        return {
            "run_status": self.status,
            "failure_classification": str(self.record.get("failure_classification") or ""),
            "health_problems": list((self.record.get("health") or {}).get("problems") or []),
            "run_status_file": str(self.status_path),
        }


class RankingSource:
    """A ranking source whose crawl writes one snapshot file per edition.

    A subclass names itself and implements ``crawl``. ``run`` adds the status file and the health check;
    it never swallows the crawl's exception, so a caller that reruns network failures still sees them.
    """

    name: str = ""
    ranking_type: str = "world"

    def crawl(self, *, year: int, output_dir: Path) -> Path:
        raise NotImplementedError

    def run(
        self,
        *,
        year: int,
        output_dir: Path,
        status_dir: Optional[Path] = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> SourceRun:
        output_dir = Path(output_dir)
        # Inside the directory the caller chose. A subdirectory, so nothing that globs the snapshots
        # (`<source>_rankings_*.json`) picks a status file up as one.
        status_root = Path(status_dir) if status_dir is not None else output_dir / STATUS_DIR_NAME
        status_path = status_path_for(status_root, source=self.name, ranking_year=year)
        previous = read_run_status(status_path)
        started = now()
        run = SourceRun(source=self.name, ranking_year=int(year), status_path=status_path)
        base = {
            "source": self.name,
            "ranking_type": self.ranking_type,
            "ranking_year": int(year),
            "run_id": f"{self.name.lower()}-{self.ranking_type}-{int(year)}-{_stamp(started)}",
            "started_at": _stamp(started),
        }

        try:
            snapshot_path = Path(self.crawl(year=int(year), output_dir=output_dir))
        except Exception as exc:
            classification = classify_failure(exc)
            run.record = {
                **base,
                "status": run_status_for(failure_classification=classification, standardized_count=0),
                "failure_classification": classification,
                "failure_family": failure_family(classification),
                "message": str(exc),
                "error_type": type(exc).__name__,
                "finished_at": _stamp(now()),
                "crawl_meta": {"failure_classification": classification, "failure_message": str(exc)},
                "normalized_count": 0,
                "standardized_count": 0,
                "ingested": False,
            }
            last_success = _last_success(previous)
            if last_success:
                run.record["last_success"] = last_success
            _write_run_status(status_path, run.record)
            raise

        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        rows = rows if isinstance(rows, list) else []
        metadata = payload.get("metadata") if isinstance(payload, dict) else None
        metadata = metadata if isinstance(metadata, dict) else {}
        problems = check_snapshot_rows(rows, ranking_year=int(year))
        classification = HEALTH_CHECK_FAILED if problems else ""
        valid_ranks = sum(1 for row in rows if isinstance(row, dict) and row.get("rank") not in (None, ""))

        run.snapshot_path = snapshot_path
        run.record = {
            **base,
            "status": run_status_for(failure_classification=classification, standardized_count=len(rows)),
            "failure_classification": classification,
            "failure_family": failure_family(classification),
            "message": "; ".join(problems),
            "finished_at": _stamp(now()),
            # `edition` sits where ranking_edition.snapshot_edition_ok reads it for QS.
            "crawl_meta": {**metadata, "run_backing": "live", "failure_classification": classification},
            "normalized_count": len(rows),
            "standardized_count": len(rows),
            "valid_rank_count": valid_ranks,
            "health": {"ok": not problems, "problems": problems},
            "snapshot_file": snapshot_path.name,
            "ingested": False,
        }
        _write_run_status(status_path, run.record)
        return run
