from __future__ import annotations

from crawlernest.agent.dev_agent.engine.dev_agent_engine import DevAgentEngine
from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.shared.models.task_response import TaskResponse
from crawlernest.agent.web_agent.engine.web_agent_engine import WebAgentEngine


class AgentRunner:
    def __init__(self) -> None:
        self._web_engine = WebAgentEngine()
        self._dev_engine = DevAgentEngine()

    def execute(self, request: TaskRequest) -> TaskResponse:
        if request.source == "web":
            return self._web_engine.execute(request)
        return self._dev_engine.execute(request)
