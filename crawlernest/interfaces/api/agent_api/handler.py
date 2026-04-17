from __future__ import annotations

import uuid
from typing import Any

from crawlernest.agent.models.task_request import TaskRequest
from crawlernest.agent.services.agent_service import AgentService

from .dto import AgentTaskPayload


class AgentApiHandler:
    def __init__(self, service: AgentService | None = None) -> None:
        self._service = service or AgentService()

    def handle_task(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        task_payload = AgentTaskPayload.from_dict(payload)

        request = TaskRequest(
            task_id=str(uuid.uuid4()),
            mode=task_payload.mode,  # type: ignore[arg-type]
            kind=task_payload.kind,  # type: ignore[arg-type]
            user_input=task_payload.user_input,
            context=task_payload.context,
            constraints=task_payload.constraints,
            source=task_payload.source,  # type: ignore[arg-type]
            session_id=task_payload.session_id,
        )

        response = self._service.run(request)
        status_code = self._status_code_for_response(response.status)
        success = response.status == "success"

        return status_code, {
            "success": success,
            "data": {
                "taskId": response.task_id,
                "status": response.status,
                "message": response.message,
                "data": response.data,
                "traces": response.traces,
                "warnings": response.warnings,
            },
        }

    def _status_code_for_response(self, status: str) -> int:
        if status == "success":
            return 200
        if status == "rejected":
            return 400
        if status == "partial":
            return 206
        return 500
