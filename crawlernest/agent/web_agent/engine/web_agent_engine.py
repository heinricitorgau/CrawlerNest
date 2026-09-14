from __future__ import annotations

import dataclasses

from crawlernest.agent.memory_long_term.memory_retriever import LongTermMemoryRetriever
from crawlernest.agent.memory_long_term.memory_writer import LongTermMemoryWriter
from crawlernest.agent.persistence.factory import conversation_store as build_conversation_store
from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.shared.models.task_response import TaskResponse
from crawlernest.agent.shared.planner.shared_planner import SharedPlanner
from crawlernest.agent.web_agent.formatter.response_formatter import WebResponseFormatter
from crawlernest.agent.web_agent.generation.context_builder import WebContextBuilder
from crawlernest.agent.web_agent.generation.data_query_explainer import DataQueryExplainer
from crawlernest.agent.web_agent.generation.prompt_builder import WebPromptBuilder
from crawlernest.agent.web_agent.generation.ranking_explainer import RankingExplainer
from crawlernest.agent.web_agent.generation.recommendation_explainer import (
    RecommendationExplainer,
)
from crawlernest.agent.web_agent.generation.university_lookup_explainer import (
    UniversityLookupExplainer,
)
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator
from crawlernest.agent.web_agent.grounding.grounding_analyzer import GroundingAnalyzer
from crawlernest.agent.web_agent.interpretation.query_rewriter import QueryRewriter
from crawlernest.agent.web_agent.interpretation.referential_resolver import ReferentialResolver
from crawlernest.agent.web_agent.memory.conversation_store import ConversationStore
from crawlernest.agent.web_agent.memory.memory_policy import MemoryPolicy
from crawlernest.agent.web_agent.policy.generation_policy import GenerationPolicy
from crawlernest.agent.web_agent.policy.unsupported_year import unsupported_year_warnings
from crawlernest.agent.web_agent.policy.web_agent_policy import WebAgentPolicy
from crawlernest.agent.web_agent.tool_router.web_tool_router import WebToolRouter

# Internal sentinel key used to pass the memory debug payload from
# _apply_generation() to _respond() without exposing it to the formatter.
# Must not collide with any real data field name.
_MEMORY_DEBUG_KEY = "__memory_debug__"
_REFERENCE_DEBUG_KEY = "__reference_debug__"
_GROUNDING_DEBUG_KEY = "__grounding_debug__"
_POLICY_DEBUG_KEY = "__policy_debug__"
_ORCHESTRATION_DEBUG_KEY = "__orchestration_debug__"
_LONG_TERM_MEMORY_DEBUG_KEY = "__long_term_memory_debug__"

