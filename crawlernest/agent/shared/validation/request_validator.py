from __future__ import annotations

from crawlernest.agent.dev_agent.policy.dev_agent_policy import DevAgentPolicy
from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.web_agent.policy.web_agent_policy import WebAgentPolicy


class RequestValidator:
    def validate(self, request: TaskRequest) -> None:
        if not request.user_input.strip():
            raise ValueError("user_input must not be empty")

        policy = WebAgentPolicy() if request.source == "web" else DevAgentPolicy()
        if request.kind not in policy.allowed_task_kinds:
            raise ValueError(
                f"task kind '{request.kind}' is not allowed for source '{request.source}'"
            )
