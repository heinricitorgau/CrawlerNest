

#!/usr/bin/env python3
"""CrawlerNest AutoEval - Extractor evaluator.

This runner evaluates extraction quality against a fixed golden dataset,
computes aggregate metrics, prints a concise report, and can append the run
summary to ``results.tsv``.

Supported dataset shape
-----------------------
The dataset JSON may be either:
1. a list of samples
2. an object with a top-level ``samples`` list

Each sample should contain at least:
- input text/html/content/raw field (one of: input, raw, text, html, content)
- expected output dict (one of: expected, ground_truth, golden, target)

Example sample:
{
  "id": "ntu-001",
  "input": "<html>...</html>",
  "expected": {
    "university": "National Taiwan University",
    "program": "Computer Science",
    "quota": 120
  },
  "required_fields": ["university", "program"]
}

The script tries to load the extractor implementation from:
``crawlernest-extractors/extractor.py``
and then searches for a callable such as:
- extract
- extract_fields
- run_extractor
- parse
- extract_admission_data

If no supported callable is found, the script exits with a clear error message.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


INPUT_KEYS = ("input", "raw", "text", "html", "content")
EXPECTED_KEYS = ("expected", "ground_truth", "golden", "target")
EXTRACTOR_FUNCTION_NAMES = (
    "extract",
    "extract_fields",
    "run_extractor",
    "parse",
    "extract_admission_data",
)
EXTRACTOR_METHOD_NAMES = (
    "extract",
    "extract_fields",
    "run",
    "parse",
)


@dataclass
class SampleResult:
    sample_id: str
    required_total: int
    required_filled: int
    required_exact: int
    optional_total: int
    optional_filled: int
    optional_exact: int
    field_errors: int
    runtime_s: float
    exception: str | None = None


@dataclass
class AggregateResult:
    sample_count: int
    required_fill_rate: float
    exact_match_rate: float
    optional_fill_rate: float
    error_count: int
    error_rate: float
    runtime_s: float
    score: float
    status: str


class DatasetError(ValueError):
    """Raised when the dataset format is invalid."""


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    autoeval_root = script_dir.parent
    default_dataset = autoeval_root / "datasets" / "extractor_goldens" / "samples.json"
    default_results = autoeval_root / "results.tsv"
    default_reports = autoeval_root / "reports"

    parser = argparse.ArgumentParser(description="Run extractor evaluation for CrawlerNest AutoEval.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=default_dataset,
        help="Path to the golden dataset JSON file.",
    )
    parser.add_argument(
        "--results-tsv",
        type=Path,
        default=default_results,
        help="Path to results.tsv. Use --no-log to skip writing.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Optional path for a detailed JSON report. Defaults to reports/latest_extractor_eval.json.",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="baseline extractor evaluation",
        help="Description written to results.tsv.",
    )
    parser.add_argument(
        "--status",
        type=str,
        default="keep",
        choices=("keep", "discard", "crash"),
        help="Status label written to results.tsv.",
    )
    parser.add_argument(
        "--extractor-file",
        type=Path,
        default=None,
        help="Optional direct path to extractor.py. By default the script auto-discovers crawlernest-extractors/extractor.py.",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Do not append the summary row to results.tsv.",
    )
    parser.add_argument(
        "--fail-on-exception",
        action="store_true",
        help="Exit with code 1 if any sample raises an exception.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat missing expected keys or malformed outputs as fatal dataset/extractor errors.",
    )
    parser.add_argument(
        "--top-errors",
        type=int,
        default=10,
        help="Maximum number of per-sample failures to print in the console summary.",
    )
    parser.add_argument(
        "--print-sample-details",
        action="store_true",
        help="Print one line per sample with metrics.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Optional explicit CrawlerNest project root.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=default_reports,
        help="Directory used when --report-json is omitted.",
    )
    return parser.parse_args()


def discover_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "crawlernest-extractors").exists() and (candidate / "crawlernest-core").exists():
            return candidate
    raise FileNotFoundError(
        "Unable to discover the CrawlerNest project root from the current script location. "
        "Use --project-root to specify it explicitly."
    )


def discover_extractor_file(project_root: Path) -> Path:
    extractor_file = project_root / "crawlernest-extractors" / "extractor.py"
    if not extractor_file.exists():
        raise FileNotFoundError(f"Extractor file not found: {extractor_file}")
    return extractor_file


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def extract_samples(dataset: Any) -> list[dict[str, Any]]:
    if isinstance(dataset, list):
        samples = dataset
    elif isinstance(dataset, dict) and isinstance(dataset.get("samples"), list):
        samples = dataset["samples"]
    else:
        raise DatasetError(
            "Dataset must be either a JSON list or an object containing a top-level 'samples' list."
        )

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(samples):
        if not isinstance(item, dict):
            raise DatasetError(f"Sample #{index} must be a JSON object.")
        normalized.append(item)
    if not normalized:
        raise DatasetError("Dataset contains zero samples.")
    return normalized


def first_present(mapping: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def canonicalize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isfinite(value):
            return round(value, 6)
        return value
    if isinstance(value, str):
        normalized = " ".join(value.strip().split())
        return normalized.casefold()
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return [canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): canonicalize(val) for key, val in sorted(value.items(), key=lambda kv: str(kv[0]))}
    return str(value).strip().casefold()


def is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def try_load_extractor_callable(extractor_file: Path) -> Callable[[Any], Any]:
    module_name = f"crawlernest_autoeval_dynamic_extractor_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(module_name, extractor_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load extractor module from {extractor_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    for name in EXTRACTOR_FUNCTION_NAMES:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn

    extractor_cls = getattr(module, "Extractor", None)
    if extractor_cls is not None:
        try:
            instance = extractor_cls()
        except TypeError as exc:
            raise TypeError(
                "Found 'Extractor' class but it could not be instantiated without arguments. "
                "Either add a zero-argument constructor or expose a module-level function such as 'extract'."
            ) from exc
        for name in EXTRACTOR_METHOD_NAMES:
            method = getattr(instance, name, None)
            if callable(method):
                return method

    available = sorted(name for name in dir(module) if not name.startswith("_"))
    raise AttributeError(
        "No supported extractor callable found in extractor.py. Expected one of "
        f"{', '.join(EXTRACTOR_FUNCTION_NAMES)} or an Extractor class with one of "
        f"{', '.join(EXTRACTOR_METHOD_NAMES)}. Available public names: {available}"
    )


def invoke_extractor(extractor_fn: Callable[[Any], Any], raw_input: Any) -> Any:
    try:
        return extractor_fn(raw_input)
    except TypeError:
        # Small compatibility shim for extractors that expect string input only.
        if isinstance(raw_input, dict):
            for key in INPUT_KEYS:
                value = raw_input.get(key)
                if value is not None:
                    return extractor_fn(value)
        raise


def compare_sample(sample: dict[str, Any], extractor_fn: Callable[[Any], Any], strict: bool) -> tuple[SampleResult, dict[str, Any]]:
    sample_id = str(sample.get("id") or sample.get("sample_id") or sample.get("url") or f"sample-{id(sample)}")
    raw_input = first_present(sample, INPUT_KEYS)
    expected = first_present(sample, EXPECTED_KEYS)

    if raw_input is None:
        raise DatasetError(f"Sample '{sample_id}' is missing an input field. Expected one of: {INPUT_KEYS}")
    if not isinstance(expected, dict):
        raise DatasetError(f"Sample '{sample_id}' is missing an expected output object. Expected one of: {EXPECTED_KEYS}")

    expected_keys = list(expected.keys())
    declared_required = sample.get("required_fields")
    if declared_required is None:
        required_fields = expected_keys
    elif isinstance(declared_required, list):
        required_fields = [str(item) for item in declared_required]
    else:
        raise DatasetError(f"Sample '{sample_id}' has invalid required_fields; expected a list of strings.")

    optional_fields = [key for key in expected_keys if key not in required_fields]

    start = time.perf_counter()
    exception_message: str | None = None
    try:
        predicted = invoke_extractor(extractor_fn, raw_input)
    except Exception as exc:  # noqa: BLE001
        runtime_s = time.perf_counter() - start
        exception_message = f"{type(exc).__name__}: {exc}"
        result = SampleResult(
            sample_id=sample_id,
            required_total=len(required_fields),
            required_filled=0,
            required_exact=0,
            optional_total=len(optional_fields),
            optional_filled=0,
            optional_exact=0,
            field_errors=len(required_fields) + len(optional_fields),
            runtime_s=runtime_s,
            exception=exception_message,
        )
        details = {
            "sample_id": sample_id,
            "expected": expected,
            "predicted": None,
            "missing_fields": required_fields,
            "mismatch_fields": expected_keys,
            "exception": exception_message,
            "runtime_s": round(runtime_s, 6),
        }
        return result, details

    runtime_s = time.perf_counter() - start
    if predicted is None:
        predicted = {}
    if not isinstance(predicted, dict):
        if strict:
            raise TypeError(
                f"Sample '{sample_id}' produced a non-dict extractor output of type {type(predicted).__name__}."
            )
        predicted = {"_value": predicted}

    required_filled = 0
    required_exact = 0
    optional_filled = 0
    optional_exact = 0
    field_errors = 0
    missing_fields: list[str] = []
    mismatch_fields: list[str] = []

    for field in required_fields:
        pred_value = predicted.get(field)
        exp_value = expected.get(field)
        if is_filled(pred_value):
            required_filled += 1
        else:
            missing_fields.append(field)
            field_errors += 1
        if canonicalize(pred_value) == canonicalize(exp_value):
            required_exact += 1
        else:
            if field not in mismatch_fields:
                mismatch_fields.append(field)
            if is_filled(pred_value):
                field_errors += 1

    for field in optional_fields:
        pred_value = predicted.get(field)
        exp_value = expected.get(field)
        if is_filled(pred_value):
            optional_filled += 1
        if canonicalize(pred_value) == canonicalize(exp_value):
            optional_exact += 1
        else:
            if field not in mismatch_fields:
                mismatch_fields.append(field)
            if is_filled(pred_value) or is_filled(exp_value):
                field_errors += 1

    result = SampleResult(
        sample_id=sample_id,
        required_total=len(required_fields),
        required_filled=required_filled,
        required_exact=required_exact,
        optional_total=len(optional_fields),
        optional_filled=optional_filled,
        optional_exact=optional_exact,
        field_errors=field_errors,
        runtime_s=runtime_s,
        exception=exception_message,
    )
    details = {
        "sample_id": sample_id,
        "expected": expected,
        "predicted": predicted,
        "missing_fields": missing_fields,
        "mismatch_fields": mismatch_fields,
        "exception": exception_message,
        "runtime_s": round(runtime_s, 6),
    }
    return result, details


def aggregate_results(sample_results: list[SampleResult]) -> AggregateResult:
    sample_count = len(sample_results)
    total_required = sum(item.required_total for item in sample_results)
    total_required_filled = sum(item.required_filled for item in sample_results)
    total_required_exact = sum(item.required_exact for item in sample_results)
    total_optional = sum(item.optional_total for item in sample_results)
    total_optional_filled = sum(item.optional_filled for item in sample_results)
    total_optional_exact = sum(item.optional_exact for item in sample_results)
    error_count = sum(item.field_errors for item in sample_results)
    total_runtime = sum(item.runtime_s for item in sample_results)
    crashed = any(item.exception for item in sample_results)

    total_expected_fields = total_required + total_optional
    required_fill_rate = total_required_filled / total_required if total_required else 0.0
    exact_match_rate = (
        (total_required_exact + total_optional_exact) / total_expected_fields if total_expected_fields else 0.0
    )
    optional_fill_rate = total_optional_filled / total_optional if total_optional else 1.0
    error_rate = error_count / total_expected_fields if total_expected_fields else 0.0
    avg_runtime = total_runtime / sample_count if sample_count else 0.0

    # Tunable but simple scoring formula. Higher is better.
    runtime_penalty = min(avg_runtime / 10.0, 1.0) * 0.05
    score = (
        0.45 * exact_match_rate
        + 0.35 * required_fill_rate
        + 0.15 * optional_fill_rate
        - 0.10 * error_rate
        - runtime_penalty
    )
    score = max(0.0, min(1.0, score))

    status = "crash" if crashed else "keep"
    return AggregateResult(
        sample_count=sample_count,
        required_fill_rate=required_fill_rate,
        exact_match_rate=exact_match_rate,
        optional_fill_rate=optional_fill_rate,
        error_count=error_count,
        error_rate=error_rate,
        runtime_s=total_runtime,
        score=score,
        status=status,
    )


def current_git_commit(project_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
        commit = completed.stdout.strip()
        return commit or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def ensure_results_tsv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(
            [
                "commit",
                "score",
                "required_fill_rate",
                "exact_match_rate",
                "error_count",
                "runtime_s",
                "status",
                "description",
            ]
        )


def append_results_row(
    path: Path,
    commit_hash: str,
    aggregate: AggregateResult,
    description: str,
    forced_status: str | None,
) -> None:
    ensure_results_tsv(path)
    status = aggregate.status if forced_status is None else forced_status
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(
            [
                commit_hash,
                f"{aggregate.score:.6f}",
                f"{aggregate.required_fill_rate:.6f}",
                f"{aggregate.exact_match_rate:.6f}",
                str(aggregate.error_count),
                f"{aggregate.runtime_s:.6f}",
                status,
                description,
            ]
        )


def build_report(
    dataset_path: Path,
    extractor_file: Path,
    aggregate: AggregateResult,
    sample_results: list[SampleResult],
    details: list[dict[str, Any]],
    description: str,
    commit_hash: str,
) -> dict[str, Any]:
    return {
        "description": description,
        "commit": commit_hash,
        "dataset": str(dataset_path),
        "extractor_file": str(extractor_file),
        "summary": {
            "sample_count": aggregate.sample_count,
            "required_fill_rate": round(aggregate.required_fill_rate, 6),
            "exact_match_rate": round(aggregate.exact_match_rate, 6),
            "optional_fill_rate": round(aggregate.optional_fill_rate, 6),
            "error_count": aggregate.error_count,
            "error_rate": round(aggregate.error_rate, 6),
            "runtime_s": round(aggregate.runtime_s, 6),
            "score": round(aggregate.score, 6),
            "status": aggregate.status,
        },
        "samples": [
            {
                "sample_id": result.sample_id,
                "required_total": result.required_total,
                "required_filled": result.required_filled,
                "required_exact": result.required_exact,
                "optional_total": result.optional_total,
                "optional_filled": result.optional_filled,
                "optional_exact": result.optional_exact,
                "field_errors": result.field_errors,
                "runtime_s": round(result.runtime_s, 6),
                "exception": result.exception,
                **detail,
            }
            for result, detail in zip(sample_results, details, strict=False)
        ],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def print_console_summary(
    aggregate: AggregateResult,
    sample_results: list[SampleResult],
    details: list[dict[str, Any]],
    top_errors: int,
    print_sample_details: bool,
) -> None:
    print("---")
    print(f"sample_count:         {aggregate.sample_count}")
    print(f"required_fill_rate:  {aggregate.required_fill_rate:.6f}")
    print(f"exact_match_rate:    {aggregate.exact_match_rate:.6f}")
    print(f"optional_fill_rate:  {aggregate.optional_fill_rate:.6f}")
    print(f"error_count:         {aggregate.error_count}")
    print(f"error_rate:          {aggregate.error_rate:.6f}")
    print(f"runtime_s:           {aggregate.runtime_s:.6f}")
    print(f"score:               {aggregate.score:.6f}")
    print(f"status:              {aggregate.status}")

    if print_sample_details:
        print("---")
        for result in sample_results:
            print(
                f"[{result.sample_id}] req={result.required_exact}/{result.required_total} "
                f"filled={result.required_filled}/{result.required_total} "
                f"opt={result.optional_exact}/{result.optional_total} "
                f"errors={result.field_errors} runtime={result.runtime_s:.4f}s"
            )

    failures = [detail for detail in details if detail.get("exception") or detail.get("missing_fields") or detail.get("mismatch_fields")]
    if failures:
        print("---")
        print(f"top_failures_shown:   {min(len(failures), top_errors)}")
        for detail in failures[:top_errors]:
            sample_id = detail.get("sample_id", "unknown")
            print(f"- {sample_id}")
            if detail.get("exception"):
                print(f"    exception: {detail['exception']}")
            if detail.get("missing_fields"):
                print(f"    missing:   {detail['missing_fields']}")
            if detail.get("mismatch_fields"):
                print(f"    mismatch:  {detail['mismatch_fields']}")


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    autoeval_root = script_dir.parent
    project_root = args.project_root.resolve() if args.project_root else discover_project_root(autoeval_root)
    extractor_file = args.extractor_file.resolve() if args.extractor_file else discover_extractor_file(project_root)
    dataset_path = args.dataset.resolve()

    if args.report_json is None:
        report_json = args.report_dir.resolve() / "latest_extractor_eval.json"
    else:
        report_json = args.report_json.resolve()

    dataset = load_json(dataset_path)
    samples = extract_samples(dataset)
    extractor_fn = try_load_extractor_callable(extractor_file)

    sample_results: list[SampleResult] = []
    details: list[dict[str, Any]] = []
    for sample in samples:
        result, detail = compare_sample(sample, extractor_fn, strict=args.strict)
        sample_results.append(result)
        details.append(detail)

    aggregate = aggregate_results(sample_results)
    commit_hash = current_git_commit(project_root)
    report = build_report(
        dataset_path=dataset_path,
        extractor_file=extractor_file,
        aggregate=aggregate,
        sample_results=sample_results,
        details=details,
        description=args.description,
        commit_hash=commit_hash,
    )

    write_report(report_json, report)
    if not args.no_log:
        forced_status = "crash" if aggregate.status == "crash" else args.status
        append_results_row(
            path=args.results_tsv.resolve(),
            commit_hash=commit_hash,
            aggregate=aggregate,
            description=args.description,
            forced_status=forced_status,
        )

    print_console_summary(
        aggregate=aggregate,
        sample_results=sample_results,
        details=details,
        top_errors=args.top_errors,
        print_sample_details=args.print_sample_details,
    )
    print(f"report_json:          {report_json}")
    if not args.no_log:
        print(f"results_tsv:          {args.results_tsv.resolve()}")

    has_exceptions = any(item.exception for item in sample_results)
    if has_exceptions and args.fail_on_exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())