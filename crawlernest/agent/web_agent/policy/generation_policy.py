from __future__ import annotations

import re

from crawlernest.agent.web_agent.generation.models import RetrievedContext
from crawlernest.agent.web_agent.interpretation.models import ResolvedReference
from crawlernest.agent.web_agent.memory.conversation_store import ConversationTurn
from crawlernest.agent.web_agent.policy.policy_types import (
    GenerationDecision,
    GenerationDecisionSignals,
)


class GenerationPolicy:
    def decide(
        self,
        *,
        task_kind: str,
        original_input: str,
        rewritten_query: str | None,
        resolved_reference: ResolvedReference | None,
        retrieved: RetrievedContext,
        selected_memory_turns: list[ConversationTurn],
        memory_ambiguity_level: str = "medium",
    ) -> GenerationDecision:
        query_type = self._detect_query_type(
            task_kind=task_kind,
            original_input=original_input,
            rewritten_query=rewritten_query,
            resolved_reference=resolved_reference,
        )
        retrieval_confidence = self._compute_retrieval_confidence(
            query_text=rewritten_query or original_input,
            retrieved=retrieved,
        )
        has_retrieval = retrieval_confidence > 0.0
        has_memory = len(selected_memory_turns) > 0

        signals = GenerationDecisionSignals(
            has_retrieval=has_retrieval,
            retrieval_confidence=round(retrieval_confidence, 3),
            has_memory=has_memory,
            ambiguity_level=memory_ambiguity_level,
            query_type=query_type,
        )

        if (
            query_type == "fact"
            and retrieval_confidence >= 0.45
            and memory_ambiguity_level == "low"
        ):
            return GenerationDecision(
                mode="deterministic",
                reason="Fact query has strong retrieval support and low ambiguity.",
                signals=signals,
                minimal_context=False,
                debug=self._build_debug_payload(
                    mode="deterministic",
                    reason="fact query with strong retrieval grounding",
                    signals=signals,
                ),
            )

        if query_type in {"comparison", "recommendation"}:
            return GenerationDecision(
                mode="hybrid",
                reason="Comparison or recommendation queries benefit from synthesis on top of retrieval data.",
                signals=signals,
                minimal_context=False,
                debug=self._build_debug_payload(
                    mode="hybrid",
                    reason="comparison/recommendation query requires synthesis",
                    signals=signals,
                ),
            )

        if query_type == "open_ended" and retrieval_confidence < 0.45:
            return GenerationDecision(
                mode="llm",
                reason="Open-ended query has weak retrieval grounding, so a guarded LLM answer is needed.",
                signals=signals,
                minimal_context=True,
                debug=self._build_debug_payload(
                    mode="llm",
                    reason="open-ended query with weak retrieval support",
                    signals=signals,
                ),
            )

        if retrieval_confidence < 0.15 and memory_ambiguity_level == "high":
            return GenerationDecision(
                mode="llm",
                reason="Grounding signals are weak and ambiguity is high.",
                signals=signals,
                minimal_context=True,
                debug=self._build_debug_payload(
                    mode="llm",
                    reason="weak retrieval and high ambiguity",
                    signals=signals,
                ),
            )

        if has_retrieval:
            return GenerationDecision(
                mode="hybrid",
                reason="Retrieval data exists but still needs explanation or synthesis.",
                signals=signals,
                minimal_context=False,
                debug=self._build_debug_payload(
                    mode="hybrid",
                    reason="retrieval present but synthesis still helpful",
                    signals=signals,
                ),
            )

        return GenerationDecision(
            mode="deterministic",
            reason="No reliable generation advantage detected; keep deterministic response path.",
            signals=signals,
            minimal_context=False,
            debug=self._build_debug_payload(
                mode="deterministic",
                reason="fallback to deterministic path",
                signals=signals,
            ),
        )

    def _detect_query_type(
        self,
        *,
        task_kind: str,
        original_input: str,
        rewritten_query: str | None,
        resolved_reference: ResolvedReference | None,
    ) -> str:
        text = (rewritten_query or original_input).strip()
        lowered = text.lower()

        if task_kind == "recommendation":
            return "recommendation"

        if re.search(r"(比較|相比|對比|compare|versus|\bvs\.?\b)", text, re.IGNORECASE):
            return "comparison"

        if re.search(
            r"(在哪|哪裡|哪里|哪個國家|哪个国家|ielts|toefl|雅思|托福|排名|rank|幾分|几分|多少)",
            text,
            re.IGNORECASE,
        ):
            return "fact"

        if task_kind in {"data_query", "university_lookup"}:
            return "fact"

        if re.search(r"(為什麼|为什么|explain|why|culture|特色|academic|學術文化|哲學)", lowered, re.IGNORECASE):
            return "open_ended"

        if (
            resolved_reference
            and resolved_reference.input_type == "compare_followup"
            and len(resolved_reference.resolved_entities) >= 2
        ):
            return "comparison"

        return "open_ended"

    def _compute_retrieval_confidence(
        self,
        *,
        query_text: str,
        retrieved: RetrievedContext,
    ) -> float:
        query_tokens = self._tokenize(query_text)
        retrieval_tokens = self._tokenize(" ".join(self._flatten_retrieval(retrieved)))
        if not retrieval_tokens:
            return 0.0

        overlap_ratio = (
            len(query_tokens & retrieval_tokens) / max(len(query_tokens), 1)
            if query_tokens
            else 0.0
        )
        completeness = 0.0
        if retrieved.records:
            completeness += 0.4
        if retrieved.summary_facts:
            completeness += 0.25
        if retrieved.focus_entity:
            completeness += 0.05
        if retrieved.metadata:
            completeness += 0.1
        if retrieved.source_hints:
            completeness += 0.1

        return min(1.0, round(overlap_ratio * 0.7 + completeness * 0.3, 3))

    def _flatten_retrieval(self, retrieved: RetrievedContext) -> list[str]:
        lines: list[str] = []
        if retrieved.focus_entity:
            lines.append(str(retrieved.focus_entity))
        lines.extend(str(fact) for fact in retrieved.summary_facts if str(fact).strip())
        for record in retrieved.records[:8]:
            compact = ", ".join(
                f"{key}={value}"
                for key, value in record.items()
                if value not in (None, "", [], {})
            )
            if compact:
                lines.append(compact)
        lines.extend(str(hint) for hint in retrieved.source_hints if str(hint).strip())
        return lines

    def _tokenize(self, text: str) -> set[str]:
        if not text:
            return set()
        tokens: set[str] = set()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#-]{1,}|[\u4e00-\u9fff]{2,}", text.lower()):
            normalized = token.strip(".,:;!?()[]{}\"'")
            if normalized:
                tokens.add(normalized)
        return tokens

    def _build_debug_payload(
        self,
        *,
        mode: str,
        reason: str,
        signals: GenerationDecisionSignals,
    ) -> dict[str, object]:
        return {
            "mode": mode,
            "reason": reason,
            "signals": {
                "has_retrieval": signals.has_retrieval,
                "retrieval_confidence": signals.retrieval_confidence,
                "has_memory": signals.has_memory,
                "ambiguity_level": signals.ambiguity_level,
                "query_type": signals.query_type,
            },
        }
