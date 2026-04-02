"""
Test and comparison script for C bridge vs Python fallback normalization.
Run: python3 crawlernest/crawlernest-normalization-py/test_bridge.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "crawlernest-normalization-py"))
sys.path.insert(0, str(Path(__file__).parent.parent / "crawlernest-core"))

from normalizer_bridge import CNormalizerBridge, normalize_name_py, normalize_country_py

NAME_CASES = [
    ("Massachusetts Institute of Technology (MIT)", "massachusetts institute technology mit"),
    ("École Polytechnique Fédérale de Lausanne", "ecole polytechnique federale lausanne"),
    ("Ludwig-Maximilians-Universität München", "ludwig maximilians universitat munchen"),
    ("National University of Singapore (NUS)", "national university singapore nus"),
    ("The University of Hong Kong", "university hong kong"),
    ("Universität Heidelberg", "universitat heidelberg"),
    ("LMU Munich", "lmu munich"),
]

COUNTRY_CASES = [
    ("USA", "United States"),
    ("United States of America", "United States"),
    ("UK", "United Kingdom"),
    ("Hong Kong SAR", "Hong Kong SAR"),
    ("People's Republic of China", "China (Mainland)"),
    ("South Korea", "South Korea"),
    ("Republic of Korea", "South Korea"),
]


def main() -> None:
    bridge = CNormalizerBridge()
    print(f"C engine available: {bridge.is_available}")
    print(f"Binary path: {bridge._binary}\n")

    print("=" * 80)
    print("UNIVERSITY NAME NORMALIZATION")
    print("=" * 80)
    print(f"{'Input':<50} {'Python':<35} {'Expected':<35}")
    print("-" * 80)
    all_pass = True
    for raw, expected in NAME_CASES:
        py_result = normalize_name_py(raw)
        match = "✅" if py_result == expected else "❌"
        if py_result != expected:
            all_pass = False
        print(f"{raw[:48]:<50} {py_result:<35} {match}")

    print("\n" + "=" * 80)
    print("COUNTRY NORMALIZATION")
    print("=" * 80)
    print(f"{'Input':<40} {'Python':<30} {'Expected':<30}")
    print("-" * 80)
    for raw, expected in COUNTRY_CASES:
        py_result = normalize_country_py(raw)
        match = "✅" if py_result == expected else "❌"
        if py_result != expected:
            all_pass = False
        print(f"{raw:<40} {py_result:<30} {match}")

    print("\n" + "=" * 80)
    overall = "ALL PASS ✅" if all_pass else "SOME FAILURES ❌"
    print(f"Result: {overall}")


if __name__ == "__main__":
    main()
