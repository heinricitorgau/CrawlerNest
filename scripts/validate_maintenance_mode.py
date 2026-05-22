#!/usr/bin/env python3
"""Minimal validation for controlled maintenance mode helpers."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from inspect_source_freshness import inspect, load_snapshot


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="crawlernest-maint-") as tmp:
        root = Path(tmp)

        missing_snapshot = root / "missing.json"
        snapshot, warnings = load_snapshot(missing_snapshot)
        report = inspect(snapshot, warnings)
        check(report["freshness_state"] == "critical", "missing snapshot should be critical")
        check(warnings, "missing snapshot should warn")

        malformed = root / "malformed.json"
        malformed.write_text("{broken", encoding="utf-8")
        snapshot, warnings = load_snapshot(malformed)
        report = inspect(snapshot, warnings)
        check(report["freshness_state"] == "critical", "malformed snapshot should be critical")
        check(warnings, "malformed snapshot should warn")

        minimal = root / "minimal.json"
        minimal.write_text(
            json.dumps({"snapshot_timestamp": "2026-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        snapshot, warnings = load_snapshot(minimal)
        report = inspect(snapshot, warnings)
        check(report["aggregation"]["aggregated_count"] == 0, "missing count should default to 0")
        check(report["source_coverage"]["missing_sources"], "missing sources should be reported")

    print("[maintenance-mode-validation] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
