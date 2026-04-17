from __future__ import annotations

import argparse
import json
import uuid

from crawlernest.agent.models.task_request import TaskRequest
from crawlernest.agent.services.agent_service import AgentService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CrawlerNest agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-task", help="Run an agent task")
    run_parser.add_argument("--mode", choices=["dev", "web"], required=True)
    run_parser.add_argument(
        "--kind",
        choices=[
            "dev_refinement",
            "data_query",
            "recommendation",
            "ranking_explain",
            "university_lookup",
        ],
        required=True,
    )
    run_parser.add_argument("--input", required=True, dest="user_input")
    run_parser.add_argument("--context-json", default="{}", dest="context_json")
    run_parser.add_argument("--constraints-json", default="{}", dest="constraints_json")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    service = AgentService()
    request = TaskRequest(
        task_id=str(uuid.uuid4()),
        mode=args.mode,
        kind=args.kind,
        user_input=args.user_input,
        context=json.loads(args.context_json),
        constraints=json.loads(args.constraints_json),
        source="cli",
    )
    response = service.run(request)
    print(
        json.dumps(
            {
                "task_id": response.task_id,
                "status": response.status,
                "message": response.message,
                "data": response.data,
                "traces": response.traces,
                "warnings": response.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
