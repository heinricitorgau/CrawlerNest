"""
interfaces/cli/run_agent.py
===========================

Dev agent CLI entry point (new interfaces/ layer).

Usage
-----
    python interfaces/cli/run_agent.py --task "fix extractor"
    python interfaces/cli/run_agent.py --task "recommend UK universities" --mode web
    python interfaces/cli/run_agent.py --task "fix parser" --mode dev --threshold 0.9
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.contracts import TaskRequest
from agent.service import AgentService
from runtime.config import get_config


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crawlernest-agent",
        description="CrawlerNest agent CLI — dev and web modes.",
    )
    p.add_argument("--task", required=True, help="Task prompt for the agent.")
    p.add_argument(
        "--mode",
        choices=["dev", "web", "auto"],
        default="auto",
        help='Task mode. "dev" for code tasks, "web" for user-facing tasks, '
             '"auto" to let the agent infer (default: auto).',
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Score threshold for pass/fail (overrides config default).",
    )
    p.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output the full response as JSON.",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    cfg = get_config()

    threshold = args.threshold or (
        cfg.agent_dev_threshold if args.mode == "dev" else cfg.agent_threshold
    )

    service = AgentService(threshold=threshold, mode=args.mode)
    request = TaskRequest(prompt=args.task, task_type=args.mode)
    response = service.run(request)

    if args.output_json:
        print(json.dumps(response.to_dict(), indent=2))
        return

    # --- human-readable output ---
    print(f"\n{'='*50}")
    print(f"  Task    : {response.task}")
    print(f"  Mode    : {response.mode}")
    print(f"  Score   : {response.score:.2f}  {'✓ passed' if response.passed else '✗ failed'}")
    print(f"  Iters   : {response.iterations}")
    print(f"{'='*50}\n")
    print(response.result)

    if response.feedback:
        print("\nEvaluator feedback:")
        for line in response.feedback:
            print(f"  · {line}")

    if response.error:
        print(f"\n[ERROR] {response.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
