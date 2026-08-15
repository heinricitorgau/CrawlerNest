"""Decide what to do with a generated explanation, given two signals.

Until now the faithfulness checker existed only in the evaluation harness: it was
scored on a golden set every CI run and never consulted at generation time. So an
explanation that violated the honesty contract was measured, not stopped. This is
the layer that acts on it.

Two signals with different precision, so two different responses:

``rules`` -- the mechanical checker
    Perfect precision on the golden set: 20 detections, no false positives. When
    it fires, the explanation really did invent a figure, drop a caveat or name
    an institution that is not there. Acting decisively is warranted, so the
    deterministic reply is used instead and the model's text is discarded.

``judge`` -- the optional LLM second opinion
    Recall 0.714 against 0.607 for the rules, but precision 0.952: one clean
    explanation in the golden set gets flagged. Discarding a good answer on a
    signal that is wrong one time in twenty is the wrong trade, so a judge-only
    concern attaches a warning and keeps the text. The warning is for operators
    reading generation stats, not a user-facing accusation.

Absence of the judge is not approval. ``None`` from the judge means no opinion --
unconfigured, unreachable, or an unparseable reply -- and the outcome is exactly
what the rules alone would have produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crawlernest.agent.web_agent.generation.faithfulness import check_faithfulness
from crawlernest.agent.web_agent.generation.judge import JudgeVerdict, LlmJudge

#: What the caller should do with the generated text.
KEEP = "keep"
KEEP_WITH_WARNING = "keep_with_warning"
USE_FALLBACK = "use_fallback"


@dataclass(frozen=True)
class VerificationOutcome:
    action: str
    rule_violations: list[str] = field(default_factory=list)
    judge_reason: str | None = None
    judge_model: str | None = None

    @property
    def warning(self) -> str | None:
        """One line for the caller to attach, or ``None`` when nothing was found."""
        if self.action == USE_FALLBACK:
            kinds = ", ".join(sorted(set(self.rule_violations)))
            return (f"Generated explanation failed the faithfulness check ({kinds}); "
                    "deterministic reply used.")
        if self.action == KEEP_WITH_WARNING:
            return (f"Second-opinion review flagged this explanation: {self.judge_reason} "
                    "The mechanical check found nothing, so the text was kept.")
        return None

    def as_stats_key(self) -> str:
        return self.action


def verify_explanation(
    *,
    explanation: str,
    items: list[dict[str, Any]] | None = None,
    caveats: list[str] | None = None,
    evidence: Any = None,
    judge: LlmJudge | None = None,
) -> VerificationOutcome:
    """Run the rules, then the judge if one is configured, and decide."""
    report = check_faithfulness(
        explanation=explanation, items=items, evidence=evidence, caveats=caveats
    )
    if not report.faithful:
        # The rules are authoritative for what they define. No point asking a
        # second opinion about a verdict that is already reliable.
        return VerificationOutcome(action=USE_FALLBACK, rule_violations=report.kinds)

    verdict: JudgeVerdict | None = None
    if judge is not None:
        verdict = judge.review(
            explanation=explanation, items=items, caveats=caveats, evidence=evidence
        )

    if verdict is not None and not verdict.faithful:
        return VerificationOutcome(
            action=KEEP_WITH_WARNING,
            judge_reason=verdict.reason or "no reason given",
            judge_model=verdict.model_name,
        )

    return VerificationOutcome(action=KEEP)
