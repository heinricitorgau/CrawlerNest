"""Mechanical faithfulness checking for generated explanations.

The explainers promise that the model only writes prose: it must not invent
numbers or universities, and it must reproduce caveats verbatim (see the
"No black-box scores" rule in the repo ``CLAUDE.md``). This module verifies that
promise **mechanically** — no LLM judge, no scoring model. Every violation is
derived from a rule you can read and re-check by hand, which is the same standard
the rest of the pipeline is held to.

Checks
------
``unsupported_number``
    A number in the explanation that does not appear anywhere in the evidence.
    Positions and counts derivable from the evidence list (``0..len(items)``) are
    allowed, since "the top 3" is a statement about the given list, not a new
    fact.
``missing_caveat``
    A caveat that was supplied as evidence but does not appear in the
    explanation. Caveats are an honesty contract and must survive verbatim
    (whitespace-normalized).
``unsupported_university``
    A university-shaped name ("X University", "University of X", "National X")
    that does not appear in the evidence.

Known limits (stated plainly rather than papered over):
- Number matching is textual. An explanation that legitimately reformats a value
  (``0.82`` as ``82%``) is reported as unsupported; that is deliberate, since
  rescaling a score is exactly the kind of silent transformation the honesty
  contract forbids.
- University detection is a name-shape heuristic. It catches confidently
  fabricated institutions, not every possible invented entity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

# University-shaped names: "National Taiwan University", "University of Oxford".
_UNIVERSITY_RE = re.compile(
    r"\b(?:University of [A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*"
    r"|(?:[A-Z][\w'-]*\s+){1,4}University)\b"
)


@dataclass(frozen=True)
class Violation:
    kind: str  # "unsupported_number" | "missing_caveat" | "unsupported_university"
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "detail": self.detail}


@dataclass
class FaithfulnessReport:
    faithful: bool
    violations: list[Violation] = field(default_factory=list)

    @property
    def kinds(self) -> list[str]:
        return [v.kind for v in self.violations]

    def as_dict(self) -> dict[str, Any]:
        return {
            "faithful": self.faithful,
            "violations": [v.as_dict() for v in self.violations],
        }


def _normalize_number(token: str) -> str:
    """Canonical form so 68, 68.0 and 0.820 compare equal."""
    try:
        value = float(token)
    except ValueError:
        return token
    if value == int(value):
        return str(int(value))
    return repr(round(value, 6)).rstrip("0").rstrip(".")


def _collect_evidence_numbers(evidence: Any, out: set[str]) -> None:
    """Every number appearing anywhere in the evidence, at any nesting depth."""
    if isinstance(evidence, dict):
        for value in evidence.values():
            _collect_evidence_numbers(value, out)
    elif isinstance(evidence, (list, tuple)):
        for value in evidence:
            _collect_evidence_numbers(value, out)
    elif isinstance(evidence, bool):
        return
    elif isinstance(evidence, (int, float)):
        out.add(_normalize_number(str(evidence)))
    elif isinstance(evidence, str):
        for token in _NUMBER_RE.findall(evidence):
            out.add(_normalize_number(token))


def _collect_evidence_text(evidence: Any, out: list[str]) -> None:
    if isinstance(evidence, dict):
        for value in evidence.values():
            _collect_evidence_text(value, out)
    elif isinstance(evidence, (list, tuple)):
        for value in evidence:
            _collect_evidence_text(value, out)
    elif isinstance(evidence, str):
        out.append(evidence)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check_faithfulness(
    *,
    explanation: str,
    items: list[dict[str, Any]] | None = None,
    evidence: Any = None,
    caveats: list[str] | None = None,
) -> FaithfulnessReport:
    """Check *explanation* against the evidence it was supposed to be grounded on.

    ``items`` is the usual evidence-row list; ``evidence`` accepts any extra
    structure (a profile, a detail preview) whose values also count as support.
    """
    items = items or []
    caveats = [c for c in (caveats or []) if str(c).strip()]
    violations: list[Violation] = []

    # ---- numbers ---------------------------------------------------------
    supported: set[str] = set()
    _collect_evidence_numbers(items, supported)
    if evidence is not None:
        _collect_evidence_numbers(evidence, supported)
    _collect_evidence_numbers(caveats, supported)
    # Positions and counts are statements about the given list, not new facts.
    supported.update(str(i) for i in range(len(items) + 1))

    for token in _NUMBER_RE.findall(explanation):
        if _normalize_number(token) not in supported:
            violations.append(
                Violation("unsupported_number", f"{token} does not appear in the evidence")
            )

    # ---- caveats ---------------------------------------------------------
    squashed_explanation = _squash(explanation)
    for caveat in caveats:
        if _squash(caveat) not in squashed_explanation:
            violations.append(Violation("missing_caveat", f"caveat not reproduced: {caveat}"))

    # ---- university names ------------------------------------------------
    evidence_text_parts: list[str] = []
    _collect_evidence_text(items, evidence_text_parts)
    if evidence is not None:
        _collect_evidence_text(evidence, evidence_text_parts)
    evidence_text = _squash(" ".join(evidence_text_parts)).lower()

    seen: set[str] = set()
    for name in _UNIVERSITY_RE.findall(explanation):
        key = _squash(name).lower()
        if key in seen:
            continue
        seen.add(key)
        if key not in evidence_text:
            violations.append(
                Violation("unsupported_university", f"{name} does not appear in the evidence")
            )

    return FaithfulnessReport(faithful=not violations, violations=violations)
