from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.memory import Memory
from agent.runner import run_task


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the minimal CrawlerNest agent engine.")
    parser.add_argument("--task", required=True, help="Task prompt for the agent.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Score threshold before refinement is triggered.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    memory = Memory()
    memory.add("system", "CrawlerNest dev-agent session started.")

    result = run_task(
        task_input=args.task,
        memory=memory,
        threshold=args.threshold,
        logger=print,
    )

    print("\n=== Final Result ===")
    print(result.output)
    print(f"\nEvaluation score: {result.score:.2f}")
    print(f"Passed threshold: {result.passed}")
    print(f"Iterations: {result.iterations}")

    if result.tool_outputs:
        print("\nTool outputs:")
        print(json.dumps(result.tool_outputs, indent=2))

    if result.feedback:
        print("\nEvaluator feedback:")
        for item in result.feedback:
            print(f"- {item}")


if __name__ == "__main__":
    main()

