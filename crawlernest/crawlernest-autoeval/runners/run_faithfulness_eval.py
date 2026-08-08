#!/usr/bin/env python3
"""Faithfulness eval for generated explanations.

Checks that an explanation stays inside the evidence it was grounded on: no
invented numbers, no invented universities, and caveats reproduced verbatim. The
check is mechanical (see
``crawlernest/agent/web_agent/generation/faithfulness.py``) — there is no LLM
judge, so the verdict is reproducible and inspectable, the same standard the
warehouse numbers are held to.

Two modes:

``fixture`` (default)
    Run the checker over the golden dataset's stored explanations and compare to
    each entry's expectation. Needs no model, so it runs in CI and guards the
    checker itself against regressions.

``--live``
    Generate the explanation with the configured provider (ds4 when
    ``WEB_AGENT_DS4_BASE_URL`` is set), then check the real output. Reports the
    faithfulness of what the model actually produced; requires a reachable
    server.

Exit codes: 0 = PASS, 1 = FAIL, 2 = usage/setup error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GOLDEN_FILE = Path(__file__).resolve().parents[1] / "datasets" / "faithfulness" / "golden.json"

from crawlernest.agent.web_agent.generation.faithfulness import (  # noqa: E402
    check_faithfulness,
)


def load_golden(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"ERROR golden file not found: {path}")
        sys.exit(2)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"ERROR golden file is not valid JSON: {exc}")
        sys.exit(2)
    if not isinstance(data, list) or not data:
        print("ERROR golden file must be a non-empty list")
        sys.exit(2)
    return data


def generate_live(entry: dict[str, Any]) -> tuple[str, str]:
    """Generate an explanation with the configured provider.

    Returns ``(explanation_text, source)`` where source is "llm" or "fallback".
    """
    from crawlernest.agent.web_agent.generation.ranking_explainer import RankingExplainer
    from crawlernest.agent.web_agent.generation.recommendation_explainer import (
        RecommendationExplainer,
    )

    evidence = entry.get("evidence", {})
    items = evidence.get("items", [])
    caveats = evidence.get("caveats", [])
    query = entry.get("query", "Explain this result.")

    if entry.get("task_kind") == "ranking_explain":
        result = RankingExplainer().explain(
            items=items,
            query=query,
            caveats=caveats,
            deterministic_reply="",
        )
    else:
        result = RecommendationExplainer().explain(
            items=items,
            profile=evidence.get("profile"),
            query=query,
            caveats=caveats,
            deterministic_reply="",
        )
    return result.text, result.source


def evaluate(entries: list[dict[str, Any]], *, live: bool, verbose: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    passed = failed = 0

    for entry in entries:
        evidence = entry.get("evidence", {})
        items = evidence.get("items", [])
        caveats = evidence.get("caveats", [])

        if live:
            explanation, source = generate_live(entry)
        else:
            explanation, source = entry.get("explanation", ""), "fixture"

        report = check_faithfulness(
            explanation=explanation,
            items=items,
            evidence={k: v for k, v in evidence.items() if k not in {"items", "caveats"}} or None,
            caveats=caveats,
        )

        expect = entry.get("expect", {})
        if live:
            # No stored expectation applies to freshly generated text: the model
            # output is what is under test, so any violation is a failure.
            entry_ok = report.faithful
        else:
            entry_ok = report.faithful == expect.get("faithful", True) and sorted(
                set(report.kinds)
            ) == sorted(set(expect.get("violation_kinds", [])))

        passed += entry_ok
        failed += not entry_ok
        results.append(
            {
                "id": entry.get("id"),
                "description": entry.get("description"),
                "status": "PASS" if entry_ok else "FAIL",
                "source": source,
                "faithful": report.faithful,
                "violations": [v.as_dict() for v in report.violations],
                **({"expected": expect} if not live else {}),
            }
        )

        if verbose:
            print(f"[{results[-1]['status']}] {entry.get('id')} — {entry.get('description')}")
            for violation in report.violations:
                print(f"    ! {violation.kind}: {violation.detail}")

    return {
        "mode": "live" if live else "fixture",
        "total": len(entries),
        "passed": passed,
        "failed": failed,
        "result": "PASS" if failed == 0 else "FAIL",
        "entries": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Explanation faithfulness eval runner")
    parser.add_argument("--golden-file", default=str(GOLDEN_FILE))
    parser.add_argument(
        "--live",
        action="store_true",
        help="Generate explanations with the configured provider instead of using stored ones",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    args = parser.parse_args()

    entries = load_golden(Path(args.golden_file))
    summary = evaluate(entries, live=args.live, verbose=not args.json)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"Faithfulness ({summary['mode']} mode): {summary['passed']} passed, {summary['failed']} failed")
        print(f"Result: {summary['result']}")

    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
