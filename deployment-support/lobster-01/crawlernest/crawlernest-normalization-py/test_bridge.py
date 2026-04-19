"""
test_bridge.py

Integration tests for CNormalizerBridge.

Each test case runs both the C bridge and the Python fallback,
then prints a side-by-side comparison table.

Usage:
    python crawlernest/crawlernest-normalization-py/test_bridge.py
    # or from repo root:
    python -m crawlernest.crawlernest-normalization-py.test_bridge
"""

from __future__ import annotations

import sys
import os

# Allow running directly from the repo root
_repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
_core_path  = os.path.join(os.path.dirname(__file__), "..", "crawlernest-core")
for _p in (_repo_root, os.path.normpath(_core_path)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from entity_resolution.normalizer import (  # type: ignore[import]
    normalize_university_name as py_normalize_name,
)

# Import bridge (works even if C binary absent — falls back automatically)
_bridge_dir = os.path.dirname(__file__)
sys.path.insert(0, _bridge_dir)
from normalizer_bridge import CNormalizerBridge, normalize_country_py

# ─── helpers ──────────────────────────────────────────────────────────────────

def _fmt_row(label: str, c_out: str, py_out: str, match: bool) -> str:
    icon = "✓" if match else "✗"
    return f"  {icon}  {label:<55}  C: {c_out!r:<50}  Py: {py_out!r}"


def _separator(char: str = "─", width: int = 160) -> str:
    return char * width


# ─── test cases ───────────────────────────────────────────────────────────────

NAME_CASES: list[tuple[str, str]] = [
    (
        "Massachusetts Institute of Technology (MIT)",
        "massachusetts institute technology mit",
    ),
    (
        "École Polytechnique Fédérale de Lausanne",
        "ecole polytechnique federale de lausanne",
    ),
    (
        "Ludwig-Maximilians-Universität München",
        "ludwig maximilians universitat munchen",
    ),
]

COUNTRY_CASES: list[tuple[str, str]] = [
    ("USA",                         "United States"),
    ("Hong Kong SAR",               "Hong Kong SAR"),
    ("People's Republic of China",  "China (Mainland)"),
    ("Iran",                        "Iran"),
    ("Russian Federation",          "Russia"),
    ("Macau",                       "Macau SAR"),
    ("ROC",                         "Taiwan"),
]

BATCH_RECORDS: list[dict] = [
    {"name": "Massachusetts Institute of Technology (MIT)", "country": "USA"},
    {"name": "École Polytechnique Fédérale de Lausanne",   "country": "Switzerland"},
    {"name": "Ludwig-Maximilians-Universität München",     "country": "Germany"},
]


# ─── main ─────────────────────────────────────────────────────────────────────

def run_tests() -> None:
    bridge = CNormalizerBridge()

    print()
    print(_separator("═"))
    print("  CLAWER NORMALIZATION BRIDGE — Integration Test Report")
    print(_separator("═"))
    print(f"  C binary available : {bridge.is_available}")
    if bridge.is_available:
        print(f"  C binary path      : {bridge._binary}")
    print(_separator("─"))

    total  = 0
    passed = 0

    # ── name normalization ───────────────────────────────────────────────────
    print("\n  [NAME NORMALIZATION]\n")
    print(f"  {'Input':<55}  {'Expected':<50}  C result / Py result")
    print(_separator("-"))

    for raw, expected in NAME_CASES:
        c_out  = bridge.normalize_name(raw)
        py_out = py_normalize_name(raw)

        c_ok  = (c_out  == expected)
        py_ok = (py_out == expected)

        c_icon  = "✓" if c_ok  else "✗"
        py_icon = "✓" if py_ok else "✗"
        match   = c_out == py_out

        total  += 2
        passed += int(c_ok) + int(py_ok)

        short = raw if len(raw) <= 55 else raw[:52] + "..."
        print(f"  Input : {short}")
        print(f"  Expect: {expected!r}")
        print(f"  C     : {c_icon} {c_out!r}")
        print(f"  Py    : {py_icon} {py_out!r}")
        print(f"  Match : {'YES ✓' if match else 'NO  ✗  (C ≠ Py)'}")
        print()

    # ── country normalization ────────────────────────────────────────────────
    print(_separator("-"))
    print("\n  [COUNTRY NORMALIZATION]\n")
    print(f"  {'Input':<40}  {'Expected':<25}  C result / Py result")
    print(_separator("-"))

    for raw, expected in COUNTRY_CASES:
        c_out  = bridge.normalize_country(raw)
        py_out = normalize_country_py(raw)

        c_ok  = (c_out  == expected)
        py_ok = (py_out == expected)

        c_icon  = "✓" if c_ok  else "✗"
        py_icon = "✓" if py_ok else "✗"
        match   = c_out == py_out

        total  += 2
        passed += int(c_ok) + int(py_ok)

        print(f"  {raw:<40}  {expected:<25}  "
              f"C:{c_icon} {c_out!r:<25}  Py:{py_icon} {py_out!r}")

    # ── batch normalization ──────────────────────────────────────────────────
    print()
    print(_separator("-"))
    print("\n  [BATCH NORMALIZATION]\n")

    batch_results = bridge.normalize_batch(BATCH_RECORDS)
    for i, (rec, result) in enumerate(zip(BATCH_RECORDS, batch_results)):
        print(f"  Record {i+1}: {rec['name'][:60]}")
        print(f"    normalized_name    : {result.get('normalized_name', '')!r}")
        print(f"    normalized_country : {result.get('normalized_country', '')!r}")
        print()

    # ── summary ──────────────────────────────────────────────────────────────
    print(_separator("═"))
    print(f"  SUMMARY : {passed}/{total} assertions passed "
          f"({'PASS' if passed == total else 'SOME FAILED'})")
    print(_separator("═"))
    print()

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
