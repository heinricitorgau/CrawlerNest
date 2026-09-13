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

That contract has a temporal half, added here because it cannot be enforced
downstream: a trend claim invents no figure, no caveat and no institution, so
nothing in ``faithfulness.py`` reaches it. :meth:`GroundedExplainer._explain`
therefore states the shape of the corpus at the top of every evidence block and
appends the year and movement rules to every explainer's constraints, both
derived from the rows it was given -- see ``dataset_context.py``. Subclasses get
both for free and must not restate either.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from crawlernest.agent.web_agent.generation.dataset_context import (
    build_dataset_header,
    dataset_constraints,
)
from crawlernest.agent.web_agent.generation.judge import LlmJudge
from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator
from crawlernest.agent.web_agent.generation.verification import (
    USE_FALLBACK,
    verify_explanation,
)

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

    def __init__(
        self,
        generator: WebResponseGenerator | None = None,
        judge: LlmJudge | None = None,
        verify: bool | None = None,
    ) -> None:
        self._generator = generator or WebResponseGenerator()
        # Absent unless WEB_AGENT_JUDGE_BASE_URL is set; see judge.LlmJudge.
        self._judge = judge if judge is not None else LlmJudge()
        # On by default: the honesty contract is the reason this layer exists.
        # WEB_AGENT_VERIFY_EXPLANATIONS=0 disables it, which means shipping model
        # text that has not been checked against its evidence -- an operational
        # escape hatch, not a supported mode.
        self._verify = (
            verify if verify is not None
            else os.getenv("WEB_AGENT_VERIFY_EXPLANATIONS", "1").strip() not in {"0", "false", "no"}
        )

    def _explain(
        self,
        *,
        evidence_block: str,
        fallback: str,
        default_query: str,
        query: str = "",
        items: list[dict[str, Any]] | None = None,
        caveats: list[str] | None = None,
    ) -> ExplanationResult:
        # The corpus description leads the evidence, and the same enriched block
        # is what verification checks the answer against: the dataset year is a
        # fact of the evidence, so an explanation naming it must not read as an
        # invented figure.
        #
        # Both are computed from the rows: which years they carry, and whether
        # any carries a rank-change field. What the warehouse holds does not
        # decide what these rows can show.
        dataset_header = build_dataset_header(items)
        rules = dataset_constraints(items)
        grounded_block = f"{dataset_header}\n\n{evidence_block}"

        # The header and the dataset rules go in twice, on purpose: once here in
        # the system turn, where they cannot read as one turn's request, and
        # once below in the user turn, where they sit next to the evidence they
        # describe. See PromptPayload.system_context for why the user turn alone
        # is not enough.
        prompt = PromptPayload(
            system_instruction=self.system_instruction,
            user_message=query.strip() or default_query,
            context_block=grounded_block,
            response_constraints=[*self.constraints, *rules],
            system_context=dataset_header,
            system_constraints=[*rules],
        )
        result: GenerationResult = self._generator.generate_response(
            prompt=prompt,
            fallback_text=fallback,
        )

        # Only model output is worth checking. The fallback is the deterministic
        # text this layer would substitute anyway, so verifying it would at best
        # replace it with itself.
        if not self._verify or result.source != "llm":
            return ExplanationResult(
                text=result.reply_text,
                paragraphs=result.paragraphs,
                source=result.source,
                model_name=result.model_name,
                warning=result.warning,
            )

        outcome = verify_explanation(
            explanation=result.reply_text,
            items=items,
            caveats=caveats,
            evidence=grounded_block,
            judge=self._judge if self._judge.is_configured else None,
        )
        warning = " ".join(w for w in (result.warning, outcome.warning) if w) or None

        if outcome.action == USE_FALLBACK:
            return ExplanationResult(
                text=fallback,
                paragraphs=split_paragraphs(fallback),
                source="fallback",
                model_name=result.model_name,
                warning=warning,
            )

        return ExplanationResult(
            text=result.reply_text,
            paragraphs=result.paragraphs,
            source=result.source,
            model_name=result.model_name,
            warning=warning,
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
