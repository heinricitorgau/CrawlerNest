#!/usr/bin/env python3
"""Minimal validation for operational consolidation report tolerance."""

from __future__ import annotations

from build_operational_index_summary import validate_missing_empty_malformed


def main() -> int:
    validate_missing_empty_malformed()
    print("[operational-consolidation-validation] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
