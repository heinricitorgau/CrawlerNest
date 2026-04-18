from __future__ import annotations

import re
from dataclasses import asdict

from crawlernest.agent.web_agent.generation.models import RetrievedContext
from crawlernest.agent.web_agent.grounding.grounding_types import (
    GroundingExplanation,
    GroundingReport,
    GroundingScore,
    GroundingSourceDetail,
    HallucinationRisk,
)
from crawlernest.agent.web_agent.memory.conversation_store import ConversationTurn


class GroundingAnalyzer:
    def analyze(
        self,
        *,
        answer_text: str,
        retrieved: RetrievedContext,
        selected_memory_turns: list[ConversationTurn],
        rewritten_query: str | None = None,
    ) -> GroundingReport:
        answer_tokens = self._tokenize(answer_text)

        retrieval_lines = self._flatten_retrieval(retrieved, rewritten_query=rewritten_query)
        retrieval_detail = self._analyze_retrieval(answer_tokens, retrieval_lines)
        memory_detail = self._analyze_memory(answer_tokens, selected_memory_turns)
        generation_detail = self._analyze_generation(
            retrieval_score=retrieval_detail.match_score,
            memory_score=memory_detail.match_score,
        )

        overall = round(
            min(1.0, retrieval_detail.match_score * 0.7 + memory_detail.match_score * 0.3),
            3,
        )
        score = GroundingScore(
            overall=overall,
            breakdown={
                "retrieval_weight": round(retrieval_detail.match_score, 3),
                "memory_weight": round(memory_detail.match_score, 3),
            },
        )
        risk = self._assess_hallucination_risk(
            retrieval_score=retrieval_detail.match_score,
            memory_score=memory_detail.match_score,
        )
        explanation = self._build_explanation(
            retrieval_detail=retrieval_detail,
            memory_detail=memory_detail,
            generation_detail=generation_detail,
        )

        return GroundingReport(
            answer_preview=self._preview(answer_text),
            grounding_sources={
                "retrieval": asdict(retrieval_detail),
                "memory": asdict(memory_detail),
                "generation": asdict(generation_detail),
            },
            grounding_score=score,
            hallucination_risk=risk,
            explanation=explanation,
        )

    def _analyze_retrieval(
        self,
        answer_tokens: set[str],
        retrieval_lines: list[str],
    ) -> GroundingSourceDetail:
        if not retrieval_lines or not answer_tokens:
            return GroundingSourceDetail(
                used=False,
                matched_items=[],
                match_score=0.0,
                reason="No retrieval context or no answer tokens available.",
            )

        matched_items: list[str] = []
        retrieval_tokens: set[str] = set()
        for line in retrieval_lines:
            line_tokens = self._tokenize(line)
            retrieval_tokens |= line_tokens
            if answer_tokens & line_tokens:
                matched_items.append(self._preview(line))

        overlap = answer_tokens & retrieval_tokens
        score = round(len(overlap) / max(len(answer_tokens), 1), 3)
        return GroundingSourceDetail(
            used=score > 0.0,
            matched_items=matched_items[:5],
            match_score=score,
            reason="Answer tokens overlap with retrieved context."
            if score > 0.0
            else "Answer tokens have little overlap with retrieved context.",
        )

    def _analyze_memory(
        self,
        answer_tokens: set[str],
        selected_memory_turns: list[ConversationTurn],
    ) -> GroundingSourceDetail:
        if not selected_memory_turns or not answer_tokens:
            return GroundingSourceDetail(
                used=False,
                matched_items=[],
                match_score=0.0,
                reason="No selected memory turns or no answer tokens available.",
            )

        matched_turns: list[str] = []
        memory_tokens: set[str] = set()
        for turn in selected_memory_turns:
            turn_tokens = self._tokenize(turn.content)
            memory_tokens |= turn_tokens
            if answer_tokens & turn_tokens:
                matched_turns.append(
                    f"{turn.role}: {self._preview(turn.content)}"
                )

        overlap = answer_tokens & memory_tokens
        score = round(len(overlap) / max(len(answer_tokens), 1), 3)
        return GroundingSourceDetail(
            used=score > 0.0,
            matched_items=matched_turns[:5],
            match_score=score,
            reason="Answer tokens overlap with selected conversation memory."
            if score > 0.0
            else "Answer tokens have little overlap with selected conversation memory.",
        )

    def _analyze_generation(
        self,
        *,
        retrieval_score: float,
        memory_score: float,
    ) -> GroundingSourceDetail:
        generation_used = retrieval_score < 0.25 and memory_score < 0.2
        if generation_used:
            reason = "No strong retrieval or memory grounding signal was found."
        elif retrieval_score >= memory_score:
            reason = "Generation appears to be packaging retrieval-backed content."
        else:
            reason = "Generation appears to be packaging memory-assisted content."

        return GroundingSourceDetail(
            used=generation_used,
            matched_items=[],
            match_score=round(max(0.0, 1.0 - max(retrieval_score, memory_score)), 3),
            reason=reason,
        )

    def _assess_hallucination_risk(
        self,
        *,
        retrieval_score: float,
        memory_score: float,
    ) -> HallucinationRisk:
        if retrieval_score >= 0.45:
            return HallucinationRisk(
                level="low",
                reason="Answer strongly overlaps with retrieved context.",
            )
        if retrieval_score >= 0.2 and memory_score >= 0.15:
            return HallucinationRisk(
                level="medium",
                reason="Answer is supported by a mix of retrieval context and memory, but grounding is partial.",
            )
        if retrieval_score < 0.2 and memory_score < 0.15:
            return HallucinationRisk(
                level="high",
                reason="Both retrieval and memory overlap are weak, so the answer may rely on generation alone.",
            )
        return HallucinationRisk(
            level="medium",
            reason="Grounding signals exist, but they are not strong enough to be considered low risk.",
        )

    def _build_explanation(
        self,
        *,
        retrieval_detail: GroundingSourceDetail,
        memory_detail: GroundingSourceDetail,
        generation_detail: GroundingSourceDetail,
    ) -> GroundingExplanation:
        if retrieval_detail.match_score >= max(memory_detail.match_score, 0.25):
            summary = "Answer is primarily grounded in retrieval data."
            detail = retrieval_detail.reason or "Retrieved context provided the strongest support."
        elif memory_detail.match_score >= 0.2:
            summary = "Answer uses both recent memory and retrieved context."
            detail = (
                "Selected memory turns contributed meaningful overlap while retrieval still provided supporting evidence."
            )
        elif generation_detail.used:
            summary = "Answer is weakly grounded and relies mostly on generation."
            detail = generation_detail.reason or "No strong grounding evidence was found."
        else:
            summary = "Answer has mixed grounding support."
            detail = "Grounding signals are present, but no single source clearly dominates."

        return GroundingExplanation(summary=summary, detail=detail)

    def _flatten_retrieval(
        self,
        retrieved: RetrievedContext,
        *,
        rewritten_query: str | None,
    ) -> list[str]:
        lines: list[str] = []
        if rewritten_query:
            lines.append(rewritten_query)
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

        for key, value in retrieved.metadata.items():
            if value not in (None, "", [], {}):
                lines.append(f"{key}={value}")

        lines.extend(str(hint) for hint in retrieved.source_hints if str(hint).strip())
        return lines

    def _tokenize(self, text: str) -> set[str]:
        if not text:
            return set()
        tokens: set[str] = set()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+#-]{1,}|\b[\u4e00-\u9fff]{2,}\b", text.lower()):
            normalized = token.strip(".,:;!?()[]{}\"'")
            if normalized:
                tokens.add(normalized)
        return tokens

    def _preview(self, text: str, limit: int = 120) -> str:
        cleaned = " ".join(text.strip().split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit] + "…"
