"""The one command an external scheduler runs: refresh the released edition, once.

Scheduling lives outside the serving stack on purpose. The Spring Boot API and
the Next.js app are read-only (CLAUDE.md: "no pipeline triggers from the API
layer"); a cron or systemd timer on the host invokes

    python -m crawlernest.run_pipeline scheduled-refresh --pg-password ...

and nothing reachable over HTTP can start it. ``test_no_pipeline_triggers_from_api``
keeps it that way.

Why not ``run_pipeline run``, the command the original plan named:

* Its ``--limit`` defaults to 30, and its QS path rewrites world ranking_record
  from the legacy table, pruning every row the run did not write. A scheduled
  ``run`` would have cut the held QS edition to 30 rows. The shrink guard in
  ``MultiSourceRankingPipeline.ingest_records`` now refuses that, which turns
  the scheduled job into a nightly failure instead.
* The legacy path discards the printed rank ("=17", "601-610"), which per-source
  rank movement is computed from.
* ``run-qs-universes`` and its relatives loop forever by design.

So this runs each source's guarded, one-shot path for one edition:

* QS  -- ``run_qs_universe_ingestion`` (global), which proves the edition from
  its page and records the printed rank;
* THE -- ``run_the_rankings_ingestion``; ARWU -- ``run_arwu_rankings_ingestion``,
  both edition-verified and with ``skip_seed`` so the legacy backfill never runs.

Sources run independently: one failing (a Cloudflare block, a site redesign)
does not stop the others, and the exit code is non-zero if any failed so the
scheduler records it. A lock file stops overlapping runs, and each run writes a
JSON status next to its log.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_SOURCES = ("QS", "THE", "ARWU")


class RefreshAlreadyRunning(RuntimeError):
    pass


@dataclass
class SourceOutcome:
    source: str
    ok: bool
    started_at: str
    finished_at: str
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dataclass_fields__"):
        return _to_jsonable({k: getattr(value, k) for k in value.__dataclass_fields__})
    return str(value)


def run_scheduled_refresh(
    *,
    ranking_year: int,
    sources: Iterable[str],
    runners: dict[str, Callable[[int], Any]],
    lock_path: Path,
    status_dir: Path,
) -> int:
    """Run each source once for ``ranking_year``. Returns 0 only if every source succeeded."""
    wanted = [s.strip().upper() for s in sources if s.strip()]
    unknown = sorted(set(wanted) - set(runners))
    if unknown:
        raise ValueError(f"unknown sources {unknown}; expected some of {sorted(runners)}")

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    status_dir.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RefreshAlreadyRunning(f"another scheduled refresh holds {lock_path}") from exc
        lock.write(f"{os.getpid()}\n")
        lock.flush()

        started = _now()
        outcomes: list[SourceOutcome] = []
        for source in wanted:
            source_started = _now()
            print(f"[scheduled-refresh] {source} {ranking_year}: start", flush=True)
            try:
                summary = runners[source](ranking_year)
                outcomes.append(SourceOutcome(source, True, source_started, _now(), _to_jsonable(summary)))
                print(f"[scheduled-refresh] {source} {ranking_year}: ok", flush=True)
            except Exception as exc:  # one source failing must not hide the others
                outcomes.append(SourceOutcome(
                    source, False, source_started, _now(), error=f"{type(exc).__name__}: {exc}"))
                print(f"[scheduled-refresh] {source} {ranking_year}: FAILED {type(exc).__name__}: {exc}", flush=True)
                traceback.print_exc()

        status = {
            "ranking_year": ranking_year,
            "started_at": started,
            "finished_at": _now(),
            "ok": all(o.ok for o in outcomes),
            "sources": [_to_jsonable(o) for o in outcomes],
        }
        stamp = started.replace(":", "").replace("-", "")
        (status_dir / f"scheduled_refresh_{stamp}.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        (status_dir / "scheduled_refresh_latest.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        return 0 if status["ok"] else 1
