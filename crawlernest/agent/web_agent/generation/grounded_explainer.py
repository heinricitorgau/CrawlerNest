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
from typing import Any

from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator

#: Values treated as "no evidence" when formatting fields.
_EMPTY_VALUES = (None, "", [], {})
_MISSING = object()

# A field spec entry is (source, label): `source` is a data key, or a tuple of
# candidate keys tried in order (first non-empty wins). Used to render evidence
# as "label=value; ..." without hand-writing a per-field if-ladder.
FieldSpec = list[tuple[Any, str]]


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines into non-empty paragraphs, falling back to [text]."""
    return [part.strip() for part in text.split("\n\n") if part.strip()] or [text]


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
        return ExplanationResult(
            text=fallback,
            paragraphs=split_paragraphs(fallback),
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

    @staticmethod
    def _format_fields(data: dict[str, Any], spec: FieldSpec, *, list_limit: int = 6) -> str:
        """Render selected fields as ``label=value; ...``, skipping empty values.

        Replaces the per-field ``if data.get(k): parts.append(...)`` ladders the
        explainers used to hand-write.
        """
        out: list[str] = []
        for source, label in spec:
            keys = (source,) if isinstance(source, str) else source
            value: Any = _MISSING
            for key in keys:
                candidate = data.get(key, _MISSING)
                if candidate is not _MISSING and candidate not in _EMPTY_VALUES:
                    value = candidate
                    break
            if value is _MISSING:
                continue
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value[:list_limit])
            out.append(f"{label}={value}")
        return "; ".join(out)

    @classmethod
    def _format_named_item(cls, item: dict[str, Any], spec: FieldSpec, *, list_limit: int = 6) -> str:
        """``Name (label=value; ...)`` for a single evidence row."""
        name = str(item.get("universityName") or item.get("label") or "Unknown university")
        detail = cls._format_fields(item, spec, list_limit=list_limit) or "no additional evidence"
        return f"{name} ({detail})"

    @staticmethod
    def _top_names(items: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
        """University/label names from evidence rows, for deterministic fallbacks."""
        return [
            str(item.get("universityName") or item.get("label"))
            for item in items
            if isinstance(item, dict) and (item.get("universityName") or item.get("label"))
        ][:limit]
