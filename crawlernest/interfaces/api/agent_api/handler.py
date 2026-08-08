from __future__ import annotations

import uuid
from typing import Any

from crawlernest.agent.models.task_request import TaskRequest
from crawlernest.agent.services.agent_service import AgentService

from .dto import AgentExplainPayload, AgentTaskPayload


class AgentApiHandler:
    def __init__(self, service: AgentService | None = None) -> None:
        self._service = service or AgentService()

    def handle_explain(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Explain results the caller already holds.

        Unlike :meth:`handle_task`, this never touches the warehouse and never
        recomputes anything: the caller supplies the rows it is displaying and
        gets prose about exactly those rows. That keeps the explanation from
        describing a different result set than the user sees, and keeps the
        model out of the read path entirely.

        The response always carries ``source``: ``"llm"`` when the model wrote
        the text, ``"fallback"`` when the deterministic reply was used, so the
        caller can label it honestly.
        """
        from crawlernest.agent.web_agent.generation.data_query_explainer import (
            DataQueryExplainer,
        )
        from crawlernest.agent.web_agent.generation.ranking_explainer import RankingExplainer
        from crawlernest.agent.web_agent.generation.recommendation_explainer import (
            RecommendationExplainer,
        )
        from crawlernest.agent.web_agent.generation.university_lookup_explainer import (
            UniversityLookupExplainer,
        )

        request = AgentExplainPayload.from_dict(payload)

        if not request.items and request.task_kind != "university_lookup":
            return 400, {"success": False, "error": "items must be a non-empty list"}

        try:
            if request.task_kind == "ranking_explain":
                result = RankingExplainer().explain(
                    items=request.items,
                    focus_entity=str(request.profile.get("focusEntity", "")),
                    query=request.query,
                    caveats=request.caveats,
                    deterministic_reply=request.deterministic_reply,
                )
            elif request.task_kind == "university_lookup":
                result = UniversityLookupExplainer().explain(
                    preview=request.profile,
                    query=request.query,
                    caveats=request.caveats,
                    deterministic_reply=request.deterministic_reply,
                )
            elif request.task_kind == "data_query":
                result = DataQueryExplainer().explain(
                    items=request.items,
                    metadata=request.profile or None,
                    query=request.query,
                    caveats=request.caveats,
                    deterministic_reply=request.deterministic_reply,
                )
            else:
                result = RecommendationExplainer().explain(
                    items=request.items,
                    profile=request.profile or None,
                    query=request.query,
                    caveats=request.caveats,
                    deterministic_reply=request.deterministic_reply,
                )
        except Exception as exc:  # never let a generation problem 500 the UI
            return 200, {
                "success": True,
                "data": {
                    "taskKind": request.task_kind,
                    "explanation": request.deterministic_reply,
                    "paragraphs": [request.deterministic_reply] if request.deterministic_reply else [],
                    "source": "fallback",
                    "modelName": None,
                    "warning": f"Explanation unavailable: {exc}",
                },
            }

        return 200, {
            "success": True,
            "data": {
                "taskKind": request.task_kind,
                "explanation": result.text,
                "paragraphs": result.paragraphs,
                "source": result.source,
                "modelName": result.model_name,
                "warning": result.warning,
            },
        }

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
