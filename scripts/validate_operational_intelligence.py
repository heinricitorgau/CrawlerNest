#!/usr/bin/env python3
"""Minimal validation for operational intelligence snapshot tolerance."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from build_snapshot_timeline import build_payload, load_snapshot_records


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="crawlernest-oi-") as tmp:
        root = Path(tmp)

        empty = root / "empty"
        empty.mkdir()
        records, warnings = load_snapshot_records(empty)
        assert_true(records == [], "empty snapshot dir should produce no records")
        assert_true(warnings == [], "empty snapshot dir should not warn")

        mixed = root / "mixed"
        mixed.mkdir()
        (mixed / "broken.json").write_text("{not-json", encoding="utf-8")
        (mixed / "missing_fields.json").write_text(
            json.dumps({"snapshot_timestamp": "2026-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        records, warnings = load_snapshot_records(mixed)
        payload = build_payload(records, warnings)
        assert_true(len(records) == 1, "missing-field snapshot should be retained")
        assert_true(len(warnings) == 1, "malformed snapshot should warn once")
        assert_true(payload["timeline"][0]["aggregated_count"] == 0, "missing count defaults to 0")

    print("[operational-intelligence-validation] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
