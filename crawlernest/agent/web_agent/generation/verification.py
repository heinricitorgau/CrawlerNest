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

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any

from crawlernest.agent.web_agent.generation.faithfulness import check_faithfulness
from crawlernest.agent.web_agent.generation.judge import JudgeVerdict, LlmJudge

#: What the caller should do with the generated text.
KEEP = "keep"
KEEP_WITH_WARNING = "keep_with_warning"
USE_FALLBACK = "use_fallback"

# Process-wide counters, mirroring response_generator's generation_stats.
#
# Two failure modes are invisible without them, and they look nothing alike. A
# judge that starts flagging everything shows up as keep_with_warning climbing
# toward the total. A judge that has quietly gone dark -- wrong URL, expired key,
# a host that accepts connections and times out -- shows up as judge_no_opinion
# climbing instead, while every response still looks fine.
_stats_lock = threading.Lock()
_verification_stats: dict[str, int] = {
    "keep": 0,
    "keep_with_warning": 0,
    "use_fallback": 0,
    "judge_agreed": 0,
    "judge_flagged": 0,
    "judge_no_opinion": 0,
    "judge_absent": 0,
}


def verification_stats() -> dict[str, int]:
    """Snapshot of verification outcomes since process start.

    Actions, one per verified explanation:

    - ``keep``: both signals clean, or the only signal was clean.
    - ``keep_with_warning``: the judge objected and the rules did not; the text
      was kept because the judge's precision does not justify discarding it.
    - ``use_fallback``: the rules fired and the model's text was discarded.

    Judge outcomes, which do not sum to the actions because the rules
    short-circuit the judge entirely when they fire:

    - ``judge_agreed`` / ``judge_flagged``: it was asked and answered.
    - ``judge_no_opinion``: asked, and unreachable, slow or unparseable.
    - ``judge_absent``: not configured, or not consulted because the rules had
      already decided.
    """
    with _stats_lock:
        return dict(_verification_stats)


def reset_verification_stats() -> None:
    """Zero the counters (mainly for tests)."""
    with _stats_lock:
        for key in _verification_stats:
            _verification_stats[key] = 0


def _record(*outcomes: str) -> None:
    with _stats_lock:
        for outcome in outcomes:
            _verification_stats[outcome] = _verification_stats.get(outcome, 0) + 1


_LOG = logging.getLogger("CrawlerNest.agent.verification")

# A configured judge that answers nothing is the failure worth saying out loud,
# because it is the one that leaves no trace in the responses: every explanation
# still reads fine. Serving the count at /api/v1/agent/stats only helps someone
# who looks. This says it where logs already go.
#
# Threshold rather than every occurrence: one timeout is weather, a run of them
# is a broken endpoint, and a warning per request would be noise nobody reads --
# which is the failure mode this whole layer keeps running into.
_DARK_JUDGE_THRESHOLD = int(os.getenv("WEB_AGENT_JUDGE_DARK_THRESHOLD", "5") or 5)
_consecutive_no_opinion = 0
_dark_judge_reported = False


def _note_judge_answered() -> None:
    """A real verdict: reset the streak, and say so if it had been reported."""
    global _consecutive_no_opinion, _dark_judge_reported
    with _stats_lock:
        recovered = _dark_judge_reported
        _consecutive_no_opinion = 0
        _dark_judge_reported = False
    if recovered:
        _LOG.info("Judge is answering again after a run of no-opinion replies.")


def _note_judge_silent(judge: LlmJudge) -> None:
    global _consecutive_no_opinion, _dark_judge_reported
    with _stats_lock:
        _consecutive_no_opinion += 1
        streak = _consecutive_no_opinion
        should_report = streak >= _DARK_JUDGE_THRESHOLD and not _dark_judge_reported
        if should_report:
            _dark_judge_reported = True
    if should_report:
        _LOG.warning(
            "Judge configured at %s (model %s) has returned no opinion %d times in a row. "
            "Explanations are being verified by the rules alone; nothing in the responses "
            "shows this.",
            judge.base_url or "<unset>",
            judge.model_name,
            streak,
        )


# The mirror image: a judge objecting to everything. Less urgent than silence,
# because it is at least visible in each response's warning, but a reviewer that
# rejects every answer is broken in the same way and just as worth saying once.
_FLAG_STORM_THRESHOLD = int(os.getenv("WEB_AGENT_JUDGE_FLAG_STORM_THRESHOLD", "10") or 10)
_consecutive_flags = 0
_flag_storm_reported = False


def _note_judge_verdict(flagged: bool, judge: LlmJudge) -> None:
    """Track runs of consecutive objections, and report one once."""
    global _consecutive_flags, _flag_storm_reported
    with _stats_lock:
        if flagged:
            _consecutive_flags += 1
        else:
            _consecutive_flags = 0
            _flag_storm_reported = False
        streak = _consecutive_flags
        should_report = flagged and streak >= _FLAG_STORM_THRESHOLD and not _flag_storm_reported
        if should_report:
            _flag_storm_reported = True
    if should_report:
        _LOG.warning(
            "Judge at %s (model %s) has objected to %d explanations in a row. Each was kept, "
            "since the rules found nothing; a reviewer rejecting everything is as broken as "
            "one rejecting nothing.",
            judge.base_url or "<unset>",
            judge.model_name,
            streak,
        )


def reset_judge_health() -> None:
    """Clear the streak state (mainly for tests)."""
    global _consecutive_no_opinion, _dark_judge_reported
    global _consecutive_flags, _flag_storm_reported
    with _stats_lock:
        _consecutive_no_opinion = 0
        _dark_judge_reported = False
        _consecutive_flags = 0
        _flag_storm_reported = False


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
        _record(USE_FALLBACK, "judge_absent")
        return VerificationOutcome(action=USE_FALLBACK, rule_violations=report.kinds)

    verdict: JudgeVerdict | None = None
    if judge is None:
        _record("judge_absent")
    else:
        verdict = judge.review(
            explanation=explanation, items=items, caveats=caveats, evidence=evidence
        )
        if verdict is None:
            _record("judge_no_opinion")
            _note_judge_silent(judge)
        elif verdict.faithful:
            _record("judge_agreed")
            _note_judge_answered()
            _note_judge_verdict(flagged=False, judge=judge)
        else:
            _record("judge_flagged")
            _note_judge_answered()
            _note_judge_verdict(flagged=True, judge=judge)

    if verdict is not None and not verdict.faithful:
        _record(KEEP_WITH_WARNING)
        return VerificationOutcome(
            action=KEEP_WITH_WARNING,
            judge_reason=verdict.reason or "no reason given",
            judge_model=verdict.model_name,
        )

    _record(KEEP)
    return VerificationOutcome(action=KEEP)
