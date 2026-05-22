#!/usr/bin/env python3
"""Minimal validation for maintenance phase 2 helpers."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from build_demo_caveats import build_caveats, validate_demo_caveats
from inspect_source_freshness import inspect, load_snapshot


def main() -> int:
    validate_demo_caveats()
    with tempfile.TemporaryDirectory(prefix="crawlernest-phase2-") as tmp:
        root = Path(tmp)
        empty = root / "empty.json"
        empty.write_text(json.dumps({}), encoding="utf-8")
        snapshot, warnings = load_snapshot(empty)
        report = inspect(snapshot, warnings)
        assert report["freshness_state"] == "critical"
        assert report["source_coverage"]["missing_sources"]
        reports = root / "reports"
        reports.mkdir()
        result = build_caveats(reports, empty)
        assert "missing input" in result
    print("[maintenance-phase2-validation] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
