#!/usr/bin/env python3
"""Measure an LLM judge against the mechanical faithfulness checker.

    python crawlernest/crawlernest-autoeval/runners/run_judge_calibration.py \
        --base-url http://localhost:11434/v1 --model qwen2.5:7b-instruct

## Why this exists before any judge is wired in

An LLM judge is the only way to catch unfaithfulness the rules cannot see -- a
claim that is technically supported by the evidence but misleading, a caveat
reproduced verbatim and then undercut by the sentence after it. That makes it
tempting to add one and start trusting its verdicts.

The problem is that a judge is itself an unvalidated model, and this repository's
whole posture is that confidence is derived rather than asserted. So the judge is
measured first, on the same golden set the mechanical checker is scored against,
and the number that decides whether it is worth anything is Cohen's kappa: how
much it agrees with the mechanical checker beyond what agreeing by chance would
produce on a set with this class balance.

Nothing here writes to the pipeline. This is a measurement, not a component.

## Reading the output

Three accuracies against the golden labels -- the mechanical checker's, the
judge's, and their union -- plus kappa between the two raters. Kappa near 1 means
the judge mostly restates what the rules already found, so it adds cost without
information. Kappa near 0 means it is uncorrelated with a checker known to be
correct on this set, which is a reason to distrust it, not to celebrate the
diversity. The interesting range is in between, and the cases to read are the
disagreements printed at the end.

Exit code is 0 unless --min-kappa is given and the measurement falls below it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GOLDEN_FILE = Path(__file__).resolve().parents[1] / "datasets" / "faithfulness" / "golden.json"

from crawlernest.agent.web_agent.generation.faithfulness import (  # noqa: E402
    check_faithfulness,
)

JUDGE_SYSTEM = """You audit explanations produced from a fixed block of evidence.

An explanation is FAITHFUL when everything it asserts is supported by the
evidence: every number appears in the evidence or follows from the number of
items given, every institution named appears in the evidence, and every caveat
supplied with the evidence is reproduced without being softened or dropped.

An explanation is UNFAITHFUL when it invents a figure, invents an institution,
rescales or transforms a value, drops a caveat, or restates a caveat in weaker
language.

