from __future__ import annotations

from crawlernest.agent.dev_agent.engine.dev_agent_engine import DevAgentEngine
from crawlernest.agent.orchestration.orchestrator import Orchestrator
from crawlernest.agent.orchestration.routing_policy import RoutingPolicy
from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.shared.models.task_response import TaskResponse
from crawlernest.agent.shared.validation.request_validator import RequestValidator
from crawlernest.agent.web_agent.engine.web_agent_engine import WebAgentEngine


class AgentService:
    def __init__(self) -> None:
        self._validator = RequestValidator()
        self._web_engine = WebAgentEngine()
        self._dev_engine = DevAgentEngine()
        self._routing_policy = RoutingPolicy()
        self._orchestrator = Orchestrator(
            web_engine=self._web_engine,
            dev_engine=self._dev_engine,
            validator=self._validator,
        )

    def run(self, request: TaskRequest) -> TaskResponse:
        try:
            decision = self._routing_policy.decide(request)
            return self._orchestrator.run(request, decision)
        except Exception as exc:
            if request.source == "web":
                return self._web_engine.format_failure(
                    request,
                    str(exc),
                )
            return TaskResponse(
                task_id=request.task_id,
                status="error",
                message=str(exc),
                data={},
            )
