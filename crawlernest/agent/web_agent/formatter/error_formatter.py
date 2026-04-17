from __future__ import annotations

from crawlernest.agent.shared.models.task_response import TaskResponse


class ErrorFormatter:
    def format_error(self, response: TaskResponse) -> dict:
        return {
            "type": "error",
            "title": "Agent Error",
            "explanation": response.message,
            "items": [],
            "meta": {
                "status": response.status,
                "warningCount": len(response.warnings),
            },
        }