Answer with a single JSON object and nothing else:
{"faithful": true or false, "reason": "one short sentence"}"""


def build_prompt(entry: dict[str, Any]) -> str:
    evidence = entry.get("evidence", {})
    return json.dumps(
        {
            "evidence_items": evidence.get("items", []),
            "caveats_supplied": evidence.get("caveats", []),
            "other_evidence": {
                k: v for k, v in evidence.items() if k not in {"items", "caveats"}
            },
            "explanation_under_review": entry.get("explanation", ""),
        },
        ensure_ascii=False,
        indent=2,
    )


def ask_judge(base_url: str, model: str, prompt: str, timeout: int) -> tuple[bool | None, str]:
    """Returns (verdict, raw). verdict is None when the reply cannot be parsed."""
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 200,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"transport error: {exc}"

    text = body.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed.get("faithful"), bool):
                return parsed["faithful"], str(parsed.get("reason", "")).strip()
        except ValueError:
            pass
    return None, text.strip()[:160]


def cohens_kappa(a: list[bool], b: list[bool]) -> float:
    """Agreement between two binary raters, corrected for chance."""
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    a_true, b_true = sum(a) / n, sum(b) / n
    expected = a_true * b_true + (1 - a_true) * (1 - b_true)
    if expected >= 1.0:
        # Both raters gave one label to everything; kappa is undefined rather
        # than perfect, and reporting 1.0 here would be a lie.
        return float("nan")
    return (observed - expected) / (1 - expected)


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate an LLM judge against the rule checker.")
    parser.add_argument("--base-url", default="http://localhost:11434/v1",
                        help="OpenAI-compatible base URL")
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--golden-file", default=str(GOLDEN_FILE))
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--min-kappa", type=float, default=None,
                        help="Fail if kappa falls below this. Omit to measure only.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=None,
                        help="Write the JSON report here. Use this rather than shell "
                             "redirection: PowerShell's Out-File adds a UTF-8 BOM that "
                             "makes the result unparseable by json.load.")
    args = parser.parse_args()

    entries = json.loads(Path(args.golden_file).read_text(encoding="utf-8"))

    truth: list[bool] = []
    mechanical: list[bool] = []
    judge: list[bool] = []
    rows: list[dict[str, Any]] = []
    unparsed = 0

    for entry in entries:
        evidence = entry.get("evidence", {})
        report = check_faithfulness(
            explanation=entry.get("explanation", ""),
            items=evidence.get("items", []),
            evidence={k: v for k, v in evidence.items() if k not in {"items", "caveats"}} or None,
            caveats=evidence.get("caveats", []),
        )
        # Ground truth, not the checker's specification. For most cases they are
        # the same; for the faith-1xx cases they differ on purpose, and those are
        # the only ones that can tell you whether a judge adds anything.
        expected = bool(
            entry.get("ground_truth", {}).get(
                "faithful", entry.get("expect", {}).get("faithful", True)
            )
        )
        verdict, reason = ask_judge(args.base_url, args.model, build_prompt(entry), args.timeout)

        if verdict is None:
            unparsed += 1
            # An unusable reply is not a free pass: count it as the judge failing
            # to flag anything, which is the direction that would let a bad
            # explanation through.
            verdict = True

        truth.append(expected)
        mechanical.append(report.faithful)
        judge.append(verdict)
        rows.append({
            "id": entry.get("id"),
            "expected_faithful": expected,
            "mechanical": report.faithful,
            "judge": verdict,
            "judge_reason": reason,
            "description": entry.get("description"),
        })

        if not args.json:
            marks = "".join([
                "." if report.faithful == expected else "M",
                "." if verdict == expected else "J",
            ])
            print(f"  [{marks}] {entry.get('id')}  mech={report.faithful!s:<5} "
                  f"judge={verdict!s:<5} expected={expected}")

    n = len(entries)
    mech_acc = sum(1 for m, t in zip(mechanical, truth) if m == t) / n
    judge_acc = sum(1 for j, t in zip(judge, truth) if j == t) / n
    kappa = cohens_kappa(judge, mechanical)

    # The whole question, in one list: unfaithfulness the rules cannot express
    # and the judge nonetheless catches. Everything else a judge does here is
    # duplication or noise.
    caught_only_by_judge = [
        r["id"] for r in rows
        if r["mechanical"] is True and r["expected_faithful"] is False and r["judge"] is False
    ]
    # And what it would cost: clean text the judge flags and the rules do not.
    false_alarms = [
        r["id"] for r in rows
        if r["expected_faithful"] is True and r["judge"] is False
    ]

    summary = {
        "model": args.model,
        "cases": n,
        "mechanical_accuracy": round(mech_acc, 4),
        "judge_accuracy": round(judge_acc, 4),
        "cohens_kappa_judge_vs_mechanical": None if kappa != kappa else round(kappa, 4),
        "unparseable_judge_replies": unparsed,
        "caught_only_by_judge": caught_only_by_judge,
        "judge_false_alarms_on_clean_text": false_alarms,
        "rows": rows,
    }

    if args.out:
        Path(args.out).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nreport written to {args.out}")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"model                    {args.model}")
        print(f"cases                    {n}")
        print(f"mechanical accuracy      {mech_acc:.4f}")
        print(f"judge accuracy           {judge_acc:.4f}")
        print(f"Cohen's kappa            "
              f"{'undefined (a rater used one label throughout)' if kappa != kappa else f'{kappa:.4f}'}")
        print(f"unparseable judge replies{unparsed:>5}")
        print(f"caught only by the judge {caught_only_by_judge or 'none'}")
        print(f"judge false alarms       {false_alarms or 'none'}")
        print()
        disagreements = [r for r in rows if r["mechanical"] != r["judge"]]
        print(f"disagreements ({len(disagreements)}):")
        for r in disagreements:
            print(f"  {r['id']}  mech={r['mechanical']} judge={r['judge']} "
                  f"expected={r['expected_faithful']}")
            print(f"      {r['description']}")
            if r["judge_reason"]:
                print(f"      judge said: {r['judge_reason']}")

    if args.min_kappa is not None:
        if kappa != kappa or kappa < args.min_kappa:
            print(f"\nFAIL: kappa below the --min-kappa floor of {args.min_kappa}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
