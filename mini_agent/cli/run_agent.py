from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from engine import Agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Mini Agent CLI.")
    parser.add_argument("--task", required=True, help="Task for the agent to run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = Agent()

    print("[Agent] Generating...")
    print("[Agent] Evaluating...")
    result = agent.run(args.task)

    if result["refined"]:
        print(f"Score: {result['initial_score']}")
        print("[Agent] Refining...")
    else:
        print(f"Score: {result['score']}")

    print(f"Final Result: {result['result']}")


if __name__ == "__main__":
    main()
