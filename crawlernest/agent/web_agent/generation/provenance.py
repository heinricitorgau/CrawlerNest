"""Mechanical checks on where a figure came from, how old it is, and what is absent.

``faithfulness.py`` asks whether every claim in an explanation is supported by
the evidence. This asks a different question: whether the explanation
misrepresents the *status* of that evidence. The two are independent, and the
second was the gap.

Measured on the 55-case golden set, the judge misses six failures the rules
cannot express, and all six are of one kind: an estimate credited to the ranking
source, missing data reported as the source declining to rank, our coverage gap
blamed on the institution, an ingestion point described as current, one page of
results called the complete set. Those are claims about provenance, absence and
completeness rather than about the assertions in the sentence, and they are
exactly the class this repository's honesty contract is built on -- ``caveats``
disclose absence, ``is_estimated`` discloses provenance, the support flag
discloses extrapolation.

Each check compares a structured field against a phrase pattern, so a violation
can be re-derived by hand -- the same standard the faithfulness rules are held
to, and the reason this is worth having alongside an LLM judge rather than
instead of the rules.

## What is deliberately not checked

A superlative on a dimension the evidence does not rank (``faith-108``) needs to
know which dimensions *are* ranked, and every phrasing pattern that catches "the
better choice for international students" also catches legitimate comparative
prose. Five checks with no false positives are worth more than six with some: the
value of this layer over the judge is precision, and a rule that fires on clean
text spends exactly that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: Ranking bodies this platform names. Used to spot mis-attribution.
_SOURCES = ("QS", "THE", "ARWU")

# "QS scores it at", "according to THE", "ARWU places it" -- a source presented as
# the producer of a figure.
_ATTRIBUTION = re.compile(
    r"\b(?:according to\s+(" + "|".join(_SOURCES) + r")\b"
    r"|(" + "|".join(_SOURCES) + r")\s+(?:scores|score|ranks|rank|places|place|rates|rate|gives|give|puts|put|lists|list))",
)

# "THE does not rank", "ARWU excludes", "THE has not ranked" -- absence in our
# data restated as a decision by the source.
_REFUSAL = re.compile(
    r"\b(" + "|".join(_SOURCES) + r")\b[^.]{0,60}?\b"
    r"(?:do(?:es)?\s+not\s+(?:rank|cover|include|list)"
    r"|excludes?|omits?|has\s+not\s+ranked|leaves?\s+out)",
)

# "reports less data", "provides limited information" -- a gap in our coverage
# described as something the institution did.
_INSTITUTION_BLAMED = re.compile(
    r"\b(?:reports?|provides?|discloses?|publishes?|shares?|submits?)\s+"
    r"(?:(?:much|far|somewhat)\s+)?(?:less|little|limited|fewer|no|minimal|sparse)\s+"
    r"(?:data|information|detail|figures)",
)

# "currently ranked", "as of today", "the latest tables" -- currency asserted over
# evidence that carries an ingestion point instead.
_CURRENCY = re.compile(
    r"\b(?:currently|right now|as of (?:today|now)|at present|present-day"
    r"|(?:the\s+)?(?:latest|most recent|newest|up[- ]to[- ]date)\s+"
    r"(?:tables?|rankings?|figures?|data|results?|edition))",
)

# "there are no others", "the only universities that match", "nothing else"
# -- exhaustiveness over a result set the evidence is a page of. Scoped claims
# ("all 3 on this page") are legitimate and must not match, so the patterns
# require an explicit assertion about what lies outside the evidence.
_EXHAUSTIVE = re.compile(
    r"(?:there\s+are\s+no\s+others?|no\s+others?\s+to\s+(?:consider|review|look at)"
    r"|nothing\s+else\s+to\s+(?:consider|review)"
    r"|the\s+only\s+universities\s+that\s+match"
    r"|the\s+complete\s+(?:list|set)\s+of)",
)

#: Fields that mark a value as produced by the modelling layer.
_ESTIMATE_FLAGS = ("isEstimated", "is_estimated")
#: Fields that mark the evidence as a snapshot rather than a live read.
_INGESTION_FIELDS = ("ingestedAt", "ingested_at", "lastIngestedAt", "dataAgeHours", "snapshotAt")


@dataclass(frozen=True)
class ProvenanceViolation:
    kind: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "detail": self.detail}


@dataclass
class ProvenanceReport:
    sound: bool
    violations: list[ProvenanceViolation] = field(default_factory=list)

    @property
    def kinds(self) -> list[str]:
        return [v.kind for v in self.violations]

    def as_dict(self) -> dict[str, Any]:
        return {"sound": self.sound, "violations": [v.as_dict() for v in self.violations]}


def _walk(evidence: Any):
    """Every mapping anywhere in the evidence, at any nesting depth."""
    if isinstance(evidence, dict):
        yield evidence
        for value in evidence.values():
            yield from _walk(value)
    elif isinstance(evidence, (list, tuple)):
        for value in evidence:
            yield from _walk(value)


def _has_estimate(items: list[dict[str, Any]] | None, evidence: Any) -> bool:
    for mapping in list(_walk(items)) + list(_walk(evidence)):
        for flag in _ESTIMATE_FLAGS:
            if mapping.get(flag) is True:
                return True
    return False


def _has_ingestion_marker(items: list[dict[str, Any]] | None, evidence: Any) -> bool:
    for mapping in list(_walk(items)) + list(_walk(evidence)):
        for name in _INGESTION_FIELDS:
            value = mapping.get(name)
            if value not in (None, "", [], {}):
                return True
    return False


def _null_sources(items: list[dict[str, Any]] | None, evidence: Any) -> set[str]:
    """Sources present as keys with no value -- absent from our data, not the world."""
    missing: set[str] = set()
    for mapping in list(_walk(items)) + list(_walk(evidence)):
        for key in ("sourceRanks", "source_ranks", "sourceRanksJson", "source_ranks_json"):
            ranks = mapping.get(key)
            if isinstance(ranks, dict):
                for source, rank in ranks.items():
                    if rank is None and str(source).upper() in _SOURCES:
                        missing.add(str(source).upper())
    return missing


def check_provenance(
    *,
    explanation: str,
    items: list[dict[str, Any]] | None = None,
    evidence: Any = None,
    caveats: list[str] | None = None,
) -> ProvenanceReport:
    """Check an explanation against the *status* of the evidence behind it."""
    text = explanation or ""
    violations: list[ProvenanceViolation] = []

    # Caveats are supplied text, not model claims. A caveat that legitimately
    # says "THE and ARWU ranks are null" must not trip the absence check.
    body = text
    for caveat in caveats or []:
        body = body.replace(caveat, " ")

    if _has_estimate(items, evidence):
        match = _ATTRIBUTION.search(body)
        if match:
            named = next((g for g in match.groups() if g), "a ranking source")
            violations.append(ProvenanceViolation(
                "estimate_credited_to_source",
                f"the evidence marks this value as a model estimate, and the explanation "
                f"credits it to {named}",
            ))

    missing_sources = _null_sources(items, evidence)
    if missing_sources:
        match = _REFUSAL.search(body)
        if match and match.group(1).upper() in missing_sources:
            violations.append(ProvenanceViolation(
                "absence_reported_as_refusal",
                f"{match.group(1)} has no rank in the evidence, which means it is not "
                "ingested here; the explanation states that it does not rank the university",
            ))

    if caveats and _INSTITUTION_BLAMED.search(body):
        violations.append(ProvenanceViolation(
            "coverage_gap_blamed_on_institution",
            "a disclosed coverage limitation is described as the university disclosing less",
        ))

    if _has_ingestion_marker(items, evidence) and _CURRENCY.search(body):
        violations.append(ProvenanceViolation(
            "stale_data_claimed_current",
            "the evidence records an ingestion point, and the explanation asserts currency",
        ))

    if _EXHAUSTIVE.search(body):
        violations.append(ProvenanceViolation(
            "unsupported_completeness_claim",
            "the evidence is the rows supplied, not the result set; the explanation "
            "claims there is nothing outside it",
        ))

    return ProvenanceReport(sound=not violations, violations=violations)
