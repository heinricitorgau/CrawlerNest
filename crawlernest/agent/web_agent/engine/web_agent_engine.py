from __future__ import annotations

import dataclasses

from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.shared.models.task_response import TaskResponse
from crawlernest.agent.shared.planner.shared_planner import SharedPlanner
from crawlernest.agent.web_agent.formatter.response_formatter import WebResponseFormatter
from crawlernest.agent.web_agent.generation.context_builder import WebContextBuilder
from crawlernest.agent.web_agent.generation.prompt_builder import WebPromptBuilder
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator
from crawlernest.agent.web_agent.memory.conversation_store import ConversationStore
from crawlernest.agent.web_agent.memory.memory_policy import MemoryPolicy
from crawlernest.agent.web_agent.policy.web_agent_policy import WebAgentPolicy
from crawlernest.agent.web_agent.tool_router.web_tool_router import WebToolRouter

# Internal sentinel key used to pass the memory debug payload from
# _apply_generation() to _respond() without exposing it to the formatter.
# Must not collide with any real data field name.
_MEMORY_DEBUG_KEY = "__memory_debug__"


class WebAgentEngine:
    def __init__(
        self,
        planner: SharedPlanner | None = None,
        tool_router: WebToolRouter | None = None,
        policy: WebAgentPolicy | None = None,
        formatter: WebResponseFormatter | None = None,
        context_builder: WebContextBuilder | None = None,
        prompt_builder: WebPromptBuilder | None = None,
        generator: WebResponseGenerator | None = None,
        memory_store: ConversationStore | None = None,
        memory_policy: MemoryPolicy | None = None,
    ) -> None:
        self._planner = planner or SharedPlanner()
        self._tools = tool_router or WebToolRouter()
        self._policy = policy or WebAgentPolicy()
        self._formatter = formatter or WebResponseFormatter()
        self._context_builder = context_builder or WebContextBuilder()
        self._prompt_builder = prompt_builder or WebPromptBuilder()
        self._generator = generator or WebResponseGenerator()
        self._memory = memory_store or ConversationStore()
        self._memory_policy = memory_policy or MemoryPolicy()

    def execute(self, request: TaskRequest) -> TaskResponse:
        plan = self._planner.build_plan(request)
        try:
            if request.kind == "university_lookup":
                raw = TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    message="University detail preview loaded.",
                    data=self._tools.university_tools.get_detail_preview(
                        request.context,
                        user_input=request.user_input,
                    ),
                    traces=plan,
                )
                return self._respond(request=request, response=raw)

            if request.kind == "data_query":
                raw = TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    message="Rankings query completed.",
                    data=self._tools.ranking_tools.list_rankings(
                        request.context,
                        user_input=request.user_input,
                    ),
                    traces=plan,
                )
                return self._respond(request=request, response=raw)

            if request.kind == "ranking_explain":
                raw = TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    message="Ranking explanation prepared.",
                    data=self._tools.ranking_tools.explain_rankings(
                        request.context,
                        user_input=request.user_input,
                    ),
                    traces=plan,
                )
                return self._respond(request=request, response=raw)

            if request.kind == "recommendation":
                raw = TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    message="Recommendation task completed.",
                    data=self._tools.recommendation_tools.recommend(
                        request.context,
                        user_input=request.user_input,
                    ),
                    traces=plan,
                )
                return self._respond(request=request, response=raw)

            raw = TaskResponse(
                task_id=request.task_id,
                status="rejected",
                message=f"Unsupported web task kind: {request.kind}",
                traces=plan,
            )
            return self._respond(request=request, response=raw)
        except Exception as exc:
            raw = TaskResponse(
                task_id=request.task_id,
                status="error",
                message=str(exc),
                traces=plan,
            )
            return self._respond(request=request, response=raw)

    def format_failure(
        self,
        request: TaskRequest,
        message: str,
        *,
        status: str = "error",
    ) -> TaskResponse:
        raw = TaskResponse(
            task_id=request.task_id,
            status=status,  # type: ignore[arg-type]
            message=message,
        )
        return self._respond(request=request, response=raw)

    def _respond(
        self,
        *,
        request: TaskRequest,
        response: TaskResponse,
    ) -> TaskResponse:
        response = self._apply_generation(request=request, response=response)

        # Lift the memory debug payload out BEFORE passing response to the
        # formatter.  Each formatter method builds a completely new dict and
        # will silently discard any field it does not recognise.  We pull the
        # payload out here and reattach it to the formatter's output afterwards,
        # so that memory debug data reaches the caller without touching the
        # formatter contract at all.
        memory_debug_payload: dict | None = None
        if isinstance(response.data, dict) and _MEMORY_DEBUG_KEY in response.data:
            # Pop from a copy so we don't mutate the dataclass field in place.
            clean_data = {k: v for k, v in response.data.items() if k != _MEMORY_DEBUG_KEY}
            memory_debug_payload = response.data[_MEMORY_DEBUG_KEY]
            response = TaskResponse(
                task_id=response.task_id,
                status=response.status,
                message=response.message,
                data=clean_data,
                traces=response.traces,
                warnings=response.warnings,
            )

        expose_traces = bool(request.constraints.get("debug")) or self._policy.expose_traces
        if response.status in {"error", "rejected"}:
            formatted = self._formatter.format_error(response)
        elif request.kind == "recommendation":
            formatted = self._formatter.format_recommendation(response)
        elif request.kind in {"data_query", "ranking_explain", "university_lookup"}:
            formatted = self._formatter.format_query(response)
        else:
            formatted = self._formatter.format_generic(response)

        # Reattach memory debug to the formatted output under the public key.
        # This is only present when debug=true was set in request.constraints.
        if memory_debug_payload is not None and isinstance(formatted, dict):
            formatted["memoryDebug"] = memory_debug_payload

        return TaskResponse(
            task_id=response.task_id,
            status=response.status,
            message=response.message,
            data=formatted,
            traces=response.traces if expose_traces else [],
            warnings=response.warnings,
        )

    def _apply_generation(
        self,
        *,
        request: TaskRequest,
        response: TaskResponse,
    ) -> TaskResponse:
        if response.status != "success":
            return response
        if not self._policy.allow_generation or self._policy.generation_mode == "disabled":
            return response
        if not isinstance(response.data, dict):
            return response

        # --- Memory: load prior conversation history for this session ---
        session_id: str | None = getattr(request, "session_id", None)
        raw_history = self._memory.get_history(session_id) if session_id else []
        debug_mode = bool(request.constraints.get("debug"))

        if debug_mode:
            selected_turns, memory_debug_report = self._memory_policy.select_turns_debug(
                raw_history,
                current_input=request.user_input,
                current_task_kind=request.kind,
            )
        else:
            selected_turns = self._memory_policy.select_turns(
                raw_history,
                current_input=request.user_input,
                current_task_kind=request.kind,
            )
            memory_debug_report = None

        # --- Store the user's current input BEFORE generation ---
        if session_id:
            self._memory.append_user(
                session_id,
                content=request.user_input,
                task_kind=request.kind,
            )

        retrieved = self._context_builder.build(
            task_kind=request.kind,
            user_input=request.user_input,
            raw_data=response.data,
            request_context=request.context,
        )
        prompt = self._prompt_builder.build(
            user_input=request.user_input,
            retrieved=retrieved,
            policy=self._policy,
            conversation_history=selected_turns if selected_turns else None,
        )
        fallback_text = self._resolve_fallback_text(response)
        generation = self._generator.generate_response(
            prompt=prompt,
            fallback_text=fallback_text,
        )

        # --- Memory: persist the assistant's reply ---
        if session_id and generation.reply_text:
            self._memory.append_assistant(
                session_id,
                content=generation.reply_text,
                task_kind=request.kind,
            )

        next_data = dict(response.data)
        next_data["assistantReply"] = generation.reply_text
        next_data["assistantReplyParagraphs"] = generation.paragraphs
        next_data["generationSource"] = generation.source
        next_data["sessionId"] = session_id  # echo back so frontend can persist it
        if generation.model_name:
            next_data["modelName"] = generation.model_name
        if generation.warning:
            response.warnings.append(generation.warning)

        # Stash memory debug report under a sentinel key so _respond() can lift
        # it out before the formatter runs (the formatter builds a fresh dict
        # and would silently discard any unrecognised fields).
        if memory_debug_report is not None:
            next_data[_MEMORY_DEBUG_KEY] = dataclasses.asdict(memory_debug_report)

        return TaskResponse(
            task_id=response.task_id,
            status=response.status,
            message=response.message,
            data=next_data,
            traces=response.traces,
            warnings=response.warnings,
        )

    def _resolve_fallback_text(self, response: TaskResponse) -> str:
        data = response.data
        fallback = data.get("assistantReply") or data.get("summary") or response.message
        if isinstance(fallback, str):
            return fallback
        return response.message
