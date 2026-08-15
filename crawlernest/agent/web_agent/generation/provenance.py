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

## The ordering check, and why it is decidable after all

A superlative on a dimension the evidence does not rank ("the better choice for
international students", over rows carrying only rank and country) first looked
undecidable here: it needs to know which dimensions *are* ranked, and a pattern
that catches that sentence also catches ordinary comparative prose.

It is decidable, because the dimension vocabulary is closed. QS publishes nine
indicators and no more, so "for international students" resolves to a named
column, and whether that column is in the evidence is a fact about the item keys.
The check fires only when a recognised dimension term carries an ordering claim
*and* no item holds a field for it -- add the field and it goes quiet, like the
others. An ordering claim over an unrecognised criterion is left alone: guessing
there is where the false positives would come from, and precision is the whole
reason this layer can act rather than warn.

``_DIMENSIONS`` restates the indicator vocabulary rather than importing it,
because ``crawlernest-ml`` is not on the agent's import path. ``test_provenance``
loads ``ranking_ml/features/schema.py`` by path and asserts every QS indicator is
covered here, so the two cannot drift silently.
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

# An ordering claim: one thing placed above another. Kept narrow on purpose --
# these are the words that make a sentence a ranking, not merely a description.
_ORDERING = re.compile(
    r"\b(?:better|best|stronger|strongest|superior|leading|top|highest|finest"
    r"|outperforms?|outranks?|ahead|preferable|first choice)\b",
    re.IGNORECASE,
)

#: How far before a dimension term an ordering word still governs it.
#: "the better choice for international students" is 21 characters, so this is
#: wide enough for a subject clause. The window is additionally clipped at the
#: nearest sentence boundary: without that, "NTU is the best on rank. A separate
#: note: policies for international students vary by country" reads as an
#: ordering claim about international students, and it is not one.
_ORDERING_WINDOW = 60

#: Sentence terminators, used to stop the ordering window at a clause it cannot
#: legitimately reach across.
_SENTENCE_BREAK = re.compile(r"[.!?;:\n]")

# The closed vocabulary. Keys are the QS indicator labels (the source of truth is
# ranking_ml/features/schema.py:QS_INDICATORS, and test_provenance asserts this
# covers all nine); each entry lists the prose that expresses the dimension and
# the evidence fields that would support a claim about it. Field names are
# compared with punctuation and case stripped, so "International Student Ratio",
# "internationalStudentRatio" and "international_student_ratio" all match.
_DIMENSIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "Academic Reputation": (
        ("academic reputation", "academic standing", "academically"),
        ("academicReputation",),
    ),
    "Employer Reputation": (
        ("employer reputation", "employer regard", "reputation among employers"),
        ("employerReputation",),
    ),
    "Faculty Student Ratio": (
        ("faculty student ratio", "student faculty ratio", "class sizes", "teaching quality"),
        ("facultyStudentRatio", "studentFacultyRatio"),
    ),
    "Citations per Faculty": (
        ("citations per faculty", "citation impact", "research impact", "research output"),
        ("citationsPerFaculty",),
    ),
    "International Faculty Ratio": (
        ("international faculty", "international staff", "overseas faculty"),
        ("internationalFacultyRatio", "internationalFaculty"),
    ),
    "International Student Ratio": (
        ("international students", "international student ratio", "overseas students",
         "foreign students"),
        ("internationalStudentRatio", "internationalStudents"),
    ),
    "International Research Network": (
        ("international research network", "research collaboration",
         "international collaboration"),
        ("internationalResearchNetwork",),
    ),
    "Employment Outcomes": (
        ("employment outcomes", "graduate employment", "job prospects", "employability",
         "career outcomes"),
        ("employmentOutcomes",),
    ),
    "Sustainability Score": (
        ("sustainability", "environmental performance"),
        ("sustainabilityScore", "sustainability"),
    ),
}


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


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


def _present_fields(items: list[dict[str, Any]] | None, evidence: Any) -> set[str]:
    """Every field name anywhere in the evidence, normalised for comparison."""
    present: set[str] = set()
    for mapping in list(_walk(items)) + list(_walk(evidence)):
        for key, value in mapping.items():
            # A key explicitly set to null carries no dimension: that is the same
            # absence sourceRanks nulls describe, not a ranked dimension.
            if value is not None:
                present.add(_normalise(key))
    return present


def _ungrounded_ordering(body: str, present: set[str]) -> str | None:
    """A ranking claim over a dimension the evidence does not carry.

    Returns the dimension name, or ``None``. Only recognised dimensions are
    considered -- an ordering claim over some criterion outside the QS
    vocabulary is not evidence of anything, and guessing would cost the
    precision that lets this signal act.
    """
    lowered = body.lower()
    for dimension, (phrases, fields) in _DIMENSIONS.items():
        if any(_normalise(f) in present for f in fields):
            continue
        for phrase in phrases:
            for match in re.finditer(re.escape(phrase), lowered):
                window = lowered[max(0, match.start() - _ORDERING_WINDOW):match.start()]
                breaks = list(_SENTENCE_BREAK.finditer(window))
                if breaks:
                    window = window[breaks[-1].end():]
                if _ORDERING.search(window):
                    return dimension
    return None


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

    dimension = _ungrounded_ordering(body, _present_fields(items, evidence))
    if dimension:
        violations.append(ProvenanceViolation(
            "unsupported_ordering_criterion",
            f"the explanation ranks the options on {dimension}, which no field in "
            "the evidence carries",
        ))

    if _EXHAUSTIVE.search(body):
        violations.append(ProvenanceViolation(
            "unsupported_completeness_claim",
            "the evidence is the rows supplied, not the result set; the explanation "
            "claims there is nothing outside it",
        ))

    return ProvenanceReport(sound=not violations, violations=violations)
