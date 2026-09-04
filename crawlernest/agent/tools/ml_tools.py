"""Agent access to model estimates, with the disclosure attached rather than optional.

The modelling layer produces two things the agent can use: an estimated QS
overall score for universities QS withholds one from, and a probability that QS
and THE would disagree about a university. Both are useful. Both are also the
easiest thing in this system to state dishonestly, because they look exactly like
a published figure once they are in a sentence.

Golden case faith-105 is that failure, recorded: evidence carrying
``estimatedOverallScore: 20.4`` and the disclosure caveat, and an explanation
reading "QS scores University of Kragujevac at 20.4". Every number in it is
supported and the caveat is reproduced verbatim, so ``faithfulness.py`` passes it.
What catches it is ``provenance.check_provenance``, whose
``estimate_credited_to_source`` rule fires when the evidence carries
``isEstimated`` and the prose credits a ranking source. That rule is armed by the
data, not by a prompt.

So this module has one job beyond fetching rows: make it impossible to obtain
the values without the two things that make them safe.

- :class:`EstimateEvidence` carries items and caveats together. There is no
  method here that returns bare items, because a caller holding a list of
  estimates with the caveats left behind is precisely how the caveat gets
  dropped.
- Every row keeps ``isEstimated`` and ``isSupported`` from
  :class:`~crawlernest.core.services.ml_service.MlService`. Strip either and
  faith-105 stops being detectable at all.

None of this stops a model saying "QS scores it at 20.4". It makes the sentence
catchable when it does, which is the standard the rest of the verification layer
is held to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crawlernest.core.caveats import DISAGREEMENT_ESTIMATE_CAVEAT, ESTIMATED_VALUE_CAVEAT
from crawlernest.core.dataset import DATASET_YEAR
from crawlernest.core.services.ml_service import (
    TARGET_DISAGREEMENT,
    TARGET_OVERALL_SCORE,
    MlPredictionQuery,
    MlService,
)

__all__ = ["EstimateEvidence", "MlTools"]


@dataclass(slots=True)
class EstimateEvidence:
    """Estimate rows and the disclosures they may not be separated from.

    The explainers take ``items`` and ``caveats`` as two arguments, so the pairing
    has to survive the trip from here to there. Handing both back in one object
    is what makes dropping one of them a visible edit rather than an omission.
    """

    items: list[dict[str, Any]] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.items

    def as_dict(self) -> dict[str, Any]:
        return {"items": list(self.items), "caveats": list(self.caveats)}


class MlTools:
    """Estimate lookups for the agent's read path.

    Read-only, in keeping with the analytics rule in the repo ``CLAUDE.md``: this
    reads stored predictions and never triggers training or inference.
    """

    def __init__(self, service: MlService | None = None) -> None:
        self._service = service or MlService()

    # -- individual targets --------------------------------------------------

    def estimated_overall_scores(
        self,
        *,
        canonical_university_ids: tuple[int, ...] = (),
        year: int = DATASET_YEAR,
        limit: int = 200,
    ) -> EstimateEvidence:
        """Estimated QS overall scores, disclosed as estimates."""
        return self._fetch(
            target=TARGET_OVERALL_SCORE,
            caveats=[ESTIMATED_VALUE_CAVEAT],
            canonical_university_ids=canonical_university_ids,
            year=year,
            limit=limit,
        )

    def disagreement_probabilities(
        self,
        *,
        canonical_university_ids: tuple[int, ...] = (),
        year: int = DATASET_YEAR,
        limit: int = 200,
    ) -> EstimateEvidence:
        """Cross-source disagreement probabilities, disclosed twice over.

        Two caveats, not one: the general estimate disclosure, and the specific
        one saying a probability is not an observed disagreement. The second
        exists because the first does not cover the likeliest misreading -- "0.99
        disagreement" reads as a measured conflict, and for most of these
        universities THE publishes no rank to have conflicted with.
        """
        return self._fetch(
            target=TARGET_DISAGREEMENT,
            caveats=[ESTIMATED_VALUE_CAVEAT, DISAGREEMENT_ESTIMATE_CAVEAT],
            canonical_university_ids=canonical_university_ids,
            year=year,
            limit=limit,
        )

    # -- joining onto ranking rows -------------------------------------------

    def annotate(
        self,
        items: list[dict[str, Any]],
        *,
        year: int = DATASET_YEAR,
    ) -> EstimateEvidence:
        """Merge available estimates onto ranking rows, disclosing only what landed.

        Rows are matched on ``canonicalUniversityId``; a row without one is
        returned untouched. The caveats describe what is actually present, so a
        page whose universities all carry published scores comes back with none
        -- an unconditional disclosure would be false there, and a caveat that
        fires when it does not apply teaches readers to skip the array.
        """
        rows = [item for item in items if isinstance(item, dict)]
        ids = tuple(
            int(item["canonicalUniversityId"])
            for item in rows
            if item.get("canonicalUniversityId") is not None
        )
        if not ids:
            return EstimateEvidence(items=[dict(item) for item in rows], caveats=[])

        scores = self._fetch(
            target=TARGET_OVERALL_SCORE,
            caveats=[],
            canonical_university_ids=ids,
            year=year,
            limit=len(ids),
        )
        risks = self._fetch(
            target=TARGET_DISAGREEMENT,
            caveats=[],
            canonical_university_ids=ids,
            year=year,
            limit=len(ids),
        )

        by_id: dict[int, dict[str, Any]] = {}
        for estimate in (*scores.items, *risks.items):
            by_id.setdefault(int(estimate["canonicalUniversityId"]), {}).update(
                self._estimate_fields(estimate)
            )

        merged: list[dict[str, Any]] = []
        for item in rows:
            enriched = dict(item)
            university_id = item.get("canonicalUniversityId")
            if university_id is not None:
                enriched.update(by_id.get(int(university_id), {}))
            merged.append(enriched)

        caveats: list[str] = []
        if scores.items:
            caveats.append(ESTIMATED_VALUE_CAVEAT)
        if risks.items:
            if ESTIMATED_VALUE_CAVEAT not in caveats:
                caveats.append(ESTIMATED_VALUE_CAVEAT)
            caveats.append(DISAGREEMENT_ESTIMATE_CAVEAT)

        return EstimateEvidence(items=merged, caveats=caveats)

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _estimate_fields(estimate: dict[str, Any]) -> dict[str, Any]:
        """The fields worth merging onto a ranking row.

        ``isEstimated`` and ``isSupported`` come across with the value. A merged
        row that carried the score but not the flags would read as a published
        figure to every downstream check.
        """
        fields = {
            key: estimate[key]
            for key in ("estimatedOverallScore", "disagreementProbability", "isSupported")
            if key in estimate
        }
        if fields:
            fields["isEstimated"] = True
        return fields

    def _fetch(
        self,
        *,
        target: str,
        caveats: list[str],
        canonical_university_ids: tuple[int, ...],
        year: int,
        limit: int,
    ) -> EstimateEvidence:
        items = self._service.fetch(
            MlPredictionQuery(
                target=target,
                year=year,
                canonical_university_ids=canonical_university_ids,
                limit=limit,
            )
        )
        # No rows, no disclosure: the caveat describes values in the response,
        # and there are none.
        return EstimateEvidence(items=items, caveats=list(caveats) if items else [])
