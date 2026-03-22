#!/usr/bin/env python3
"""CrawlerNest AutoEval - extractor auto-improvement loop.

Flow:
1. Evaluate current extractor baseline
2. Ask an external coding agent / CLI to modify extractor.py, or wait for a manual edit
3. Re-evaluate
4. Keep or revert based on score / error_count
5. Repeat

This script is intentionally agent-agnostic:
- You provide the external modifier command with --modifier-cmd
- The command can call antigravity, codex, claude code, or any CLI tool
- The command may use placeholders such as:
    {extractor}
    {prompt_file}
    {project_root}
    {autoeval_root}
    {iteration}
    {baseline_report}
    {candidate_report}

Example:
    python crawlernest/crawlernest-autoeval/runners/run_extractor_autoloop.py \
      --modifier-cmd 'antigravity --prompt-file {prompt_file}'

If the command exits non-zero, the candidate is treated as a failed iteration.
With ``--manual``, the script pauses each iteration so the user can edit ``extractor.py`` before evaluation.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class EvalSummary:
    score: float
    required_fill_rate: float
    exact_match_rate: float
    optional_fill_rate: float
    error_count: int
    error_rate: float
    runtime_s: float
    status: str
    report_path: Path


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    autoeval_root = script_dir.parent

    parser = argparse.ArgumentParser(
        description="Auto loop: evaluate extractor, modify it with an external agent, then re-evaluate."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="CrawlerNest project root. Auto-discovered if omitted.",
    )
    parser.add_argument(
        "--extractor-file",
        type=Path,
        default=None,
        help="Path to crawlernest-extractors/extractor.py. Auto-discovered if omitted.",
    )
    parser.add_argument(
        "--eval-runner",
        type=Path,
        default=script_dir / "run_extractor_eval.py",
        help="Path to run_extractor_eval.py",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=autoeval_root / "datasets" / "extractor_goldens" / "samples.json",
        help="Golden dataset JSON path.",
    )
    parser.add_argument(
        "--eval-spec",
        type=Path,
        default=autoeval_root / "eval_spec.md",
        help="Evaluation spec path.",
    )
    parser.add_argument(
        "--program-md",
        type=Path,
        default=autoeval_root / "program.md",
        help="Program.md path.",
    )
    parser.add_argument(
        "--modifier-cmd",
        type=str,
        default=None,
        help=(
            "External modifier command. Supports placeholders: "
            "{extractor}, {prompt_file}, {project_root}, {autoeval_root}, "
            "{iteration}, {baseline_report}, {candidate_report}. Not required when --manual is enabled."
        ),
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Maximum improvement iterations.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=autoeval_root / "sandbox" / "autoloop",
        help="Working directory for reports, prompts, backups, and logs.",
    )
    parser.add_argument(
        "--description-prefix",
        type=str,
        default="autoloop extractor iteration",
        help="Prefix for descriptions written to loop history.",
    )
    parser.add_argument(
        "--min-score-improvement",
        type=float,
        default=0.0001,
        help="Minimum score gain required to keep a candidate.",
    )
    parser.add_argument(
        "--max-error-increase",
        type=int,
        default=0,
        help="Maximum allowed increase in error_count.",
    )
    parser.add_argument(
        "--stop-on-no-improvement",
        action="store_true",
        help="Stop after the first non-improving iteration.",
    )
    parser.add_argument(
        "--python-bin",
        type=str,
        default=sys.executable,
        help="Python interpreter used to run the evaluator.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate prompt and show commands, but do not execute modifier command.",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Manual mode: generate the prompt, wait for the user to edit extractor.py, then continue evaluation without running an external modifier command.",
    )
    parser.add_argument(
        "--manual-open",
        action="store_true",
        help="When used with --manual on macOS, automatically open the prompt file and extractor.py before waiting for Enter.",
    )
    return parser.parse_args()


def discover_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "crawlernest-extractors").exists() and (candidate / "crawlernest-core").exists():
            return candidate
    raise FileNotFoundError("Unable to discover project root. Use --project-root.")


def discover_extractor_file(project_root: Path) -> Path:
    path = project_root / "crawlernest-extractors" / "extractor.py"
    if not path.exists():
        raise FileNotFoundError(f"Extractor file not found: {path}")
    return path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_eval(
    python_bin: str,
    eval_runner: Path,
    dataset: Path,
    report_path: Path,
    description: str,
) -> EvalSummary:
    cmd = [
        python_bin,
        str(eval_runner),
        "--dataset",
        str(dataset),
        "--report-json",
        str(report_path),
        "--description",
        description,
        "--no-log",
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        message = "\n".join(x for x in [stdout, stderr] if x)
        raise RuntimeError(f"Evaluator failed:\n{message}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = report["summary"]
    return EvalSummary(
        score=float(summary["score"]),
        required_fill_rate=float(summary["required_fill_rate"]),
        exact_match_rate=float(summary["exact_match_rate"]),
        optional_fill_rate=float(summary["optional_fill_rate"]),
        error_count=int(summary["error_count"]),
        error_rate=float(summary["error_rate"]),
        runtime_s=float(summary["runtime_s"]),
        status=str(summary["status"]),
        report_path=report_path,
    )


def make_prompt(
    *,
    iteration: int,
    extractor_file: Path,
    baseline: EvalSummary,
    baseline_report_path: Path,
    dataset: Path,
    eval_spec_text: str,
    program_text: str,
) -> str:
    return textwrap.dedent(
        f"""
        You are a senior Python engineer improving CrawlerNest's extractor for AutoEval.

        Task:
        Modify ONLY this file:
        {extractor_file}

        Goal:
        Improve extractor robustness without breaking current passing cases.

        Current baseline metrics:
        - score = {baseline.score:.6f}
        - required_fill_rate = {baseline.required_fill_rate:.6f}
        - exact_match_rate = {baseline.exact_match_rate:.6f}
        - optional_fill_rate = {baseline.optional_fill_rate:.6f}
        - error_count = {baseline.error_count}
        - error_rate = {baseline.error_rate:.6f}
        - runtime_s = {baseline.runtime_s:.6f}
        - status = {baseline.status}

        Dataset:
        {dataset}

        Baseline report JSON:
        {baseline_report_path}

        Hard rules:
        1. Only modify extractor.py
        2. Do not modify dataset, eval runner, eval_spec.md, or program.md
        3. Keep extract() deterministic
        4. Never crash; always return a dict
        5. Preserve or improve current passing behavior
        6. Prefer simple, readable logic over clever complexity

        What to optimize for:
        - stronger parsing robustness
        - whitespace / casing tolerance
        - separator tolerance (:, -, |)
        - mild noise tolerance
        - quota parsing stability

        Suggested strategy:
        - strengthen fallback parsing
        - normalize keys safely
        - add conservative regex fallback
        - keep code short and readable

        Evaluation spec:
        {eval_spec_text}

        Program rules:
        {program_text}

        Output:
        Edit the file directly. Do not explain. Do not modify any other file.

        Iteration:
        {iteration}
        """
    ).strip() + "\n"


def build_modifier_command(
    template: str,
    *,
    extractor: Path,
    prompt_file: Path,
    project_root: Path,
    autoeval_root: Path,
    iteration: int,
    baseline_report: Path,
    candidate_report: Path,
) -> str:
    return template.format(
        extractor=str(extractor),
        prompt_file=str(prompt_file),
        project_root=str(project_root),
        autoeval_root=str(autoeval_root),
        iteration=iteration,
        baseline_report=str(baseline_report),
        candidate_report=str(candidate_report),
    )


def run_modifier(command: str, cwd: Path, log_path: Path, dry_run: bool) -> int:
    if dry_run:
        log_path.write_text(f"[dry-run]\n{command}\n", encoding="utf-8")
        print(f"[dry-run] modifier command:\n{command}")
        return 0

    completed = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
    )
    log_path.write_text(
        "\n".join(
            [
                f"$ {command}",
                "",
                "[stdout]",
                completed.stdout or "",
                "",
                "[stderr]",
                completed.stderr or "",
                "",
                f"[returncode] {completed.returncode}",
            ]
        ),
        encoding="utf-8",
    )
    return completed.returncode


# --- Manual mode function
def run_manual_step(prompt_file: Path, extractor_file: Path, baseline_report: Path) -> int:
    print("manual mode: no external modifier command will be run")
    print(f"prompt_file:          {prompt_file}")
    print(f"extractor_file:       {extractor_file}")
    print(f"baseline_report:      {baseline_report}")
    print("Edit extractor.py manually, save the file, then press Enter to continue.")
    try:
        input("Press Enter to run candidate evaluation...")
    except EOFError:
        print("No interactive input available; continuing immediately.")
    return 0


def maybe_open_manual_files(prompt_file: Path, extractor_file: Path, enabled: bool) -> None:
    if not enabled:
        return
    for target in (prompt_file, extractor_file):
        try:
            subprocess.run(["open", str(target)], check=False, capture_output=True, text=True)
        except Exception:
            pass


def print_candidate_diff(baseline: EvalSummary, candidate: EvalSummary) -> None:
    score_delta = candidate.score - baseline.score
    required_fill_delta = candidate.required_fill_rate - baseline.required_fill_rate
    exact_match_delta = candidate.exact_match_rate - baseline.exact_match_rate
    optional_fill_delta = candidate.optional_fill_rate - baseline.optional_fill_rate
    error_delta = candidate.error_count - baseline.error_count
    error_rate_delta = candidate.error_rate - baseline.error_rate
    runtime_delta = candidate.runtime_s - baseline.runtime_s

    print("[candidate vs baseline]")
    print(f"  score_delta:         {score_delta:+.6f}")
    print(f"  required_fill_delta: {required_fill_delta:+.6f}")
    print(f"  exact_match_delta:   {exact_match_delta:+.6f}")
    print(f"  optional_fill_delta: {optional_fill_delta:+.6f}")
    print(f"  error_count_delta:   {error_delta:+d}")
    print(f"  error_rate_delta:    {error_rate_delta:+.6f}")
    print(f"  runtime_delta_s:     {runtime_delta:+.6f}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_file(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def restore_file(src_backup: Path, dst: Path) -> None:
    shutil.copy2(src_backup, dst)


def ensure_loop_history(path: Path) -> None:
    if path.exists():
        return
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(
            [
                "iteration",
                "baseline_score",
                "candidate_score",
                "baseline_errors",
                "candidate_errors",
                "decision",
                "modifier_returncode",
                "prompt_file",
                "modifier_log",
                "baseline_report",
                "candidate_report",
                "notes",
            ]
        )


def append_loop_history(
    path: Path,
    *,
    iteration: int,
    baseline: EvalSummary,
    candidate: EvalSummary | None,
    decision: str,
    modifier_returncode: int,
    prompt_file: Path,
    modifier_log: Path,
    baseline_report: Path,
    candidate_report: Path | None,
    notes: str,
) -> None:
    ensure_loop_history(path)
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(
            [
                iteration,
                f"{baseline.score:.6f}",
                f"{candidate.score:.6f}" if candidate else "",
                baseline.error_count,
                candidate.error_count if candidate else "",
                decision,
                modifier_returncode,
                str(prompt_file),
                str(modifier_log),
                str(baseline_report),
                str(candidate_report) if candidate_report else "",
                notes,
            ]
        )


def should_keep(
    baseline: EvalSummary,
    candidate: EvalSummary,
    *,
    min_score_improvement: float,
    max_error_increase: int,
) -> tuple[bool, str]:
    score_gain = candidate.score - baseline.score
    error_delta = candidate.error_count - baseline.error_count

    if candidate.status == "crash":
        return False, "candidate crashed"
    if error_delta > max_error_increase:
        return False, f"error_count increased by {error_delta}"
    if score_gain < min_score_improvement:
        return False, f"score improvement {score_gain:.6f} below threshold {min_score_improvement:.6f}"
    return True, f"score improved by {score_gain:.6f}"


def print_summary(label: str, summary: EvalSummary) -> None:
    print(f"[{label}]")
    print(f"  score:               {summary.score:.6f}")
    print(f"  required_fill_rate:  {summary.required_fill_rate:.6f}")
    print(f"  exact_match_rate:    {summary.exact_match_rate:.6f}")
    print(f"  optional_fill_rate:  {summary.optional_fill_rate:.6f}")
    print(f"  error_count:         {summary.error_count}")
    print(f"  error_rate:          {summary.error_rate:.6f}")
    print(f"  runtime_s:           {summary.runtime_s:.6f}")
    print(f"  status:              {summary.status}")


def main() -> int:
    args = parse_args()
    autoeval_root = Path(__file__).resolve().parent.parent
    project_root = args.project_root.resolve() if args.project_root else discover_project_root(autoeval_root)
    extractor_file = args.extractor_file.resolve() if args.extractor_file else discover_extractor_file(project_root)
    eval_runner = args.eval_runner.resolve()
    dataset = args.dataset.resolve()
    eval_spec = args.eval_spec.resolve()
    program_md = args.program_md.resolve()
    work_dir = args.work_dir.resolve()

    ensure_dir(work_dir)
    prompts_dir = work_dir / "prompts"
    logs_dir = work_dir / "logs"
    reports_dir = work_dir / "reports"
    backups_dir = work_dir / "backups"
    ensure_dir(prompts_dir)
    ensure_dir(logs_dir)
    ensure_dir(reports_dir)
    ensure_dir(backups_dir)

    loop_history = work_dir / "loop_history.tsv"

    eval_spec_text = read_text(eval_spec)
    program_text = read_text(program_md)
    if not args.manual and not args.modifier_cmd:
        raise ValueError("Either provide --modifier-cmd or enable --manual.")

    baseline_report = reports_dir / "baseline_iter0.json"
    baseline = run_eval(
        args.python_bin,
        eval_runner,
        dataset,
        baseline_report,
        description=f"{args.description_prefix} baseline",
    )
    print_summary("baseline", baseline)

    current_best = baseline

    for iteration in range(1, args.iterations + 1):
        print(f"\n=== iteration {iteration} ===")

        backup_file = backups_dir / f"extractor_before_iter{iteration}.py"
        copy_file(extractor_file, backup_file)

        prompt_text = make_prompt(
            iteration=iteration,
            extractor_file=extractor_file,
            baseline=current_best,
            baseline_report_path=current_best.report_path,
            dataset=dataset,
            eval_spec_text=eval_spec_text,
            program_text=program_text,
        )
        prompt_file = prompts_dir / f"iter_{iteration:03d}.prompt.md"
        prompt_file.write_text(prompt_text, encoding="utf-8")

        candidate_report = reports_dir / f"candidate_iter{iteration:03d}.json"
        modifier_log = logs_dir / f"modifier_iter{iteration:03d}.log"
        modifier_cmd = None
        if args.modifier_cmd:
            modifier_cmd = build_modifier_command(
                args.modifier_cmd,
                extractor=extractor_file,
                prompt_file=prompt_file,
                project_root=project_root,
                autoeval_root=autoeval_root,
                iteration=iteration,
                baseline_report=current_best.report_path,
                candidate_report=candidate_report,
            )

        if args.manual:
            modifier_log.write_text("[manual-mode]\nUser edits extractor.py manually before candidate evaluation.\n", encoding="utf-8")
            maybe_open_manual_files(prompt_file, extractor_file, args.manual_open)
            returncode = run_manual_step(prompt_file, extractor_file, current_best.report_path)
        else:
            returncode = run_modifier(modifier_cmd, project_root, modifier_log, args.dry_run)

        if returncode != 0:
            restore_file(backup_file, extractor_file)
            append_loop_history(
                loop_history,
                iteration=iteration,
                baseline=current_best,
                candidate=None,
                decision="revert",
                modifier_returncode=returncode,
                prompt_file=prompt_file,
                modifier_log=modifier_log,
                baseline_report=current_best.report_path,
                candidate_report=None,
                notes="modifier command failed",
            )
            print("decision: revert (modifier command failed)")
            if args.stop_on_no_improvement:
                break
            continue

        try:
            candidate = run_eval(
                args.python_bin,
                eval_runner,
                dataset,
                candidate_report,
                description=f"{args.description_prefix} candidate {iteration}",
            )
        except Exception as exc:  # noqa: BLE001
            restore_file(backup_file, extractor_file)
            append_loop_history(
                loop_history,
                iteration=iteration,
                baseline=current_best,
                candidate=None,
                decision="revert",
                modifier_returncode=returncode,
                prompt_file=prompt_file,
                modifier_log=modifier_log,
                baseline_report=current_best.report_path,
                candidate_report=None,
                notes=f"candidate eval failed: {exc}",
            )
            print(f"decision: revert (candidate eval failed: {exc})")
            if args.stop_on_no_improvement:
                break
            continue

        print_summary("candidate", candidate)
        print_candidate_diff(current_best, candidate)
        keep, reason = should_keep(
            current_best,
            candidate,
            min_score_improvement=args.min_score_improvement,
            max_error_increase=args.max_error_increase,
        )

        if keep:
            decision = "keep"
            current_best = candidate
            notes = reason
            print(f"decision: keep ({reason})")
        else:
            decision = "revert"
            restore_file(backup_file, extractor_file)
            notes = reason
            print(f"decision: revert ({reason})")

        append_loop_history(
            loop_history,
            iteration=iteration,
            baseline=baseline if iteration == 1 else load_latest_baseline_summary(work_dir, current_best),
            candidate=candidate,
            decision=decision,
            modifier_returncode=returncode,
            prompt_file=prompt_file,
            modifier_log=modifier_log,
            baseline_report=current_best.report_path if decision == "keep" else baseline_report_for_iteration(work_dir, iteration, current_best),
            candidate_report=candidate_report,
            notes=notes,
        )

        if decision != "keep" and args.stop_on_no_improvement:
            break

    print("\n=== final best ===")
    print_summary("best", current_best)
    print(f"loop_history:         {loop_history}")
    print(f"work_dir:             {work_dir}")
    return 0


def load_latest_baseline_summary(work_dir: Path, current_best: EvalSummary) -> EvalSummary:
    # Simple pass-through helper kept for readable append_loop_history call.
    return current_best


def baseline_report_for_iteration(work_dir: Path, iteration: int, current_best: EvalSummary) -> Path:
    # Simple pass-through helper kept for readable append_loop_history call.
    return current_best.report_path


if __name__ == "__main__":
    raise SystemExit(main())