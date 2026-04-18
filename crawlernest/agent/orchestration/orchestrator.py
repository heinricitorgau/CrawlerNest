from __future__ import annotations

import re
import time

from crawlernest.agent.orchestration.handoff_types import DevHandoff, RoutingDecision
from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.shared.models.task_response import TaskResponse
from crawlernest.agent.shared.validation.request_validator import RequestValidator
from crawlernest.agent.web_agent.interpretation.query_rewriter import QueryRewriter
from crawlernest.agent.web_agent.interpretation.referential_resolver import ReferentialResolver
from crawlernest.agent.web_agent.memory.conversation_store import ConversationStore


class Orchestrator:
    def __init__(
        self,
        *,
        web_engine,
        dev_engine,
        validator: RequestValidator | None = None,
        memory_store: ConversationStore | None = None,
        referential_resolver: ReferentialResolver | None = None,
        query_rewriter: QueryRewriter | None = None,
    ) -> None:
        self._web_engine = web_engine
        self._dev_engine = dev_engine
        self._validator = validator or RequestValidator()
        self._memory = memory_store or ConversationStore()
        self._resolver = referential_resolver or ReferentialResolver()
        self._rewriter = query_rewriter or QueryRewriter()

    def run(self, request: TaskRequest, decision: RoutingDecision) -> TaskResponse:
        if not request.user_input.strip():
            raise ValueError("user_input must not be empty")

        if decision.route == "web":
            self._validator.validate(request)
            response = self._web_engine.execute(request)
            return self._attach_orchestration_debug(
                response=response,
                debug=bool(request.constraints.get("debug")),
                payload={
                    "route": decision.route,
                    "reason": decision.reason,
                    "signals": {
                        "is_dev_intent": decision.signals.is_dev_intent,
                        "has_code_keywords": decision.signals.has_code_keywords,
                        "explicit_dev_kind": decision.signals.explicit_dev_kind,
                    },
                    "dev_call": {
                        "invoked": False,
                        "latency_ms": None,
                        "returned": {"has_patch": False},
                    },
                },
            )

        if decision.route == "dev":
            self._validator.validate(request)
            response = self._dev_engine.execute(request)
            return self._attach_orchestration_debug(
                response=response,
                debug=bool(request.constraints.get("debug")),
                payload={
                    "route": decision.route,
                    "reason": decision.reason,
                    "signals": {
                        "is_dev_intent": decision.signals.is_dev_intent,
                        "has_code_keywords": decision.signals.has_code_keywords,
                        "explicit_dev_kind": decision.signals.explicit_dev_kind,
                    },
                    "dev_call": {
                        "invoked": True,
                        "latency_ms": 0,
                        "returned": {
                            "has_patch": bool(isinstance(response.data, dict) and response.data.get("filePatch")),
                        },
                    },
                },
            )

        handoff = self._build_dev_handoff(request)
        dev_request = TaskRequest(
            task_id=f"{request.task_id}:dev",
            mode="dev",
            kind="dev_refinement",
            user_input=handoff.interpreted_task,
            context=handoff.context,
            constraints=request.constraints,
            source="system",
            session_id=request.session_id,
        )
        self._validator.validate(dev_request)

        started = time.perf_counter()
        dev_response = self._dev_engine.execute(dev_request)
        latency_ms = int((time.perf_counter() - started) * 1000)

        response = self._web_engine.format_dev_handoff_result(
            request=request,
            dev_response=dev_response,
            handoff={
                "original_user_input": handoff.original_user_input,
                "interpreted_task": handoff.interpreted_task,
                "context": handoff.context,
            },
        )
        return self._attach_orchestration_debug(
            response=response,
            debug=bool(request.constraints.get("debug")),
            payload={
                "route": decision.route,
                "reason": decision.reason,
                "signals": {
                    "is_dev_intent": decision.signals.is_dev_intent,
                    "has_code_keywords": decision.signals.has_code_keywords,
                    "explicit_dev_kind": decision.signals.explicit_dev_kind,
                },
                "dev_call": {
                    "invoked": True,
                    "latency_ms": latency_ms,
                    "returned": {
                        "has_patch": bool(isinstance(dev_response.data, dict) and dev_response.data.get("filePatch")),
                    },
                },
            },
        )

    def _build_dev_handoff(self, request: TaskRequest) -> DevHandoff:
        history = self._memory.get_history(request.session_id) if request.session_id else []
        resolved_reference = self._resolver.resolve(
            current_input=request.user_input,
            task_kind=request.kind,
            history=history,
        )
        rewritten = self._rewriter.rewrite(
            original_input=request.user_input,
            resolved_reference=resolved_reference,
            task_kind=request.kind,
        )
        effective_input = (
            rewritten.rewritten_query
            if rewritten.rewrite_applied and rewritten.rewritten_query
            else request.user_input
        )
        interpreted_task = self._interpret_task(effective_input)
        handoff_context = {
            **request.context,
            "original_user_input": request.user_input,
            "target": self._extract_target(effective_input),
            "hints": self._extract_hints(effective_input),
            "rewritten_query": rewritten.rewritten_query,
            "resolved_reference": {
                "detected": resolved_reference.detected,
                "input_type": resolved_reference.input_type,
                "resolved_entities": list(resolved_reference.resolved_entities),
                "confidence": resolved_reference.confidence,
                "reason": resolved_reference.reason,
            },
        }
        return DevHandoff(
            original_user_input=request.user_input,
            interpreted_task=interpreted_task,
            context=handoff_context,
        )

    def _interpret_task(self, user_input: str) -> str:
        normalized = user_input.strip()
        lowered = normalized.lower()
        if "extractor" in lowered or "抽取器" in normalized:
            if any(token in lowered for token in ("bug", "error", "fix", "failure")) or any(
                token in normalized for token in ("修", "壞", "錯")
            ):
                return "fix extractor failure handling"
            return "improve extractor robustness"
        if "parser" in lowered or "解析器" in normalized:
            if any(token in lowered for token in ("bug", "error", "fix", "failure")) or any(
                token in normalized for token in ("修", "壞", "錯")
            ):
                return "fix parser failure handling"
            return "improve parser robustness"
        symbol_match = re.search(r"[_A-Za-z][_A-Za-z0-9]+", normalized)
        if symbol_match and any(token in lowered for token in ("improve", "fix", "refactor")):
            return f"improve {symbol_match.group(0)}"
        return normalized

    def _extract_target(self, user_input: str) -> str | None:
        lowered = user_input.lower()
        if "extractor" in lowered or "抽取器" in user_input:
            return "extractor"
        if "parser" in lowered or "解析器" in user_input:
            return "parser"
        if "ranking" in lowered:
            return "ranking"
        symbol_match = re.search(r"\b[_A-Za-z][_A-Za-z0-9]+\b", user_input)
        if symbol_match:
            return symbol_match.group(0)
        return None

    def _extract_hints(self, user_input: str) -> list[str]:
        lowered = user_input.lower()
        hints: list[str] = []
        if any(token in lowered for token in ("fix", "bug", "error", "failure")) or any(
            token in user_input for token in ("修", "錯", "壞")
        ):
            hints.append("bug_fix")
        if "refactor" in lowered or "重構" in user_input:
            hints.append("refactor")
        if "improve" in lowered or "改善" in user_input:
            hints.append("improve")
        if "function" in lowered or "函式" in user_input or "函數" in user_input:
            hints.append("function_scope")
        symbol_match = re.search(r"\b[_A-Za-z][_A-Za-z0-9]+\b", user_input)
        if symbol_match:
            hints.append(f"symbol:{symbol_match.group(0)}")
        return hints

    def _attach_orchestration_debug(
        self,
        *,
        response: TaskResponse,
        debug: bool,
        payload: dict[str, object],
    ) -> TaskResponse:
        if not debug:
            return response
        data = dict(response.data) if isinstance(response.data, dict) else {}
        data["orchestrationDebug"] = payload
        return TaskResponse(
            task_id=response.task_id,
            status=response.status,
            message=response.message,
            data=data,
            traces=response.traces,
            warnings=response.warnings,
        )
