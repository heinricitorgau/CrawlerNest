"""Shared core for the ds4-backed, honesty-bound explanation generators.

Every task-specific explainer (recommendation, ranking, university lookup, data
query) grounds an already-computed result in prose without recomputing any
number and always degrades to the deterministic reply. That boilerplate — the
provider call, the result mapping, and the empty-input fallback — lives here so
each explainer only supplies its system instruction, constraints, evidence
block, and deterministic fallback.

Honesty contract (repo CLAUDE.md, "No black-box scores"): the model writes
explanation only. Ranks, scores, confidence, and counts stay exactly as the
deterministic layer produced them, and caveats are preserved verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass

from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator


@dataclass(slots=True)
class ExplanationResult:
    text: str
    paragraphs: list[str]
    source: str  # "llm" | "fallback"
    model_name: str | None = None
    warning: str | None = None


class GroundedExplainer:
    """Base for grounded explainers.

    Subclasses set ``system_instruction`` and ``constraints`` and call
    :meth:`_explain` with a per-task evidence block, or :meth:`_fallback_result`
    when there is nothing to ground on. The engine reuses one generator across
    every explainer, so a single provider configuration drives them all.
    """

    #: Honesty-tuned system prompt; set by each subclass.
    system_instruction: str = ""
    #: Response constraints; set by each subclass.
    constraints: tuple[str, ...] = ()

    def __init__(self, generator: WebResponseGenerator | None = None) -> None:
        self._generator = generator or WebResponseGenerator()

    def _explain(
        self,
        *,
        evidence_block: str,
        fallback: str,
        default_query: str,
        query: str = "",
    ) -> ExplanationResult:
        prompt = PromptPayload(
            system_instruction=self.system_instruction,
            user_message=query.strip() or default_query,
            context_block=evidence_block,
            response_constraints=list(self.constraints),
        )
        result: GenerationResult = self._generator.generate_response(
            prompt=prompt,
            fallback_text=fallback,
        )
        return ExplanationResult(
            text=result.reply_text,
            paragraphs=result.paragraphs,
            source=result.source,
            model_name=result.model_name,
            warning=result.warning,
        )

    @staticmethod
    def _fallback_result(fallback: str, *, warning: str | None = None) -> ExplanationResult:
        paragraphs = [part.strip() for part in fallback.split("\n\n") if part.strip()] or [fallback]
        return ExplanationResult(
            text=fallback,
            paragraphs=paragraphs,
            source="fallback",
            warning=warning,
        )

    @staticmethod
    def _clean_caveats(caveats: list[str] | None) -> list[str]:
        return [c for c in (caveats or []) if str(c).strip()]

    @staticmethod
    def _caveat_lines(caveats: list[str]) -> list[str]:
        if not caveats:
            return []
        return ["", "Caveats (reproduce verbatim, do not soften):", *[f"- {c}" for c in caveats]]
