#!/usr/bin/env python3
"""Minimal validation for maintenance phase 3 trust summary."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from build_operational_trust_summary import build, derive_trust, validate_trust_summary


def main() -> int:
    validate_trust_summary()
    with tempfile.TemporaryDirectory(prefix="crawlernest-phase3-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        reports.mkdir()
        (reports / "maintenance_readiness_summary.md").write_text(
            "\n".join(
                [
                    "# Maintenance",
                    "Freshness state: **critical**",
                    "- Freshness confidence: low",
                    "- Source completeness confidence: low",
                    "- Operational confidence level: limited",
                    "- Demo caveat presence: required",
                ]
            ),
            encoding="utf-8",
        )
        (reports / "demo_caveats.md").write_text(
            "# Caveats\n- It does not hide stale data.\n", encoding="utf-8"
        )
        (reports / "drift_timeline.md").write_text(
            "# Drift\nOverall severity: info\n", encoding="utf-8"
        )
        (reports / "freshness_escalation.md").write_text("# Freshness\n", encoding="utf-8")
        snapshot = root / "latest_status.json"
        snapshot.write_text(json.dumps({"source_counts": [{"source_code": "QS", "count": 10}]}), encoding="utf-8")
        summary, warnings = derive_trust(reports, snapshot)
        assert summary["operational_trust_level"] == "critical"
        assert "THE" in summary["missing_sources"]
        assert not warnings
        assert "Operational Trust Summary" in build(reports, snapshot)
    print("[maintenance-phase3-validation] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