# The web engine has no self-improvement or meta-strategy loop. It used to
# score every reply, generate "prompt patches" and "behavior hints" from recent
# scores, persist them to unversioned JSON under /tmp, and append the active
# ones to the next prompt on the generic generation path. A prompt that
# rewrites itself between requests cannot be reviewed or reproduced, and every
# honesty rule in the prompt could be diluted by an instruction nobody wrote.
# The dev agent keeps its own loop; it never feeds a web prompt.


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
        referential_resolver: ReferentialResolver | None = None,
        query_rewriter: QueryRewriter | None = None,
        grounding_analyzer: GroundingAnalyzer | None = None,
        generation_policy: GenerationPolicy | None = None,
        long_term_memory_retriever: LongTermMemoryRetriever | None = None,
        long_term_memory_writer: LongTermMemoryWriter | None = None,
    ) -> None:
        self._planner = planner or SharedPlanner()
        self._tools = tool_router or WebToolRouter()
        self._policy = policy or WebAgentPolicy()
        self._formatter = formatter or WebResponseFormatter()
        self._context_builder = context_builder or WebContextBuilder()
        self._prompt_builder = prompt_builder or WebPromptBuilder()
        self._generator = generator or WebResponseGenerator()
        # Recommendation explanations use a dedicated grounded/honest prompt but
        # share the same provider (ds4 or whatever is configured) as generic
        # generation, so a single config drives both.
        self._recommendation_explainer = RecommendationExplainer(generator=self._generator)
        self._ranking_explainer = RankingExplainer(generator=self._generator)
        self._university_lookup_explainer = UniversityLookupExplainer(generator=self._generator)
        self._data_query_explainer = DataQueryExplainer(generator=self._generator)
        self._memory = memory_store or build_conversation_store()
        self._memory_policy = memory_policy or MemoryPolicy()
        self._referential_resolver = referential_resolver or ReferentialResolver()
        self._query_rewriter = query_rewriter or QueryRewriter()
        self._grounding_analyzer = grounding_analyzer or GroundingAnalyzer()
        self._generation_policy = generation_policy or GenerationPolicy()
        self._long_term_retriever = long_term_memory_retriever or LongTermMemoryRetriever()
        self._long_term_writer = long_term_memory_writer or LongTermMemoryWriter()

    def execute(self, request: TaskRequest) -> TaskResponse:
        plan = self._planner.build_plan(request)
        raw_history = self._memory.get_history(request.session_id) if request.session_id else []
        reference_debug = self._build_reference_debug(request=request, history=raw_history)
        effective_input = (
            reference_debug.get("rewritten_query")
            if reference_debug.get("rewrite_applied") and reference_debug.get("rewritten_query")
            else request.user_input
        )
        try:
            if request.kind == "university_lookup":
                raw = TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    message="University detail preview loaded.",
                    data=self._tools.university_tools.get_detail_preview(
                        request.context,
                        user_input=str(effective_input),
                    ),
                    traces=plan,
                )
                return self._respond(request=request, response=raw, reference_debug=reference_debug)

            if request.kind == "data_query":
                raw = TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    message="Rankings query completed.",
                    data=self._tools.ranking_tools.list_rankings(
                        request.context,
                        user_input=str(effective_input),
                    ),
                    traces=plan,
                )
                return self._respond(request=request, response=raw, reference_debug=reference_debug)

            if request.kind == "ranking_explain":
                raw = TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    message="Ranking explanation prepared.",
                    data=self._tools.ranking_tools.explain_rankings(
                        request.context,
                        user_input=str(effective_input),
                    ),
                    traces=plan,
                )
                return self._respond(request=request, response=raw, reference_debug=reference_debug)

            if request.kind == "recommendation":
                raw = TaskResponse(
                    task_id=request.task_id,
                    status="success",
                    message="Recommendation task completed.",
                    data=self._tools.recommendation_tools.recommend(
                        request.context,
                        user_input=str(effective_input),
                    ),
                    traces=plan,
                )
                return self._respond(request=request, response=raw, reference_debug=reference_debug)

            raw = TaskResponse(
                task_id=request.task_id,
                status="rejected",
                message=f"Unsupported web task kind: {request.kind}",
                traces=plan,
            )
            return self._respond(request=request, response=raw, reference_debug=reference_debug)
        except Exception as exc:
            raw = TaskResponse(
                task_id=request.task_id,
                status="error",
                message=str(exc),
                traces=plan,
            )
            return self._respond(request=request, response=raw, reference_debug=reference_debug)

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

    @staticmethod
    def _append_warnings(response: TaskResponse, warnings: list[str]) -> None:
        """Add warnings the response does not already carry, in order.

        Duplicate-suppressing because a warning derived from the request rather
        than from the work is one a re-entrant path could otherwise emit twice,
        and the same sentence twice reads as two problems.
        """
        for warning in warnings:
            if warning not in response.warnings:
                response.warnings.append(warning)

    def _respond(
        self,
        *,
        request: TaskRequest,
        response: TaskResponse,
        reference_debug: dict[str, object] | None = None,
    ) -> TaskResponse:
        # Attached here rather than in each branch of execute() because this is
        # the single funnel every response passes through -- including the
        # error and rejected ones, and format_failure. A request naming a year
        # the warehouse does not hold is answered from the one it does, and
        # nothing else in the payload says so: the tools substitute
        # DATASET_YEAR silently and the query formatter drops caveats. The
        # warnings array is the only channel that survives formatting: it
        # reaches the API as data.warnings, which the agent page renders in its
        # dev branch (the web branch reads formatter output only, so a
        # user-facing surface for this still has to be added there).
        self._append_warnings(
            response,
            unsupported_year_warnings(
                context=request.context,
                user_input=request.user_input,
            ),
        )

        response = self._apply_generation(
            request=request,
            response=response,
            reference_debug=reference_debug,
        )

        # Lift the memory debug payload out BEFORE passing response to the
        # formatter.  Each formatter method builds a completely new dict and
        # will silently discard any field it does not recognise.  We pull the
        # payload out here and reattach it to the formatter's output afterwards,
        # so that memory debug data reaches the caller without touching the
        # formatter contract at all.
        memory_debug_payload: dict | None = None
        reference_debug_payload: dict | None = None
        grounding_debug_payload: dict | None = None
        policy_debug_payload: dict | None = None
        orchestration_debug_payload: dict | None = None
        long_term_memory_debug_payload: dict | None = None
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
        if isinstance(response.data, dict) and _REFERENCE_DEBUG_KEY in response.data:
            clean_data = {k: v for k, v in response.data.items() if k != _REFERENCE_DEBUG_KEY}
            reference_debug_payload = response.data[_REFERENCE_DEBUG_KEY]
            response = TaskResponse(
                task_id=response.task_id,
                status=response.status,
                message=response.message,
                data=clean_data,
                traces=response.traces,
                warnings=response.warnings,
            )
        if isinstance(response.data, dict) and _GROUNDING_DEBUG_KEY in response.data:
            clean_data = {k: v for k, v in response.data.items() if k != _GROUNDING_DEBUG_KEY}
            grounding_debug_payload = response.data[_GROUNDING_DEBUG_KEY]
            response = TaskResponse(
                task_id=response.task_id,
                status=response.status,
                message=response.message,
                data=clean_data,
                traces=response.traces,
                warnings=response.warnings,
            )
        if isinstance(response.data, dict) and _POLICY_DEBUG_KEY in response.data:
            clean_data = {k: v for k, v in response.data.items() if k != _POLICY_DEBUG_KEY}
            policy_debug_payload = response.data[_POLICY_DEBUG_KEY]
            response = TaskResponse(
                task_id=response.task_id,
                status=response.status,
                message=response.message,
                data=clean_data,
                traces=response.traces,
                warnings=response.warnings,
            )
        if isinstance(response.data, dict) and _ORCHESTRATION_DEBUG_KEY in response.data:
            clean_data = {k: v for k, v in response.data.items() if k != _ORCHESTRATION_DEBUG_KEY}
            orchestration_debug_payload = response.data[_ORCHESTRATION_DEBUG_KEY]
            response = TaskResponse(
                task_id=response.task_id,
                status=response.status,
                message=response.message,
                data=clean_data,
                traces=response.traces,
                warnings=response.warnings,
            )
        if isinstance(response.data, dict) and _LONG_TERM_MEMORY_DEBUG_KEY in response.data:
            clean_data = {k: v for k, v in response.data.items() if k != _LONG_TERM_MEMORY_DEBUG_KEY}
            long_term_memory_debug_payload = response.data[_LONG_TERM_MEMORY_DEBUG_KEY]
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
        if reference_debug_payload is not None and isinstance(formatted, dict):
            formatted["referenceDebug"] = reference_debug_payload
        elif (
            isinstance(formatted, dict)
            and bool(request.constraints.get("debug"))
            and reference_debug is not None
        ):
            formatted["referenceDebug"] = reference_debug
        if grounding_debug_payload is not None and isinstance(formatted, dict):
            formatted["groundingDebug"] = grounding_debug_payload
        if policy_debug_payload is not None and isinstance(formatted, dict):
            formatted["policyDebug"] = policy_debug_payload
        if orchestration_debug_payload is not None and isinstance(formatted, dict):
            formatted["orchestrationDebug"] = orchestration_debug_payload
        if long_term_memory_debug_payload is not None and isinstance(formatted, dict):
            formatted["longTermMemoryDebug"] = long_term_memory_debug_payload

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
        reference_debug: dict[str, object] | None = None,
    ) -> TaskResponse:
        if response.status != "success":
            return response
        if not self._policy.allow_generation or self._policy.generation_mode == "disabled":
            return response
        # A caller running its own two-pass pipeline -- the chat route asks the
        # engine for rows and disclosures, then writes the prose itself -- would
        # otherwise pay for an explanation nobody reads, and on a local ds4 that
        # is a 60-second model call per turn. Opt-in and exact-match, so an
        # unrecognised value leaves generation on rather than silently
        # suppressing it.
        if str(request.constraints.get("generation", "")).strip().lower() == "disabled":
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

        resolved_reference_dict = (
            reference_debug.get("resolved_reference")
            if isinstance(reference_debug, dict)
            and isinstance(reference_debug.get("resolved_reference"), dict)
            else None
        )
        memory_identity = self._resolve_memory_identity(request)
        retrieved_long_term_memory = self._long_term_retriever.retrieve(
            user_id=memory_identity,
            session_id=session_id,
            current_input=request.user_input,
            task_kind=request.kind,
            resolved_reference=resolved_reference_dict,
        )

        # --- Store the user's current input BEFORE generation ---
        if session_id:
            self._memory.append_user(
                session_id,
                content=request.user_input,
                task_kind=request.kind,
            )

        retrieved = self._context_builder.build(
            task_kind=request.kind,
            user_input=(
                str(reference_debug.get("rewritten_query"))
                if isinstance(reference_debug, dict)
                and reference_debug.get("rewrite_applied")
                and reference_debug.get("rewritten_query")
                else request.user_input
            ),
            original_input=request.user_input,
            rewritten_query=(
                str(reference_debug.get("rewritten_query"))
                if isinstance(reference_debug, dict) and reference_debug.get("rewritten_query")
                else None
            ),
            resolved_reference=(
                resolved_reference_dict
            ),
            raw_data=response.data,
            request_context=request.context,
            long_term_memory=[
                {
                    "content": entry.content,
                    "confidence": entry.confidence,
                    "type": entry.type,
                    "importance": entry.importance,
                    "decay_score": entry.decay_score,
                }
                for entry in retrieved_long_term_memory.entries
            ],
        )
        memory_ambiguity_level = (
            str(memory_debug_report.memory_summary.get("ambiguity_level"))
            if memory_debug_report is not None
            else ("medium" if selected_turns else "high")
        )
        resolved_reference = resolved_reference_dict
        policy_decision = self._generation_policy.decide(
            task_kind=request.kind,
            original_input=request.user_input,
            rewritten_query=(
                str(reference_debug.get("rewritten_query"))
                if isinstance(reference_debug, dict) and reference_debug.get("rewritten_query")
                else None
            ),
            resolved_reference=self._referential_resolver.resolve(
                current_input=request.user_input,
                task_kind=request.kind,
                history=raw_history,
            ),
            retrieved=retrieved,
            selected_memory_turns=selected_turns,
            memory_ambiguity_level=memory_ambiguity_level,
        )

        fallback_text = self._resolve_fallback_text(response)
        fallback_paragraphs = self._resolve_fallback_paragraphs(response, fallback_text)
        generation_source = "deterministic"
        model_name: str | None = None

        if policy_decision.mode == "deterministic":
            answer_text = fallback_text
            answer_paragraphs = fallback_paragraphs
        elif request.kind == "recommendation":
            # Recommendations get a dedicated grounded/honest explanation:
            # scores, ranks, and confidence stay exactly as the deterministic
            # engine computed them; the model only writes prose and always
            # degrades to the deterministic reply.
            rec_data = response.data if isinstance(response.data, dict) else {}
            rec_items = rec_data.get("items")
            rec_caveats = rec_data.get("caveats")
            explanation = self._recommendation_explainer.explain(
                items=list(rec_items) if isinstance(rec_items, list) else [],
                profile=rec_data.get("profile") if isinstance(rec_data.get("profile"), dict) else None,
                query=request.user_input,
                caveats=rec_caveats if isinstance(rec_caveats, list) else None,
                deterministic_reply=fallback_text,
            )
            answer_text = explanation.text
            answer_paragraphs = explanation.paragraphs
            generation_source = explanation.source
            model_name = explanation.model_name
            if explanation.warning:
                response.warnings.append(explanation.warning)
        elif request.kind == "ranking_explain":
            # Ranking explanations get the same grounded/honest treatment:
            # ranks, composite scores, and source counts stay exactly as the
            # warehouse reported them; the model only writes prose and always
            # degrades to the deterministic reply.
            rank_data = response.data if isinstance(response.data, dict) else {}
            rank_items = rank_data.get("items")
            rank_caveats = rank_data.get("caveats")
            explanation = self._ranking_explainer.explain(
                items=list(rank_items) if isinstance(rank_items, list) else [],
                focus_entity=str(rank_data.get("focusEntity") or ""),
                query=request.user_input,
                caveats=rank_caveats if isinstance(rank_caveats, list) else None,
                deterministic_reply=fallback_text,
            )
            answer_text = explanation.text
            answer_paragraphs = explanation.paragraphs
            generation_source = explanation.source
            model_name = explanation.model_name
            if explanation.warning:
                response.warnings.append(explanation.warning)
        elif request.kind == "university_lookup":
            # University lookups explain a single detail preview; identity,
            # ranking, and admission facts come straight from the warehouse and
            # missing sections are stated plainly (honesty contract).
            lookup_data = response.data if isinstance(response.data, dict) else {}
            lookup_caveats = lookup_data.get("caveats")
            explanation = self._university_lookup_explainer.explain(
                preview=lookup_data,
                query=request.user_input,
                caveats=lookup_caveats if isinstance(lookup_caveats, list) else None,
                deterministic_reply=fallback_text,
            )
            answer_text = explanation.text
            answer_paragraphs = explanation.paragraphs
            generation_source = explanation.source
            model_name = explanation.model_name
            if explanation.warning:
                response.warnings.append(explanation.warning)
        elif request.kind == "data_query":
            # Data queries explain the returned slice: counts, page, and notable
            # rows. Ranks, scores, and totals stay as the warehouse reported
            # them, and pagination is respected (honesty contract).
            query_data = response.data if isinstance(response.data, dict) else {}
            query_items = query_data.get("items")
            query_metadata = query_data.get("metadata")
            query_caveats = query_data.get("caveats")
            explanation = self._data_query_explainer.explain(
                items=list(query_items) if isinstance(query_items, list) else [],
                metadata=query_metadata if isinstance(query_metadata, dict) else None,
                query=request.user_input,
                caveats=query_caveats if isinstance(query_caveats, list) else None,
                deterministic_reply=fallback_text,
            )
            answer_text = explanation.text
            answer_paragraphs = explanation.paragraphs
            generation_source = explanation.source
            model_name = explanation.model_name
            if explanation.warning:
                response.warnings.append(explanation.warning)
        else:
            prompt = self._prompt_builder.build(
                user_input=(
                    str(reference_debug.get("rewritten_query"))
                    if isinstance(reference_debug, dict)
                    and reference_debug.get("rewrite_applied")
                    and reference_debug.get("rewritten_query")
                    else request.user_input
                ),
                original_input=request.user_input,
                rewritten_query=(
                    str(reference_debug.get("rewritten_query"))
                    if isinstance(reference_debug, dict) and reference_debug.get("rewritten_query")
                    else None
                ),
                resolved_reference=resolved_reference,
                retrieved=retrieved,
                policy=self._policy,
                generation_mode=policy_decision.mode,
                conversation_history=selected_turns if selected_turns else None,
            )
            generation = self._generator.generate_response(
                prompt=prompt,
                fallback_text=fallback_text,
            )
            answer_text = generation.reply_text
            answer_paragraphs = generation.paragraphs
            generation_source = generation.source
            model_name = generation.model_name
            if generation.warning:
                response.warnings.append(generation.warning)

        grounding_report = self._grounding_analyzer.analyze(
            answer_text=answer_text,
            retrieved=retrieved,
            selected_memory_turns=selected_turns,
            rewritten_query=(
                str(reference_debug.get("rewritten_query"))
                if isinstance(reference_debug, dict) and reference_debug.get("rewritten_query")
                else None
            ),
        )

        # --- Memory: persist the assistant's reply ---
        if session_id and answer_text:
            self._memory.append_assistant(
                session_id,
                content=answer_text,
                task_kind=request.kind,
            )

        self._long_term_writer.write_from_interaction(
            user_id=memory_identity,
            session_id=session_id,
            task_kind=request.kind,
            user_input=request.user_input,
            response_data=response.data,
            resolved_reference=resolved_reference_dict,
        )

        next_data = dict(response.data)
        next_data["assistantReply"] = answer_text
        next_data["assistantReplyParagraphs"] = answer_paragraphs
        next_data["generationSource"] = generation_source
        next_data["sessionId"] = session_id  # echo back so frontend can persist it
        if model_name:
            next_data["modelName"] = model_name

        # Stash memory debug report under a sentinel key so _respond() can lift
        # it out before the formatter runs (the formatter builds a fresh dict
        # and would silently discard any unrecognised fields).
        if memory_debug_report is not None:
            next_data[_MEMORY_DEBUG_KEY] = dataclasses.asdict(memory_debug_report)
        if debug_mode and reference_debug is not None:
            next_data[_REFERENCE_DEBUG_KEY] = reference_debug
        if debug_mode:
            next_data[_GROUNDING_DEBUG_KEY] = dataclasses.asdict(grounding_report)
            next_data[_POLICY_DEBUG_KEY] = policy_decision.debug
            next_data[_LONG_TERM_MEMORY_DEBUG_KEY] = {
                "retrieved": [
                    {
                        "content": entry.content,
                        "type": entry.type,
                        "used": True,
                        "confidence": entry.confidence,
                        "importance": entry.importance,
                        "decayScore": entry.decay_score,
                    }
                    for entry in retrieved_long_term_memory.entries
                ]
            }

        return TaskResponse(
            task_id=response.task_id,
            status=response.status,
            message=response.message,
            data=next_data,
            traces=response.traces,
            warnings=response.warnings,
        )

    def _resolve_memory_identity(self, request: TaskRequest) -> str | None:
        for candidate in (
            request.context.get("user_id"),
            request.constraints.get("user_id"),
            request.session_id,
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    def _resolve_fallback_text(self, response: TaskResponse) -> str:
        data = response.data
        fallback = data.get("assistantReply") or data.get("summary") or response.message
        if isinstance(fallback, str):
            return fallback
        return response.message

    def _resolve_fallback_paragraphs(
        self,
        response: TaskResponse,
        fallback_text: str,
    ) -> list[str]:
        paragraphs = response.data.get("assistantReplyParagraphs")
        if isinstance(paragraphs, list):
            safe = [str(item) for item in paragraphs if str(item).strip()]
            if safe:
                return safe
        return [fallback_text] if fallback_text else []

    def _build_reference_debug(
        self,
        *,
        request: TaskRequest,
        history: list,
    ) -> dict[str, object]:
        resolved_reference = self._referential_resolver.resolve(
            current_input=request.user_input,
            task_kind=request.kind,
            history=history,
        )
        rewrite = self._query_rewriter.rewrite(
            original_input=request.user_input,
            task_kind=request.kind,
            resolved_reference=resolved_reference,
        )
        return {
            "original_input": request.user_input,
            "rewrite_applied": rewrite.rewrite_applied,
            "rewritten_query": rewrite.rewritten_query,
            "rewrite_reason": rewrite.rewrite_reason,
            "resolved_reference": dataclasses.asdict(resolved_reference),
        }

    def format_dev_handoff_result(
        self,
        *,
        request: TaskRequest,
        dev_response: TaskResponse,
        handoff: dict[str, object],
    ) -> TaskResponse:
        dev_data = dev_response.data if isinstance(dev_response.data, dict) else {}
        file_patch = dev_data.get("filePatch", {}) if isinstance(dev_data.get("filePatch"), dict) else {}
        change_summary = (
            dev_data.get("changeSummary", {})
            if isinstance(dev_data.get("changeSummary"), dict)
            else {}
        )
        validation = dev_data.get("validation", {}) if isinstance(dev_data.get("validation"), dict) else {}
        repo_debug = dev_data.get("repoDebug", {}) if isinstance(dev_data.get("repoDebug"), dict) else {}
        handoff_context = handoff.get("context", {}) if isinstance(handoff.get("context"), dict) else {}

        file_path = str(file_patch.get("file") or repo_debug.get("resolved_file") or "project files")
        target = handoff_context.get("target")
        title_subject = str(target or file_path.rsplit("/", 1)[-1])

        explanation_parts = [
            f"I routed this into the development path and prepared a file-aware change plan for {title_subject}."
        ]
        if isinstance(change_summary.get("points"), list) and change_summary.get("points"):
            explanation_parts.append(str(change_summary["points"][0]))
        if validation.get("status") == "review":
            explanation_parts.append("The proposal still needs review before we should apply it.")
        else:
            explanation_parts.append("The current validation checks look consistent with the proposed change scope.")

        items: list[dict[str, object]] = []
        for change in (file_patch.get("changes", []) if isinstance(file_patch.get("changes"), list) else [])[:5]:
            if not isinstance(change, dict):
                continue
            items.append(
                {
                    "label": str(change.get("description") or change.get("type") or "Suggested change"),
                    "kind": str(change.get("type") or "change"),
                    "description": (
                        f"target: {change.get('target')}" if change.get("target") else str(change.get("patch_hint") or "")
                    ),
                }
            )
        if not items and file_path:
            items.append(
                {
                    "label": file_path,
                    "kind": "file",
                    "description": str(repo_debug.get("resolved_symbol") or "file-aware target"),
                }
            )

        raw = TaskResponse(
            task_id=request.task_id,
            status=dev_response.status,
            message=f"Suggested fix for {title_subject}",
            data={
                "type": "dev_result",
                "title": f"Suggested fix for {title_subject}",
                "explanation": " ".join(explanation_parts),
                "explanationParagraphs": explanation_parts,
                "items": items,
                "meta": {
                    "file": file_path,
                    "risk": change_summary.get("risk_level", "unknown"),
                    "validationStatus": validation.get("status", "unknown"),
                },
            },
            warnings=dev_response.warnings,
        )
        formatted = self._formatter.format_generic(raw)
        return TaskResponse(
            task_id=request.task_id,
            status=dev_response.status,
            message=raw.message,
            data=formatted,
            traces=[],
            warnings=dev_response.warnings,
        )
