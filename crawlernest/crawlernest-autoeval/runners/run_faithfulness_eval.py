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

In fixture mode the run also scores **the checker itself as a detector**:
per-violation-kind precision, recall and F1 against the golden expectations. A
pass count alone cannot distinguish a checker that catches everything from one
that also fires on clean text, and the false-positive rate is the number that
decides whether the check can gate anything. Reading it requires the dataset to
carry enough faithful cases to put in the denominator, which is why roughly half
the golden entries expect no violation at all.

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


VIOLATION_KINDS = ("unsupported_number", "missing_caveat", "unsupported_university")


def _prf(true_positive: int, false_positive: int, false_negative: int) -> dict[str, float]:
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def ground_truth_coverage(entries: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    """How much actual unfaithfulness the rules reach, as opposed to specified.

    ``expect`` says what the checker should report; ``ground_truth`` says whether
    the explanation is in fact faithful. For most of the dataset they agree,
    because those cases were written from the checker's own taxonomy. The
    faith-1xx cases were written the other way round -- unfaithfulness first,
    then checked to confirm no rule reaches it -- so there the two differ.

    Reporting only the first number would say the checker is perfect. It is
    perfect against its specification, and that is a smaller claim.
    """
    by_id = {e.get("id"): e for e in entries}
    tracked = []
    for result in results:
        entry = by_id.get(result["id"], {})
        truth = entry.get("ground_truth", {}).get(
            "faithful", entry.get("expect", {}).get("faithful", True)
        )
        tracked.append((bool(truth), bool(result["faithful"]), entry))

    unfaithful = [t for t in tracked if not t[0]]
    caught = [t for t in unfaithful if not t[1]]
    beyond = [t for t in unfaithful if t[1]]
    clean = [t for t in tracked if t[0]]
    false_alarms = [t for t in clean if not t[1]]

    return {
        "cases": len(tracked),
        "actually_unfaithful": len(unfaithful),
        "caught_by_rules": len(caught),
        "recall_against_truth": round(len(caught) / len(unfaithful), 4) if unfaithful else 1.0,
        "beyond_the_rules": [t[2].get("id") for t in beyond],
        "actually_faithful": len(clean),
        "false_alarms": [t[2].get("id") for t in false_alarms],
    }


def detector_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Score the checker as a detector, per violation kind and overall.

    One case contributes at most one true positive per kind: the question is
    whether the kind was raised on that case, not how many times.
    """
    per_kind: dict[str, Any] = {}
    totals = {"tp": 0, "fp": 0, "fn": 0}

    for kind in VIOLATION_KINDS:
        tp = fp = fn = 0
        for result in results:
            expected = kind in set(result.get("expected", {}).get("violation_kinds", []))
            detected = kind in {v["kind"] for v in result["violations"]}
            tp += expected and detected
            fp += (not expected) and detected
            fn += expected and (not detected)
        per_kind[kind] = {"tp": tp, "fp": fp, "fn": fn, **_prf(tp, fp, fn)}
        totals["tp"] += tp
        totals["fp"] += fp
        totals["fn"] += fn

    macro = {
        metric: round(sum(per_kind[k][metric] for k in VIOLATION_KINDS) / len(VIOLATION_KINDS), 4)
        for metric in ("precision", "recall", "f1")
    }

    # Case-level verdict accuracy, and the false-positive rate on clean text --
    # the number that decides whether this check can gate a release.
    clean = [r for r in results if r.get("expected", {}).get("faithful", True)]
    flagged_clean = sum(1 for r in clean if not r["faithful"])
    correct = sum(1 for r in results if r["faithful"] == r.get("expected", {}).get("faithful", True))

    return {
        "per_kind": per_kind,
        "micro": {**totals, **_prf(totals["tp"], totals["fp"], totals["fn"])},
        "macro": macro,
        "verdict_accuracy": round(correct / len(results), 4) if results else 1.0,
        "clean_cases": len(clean),
        "false_positive_rate_on_clean": round(flagged_clean / len(clean), 4) if clean else 0.0,
    }


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

    summary = {
        "mode": "live" if live else "fixture",
        "total": len(entries),
        "passed": passed,
        "failed": failed,
        "result": "PASS" if failed == 0 else "FAIL",
        "entries": results,
    }
    if not live:
        summary["detector"] = detector_metrics(results)
        summary["ground_truth"] = ground_truth_coverage(entries, results)
    return summary


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
        detector = summary.get("detector")
        if detector:
            print()
            print("Checker scored as a detector")
            print(f"  {'kind':<26} {'TP':>3} {'FP':>3} {'FN':>3}   {'P':>6} {'R':>6} {'F1':>6}")
            for kind, stats in detector["per_kind"].items():
                print(
                    f"  {kind:<26} {stats['tp']:>3} {stats['fp']:>3} {stats['fn']:>3}   "
                    f"{stats['precision']:>6.3f} {stats['recall']:>6.3f} {stats['f1']:>6.3f}"
                )
            micro = detector["micro"]
            print(
                f"  {'micro-average':<26} {micro['tp']:>3} {micro['fp']:>3} {micro['fn']:>3}   "
                f"{micro['precision']:>6.3f} {micro['recall']:>6.3f} {micro['f1']:>6.3f}"
            )
            print(f"  macro F1 {detector['macro']['f1']:.3f}   verdict accuracy {detector['verdict_accuracy']:.3f}")
            print(
                f"  false positives on clean text: "
                f"{detector['false_positive_rate_on_clean']:.3f} over {detector['clean_cases']} cases "
                "the specification calls clean"
            )
        coverage = summary.get("ground_truth")
        if coverage:
            print()
            print("Checker measured against what is actually unfaithful")
            print(f"  cases                    {coverage['cases']}")
            print(f"  actually unfaithful      {coverage['actually_unfaithful']}")
            print(f"  caught by the rules      {coverage['caught_by_rules']}")
            print(f"  recall against truth     {coverage['recall_against_truth']:.3f}")
            print(f"  beyond the rules         {len(coverage['beyond_the_rules'])} "
                  f"({', '.join(coverage['beyond_the_rules']) or 'none'})")
            print(f"  false alarms             {coverage['false_alarms'] or 'none'}")
        print(f"\nResult: {summary['result']}")

    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
