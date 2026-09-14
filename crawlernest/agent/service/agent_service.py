from __future__ import annotations

from crawlernest.agent.dev_agent.engine.dev_agent_engine import DevAgentEngine
from crawlernest.agent.memory_long_term.memory_retriever import LongTermMemoryRetriever
from crawlernest.agent.memory_long_term.memory_writer import LongTermMemoryWriter
from crawlernest.agent.orchestration.orchestrator import Orchestrator
from crawlernest.agent.orchestration.routing_policy import RoutingPolicy
from crawlernest.agent.persistence import factory as stores
from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.shared.models.task_response import TaskResponse
from crawlernest.agent.shared.validation.request_validator import RequestValidator
from crawlernest.agent.web_agent.engine.web_agent_engine import WebAgentEngine


class AgentService:
    def __init__(self) -> None:
        self._validator = RequestValidator()
        # One conversation store and one long-term memory store per service.
        # Each component used to build its own: the orchestrator resolved
        # follow-ups against a history nothing ever wrote to, and the memory
        # retriever loaded the JSON file once at start-up, so it never saw what
        # the writer beside it stored until the process restarted.
        conversations = stores.conversation_store()
        long_term_memory = stores.long_term_memory_store()
        self._web_engine = WebAgentEngine(
            memory_store=conversations,
            long_term_memory_retriever=LongTermMemoryRetriever(long_term_memory),
            long_term_memory_writer=LongTermMemoryWriter(long_term_memory),
        )
        self._dev_engine = DevAgentEngine()
        self._routing_policy = RoutingPolicy()
        self._orchestrator = Orchestrator(
            web_engine=self._web_engine,
            dev_engine=self._dev_engine,
            validator=self._validator,
            memory_store=conversations,
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
