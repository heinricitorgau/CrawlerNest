"""The caveat strings say the same thing in all four places, or this fails.

The root ``CLAUDE.md`` warns that caveat text lives in more than one place and
that changing one copy usually means changing all of them. That warning was
accurate and insufficient: two of the strings drifted anyway, and nothing
complained for as long as it took to notice by hand.

- The stale caveat named a fixed age ("RC-1 packaging", and "approximately 354
  hours ago" in Java). All three sources were re-ingested on 2026-09-04, so it
  was overstating the data's age by about two weeks.
- THE and ARWU were described as "not available at RC-1" while the warehouse
  held 1,637 THE and 838 ARWU ranks for 2026 and the API was serving them.

Java already anchored its estimate caveat to the explainability document
(``AnalyticsCaveatContractTest``). This does the same across all four copies at
once -- Python, Java, TypeScript, prose -- because a contract enforced on one
string and trusted on four others is how the four drifted.

Matching is exact substring, not fuzzy. A caveat that has been reworded in one
language is a different disclosure, which is the thing being guarded against.
"""

from __future__ import annotations


import unittest
from pathlib import Path

from crawlernest.core.caveats import (
    CAVEAT_ARWU_PARTIAL,
    CAVEAT_QS_STALE,
    CAVEAT_THE_PARTIAL,
    DISAGREEMENT_ESTIMATE_CAVEAT,
    ESTIMATED_VALUE_CAVEAT,
    STANDARD_CAVEATS,
    UNSUPPORTED_ESTIMATE_CAVEAT,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPLAINABILITY_DOC = REPO_ROOT / "docs" / "analytics" / "ANALYTICS_EXPLAINABILITY.md"
ANALYTICS_SERVICE = (
    REPO_ROOT
    / "crawlernest" / "servise_for_java" / "src" / "main" / "java" / "clawer" / "service"
    / "AnalyticsService.java"
)
CAVEAT_MESSAGES_TS = (
    REPO_ROOT / "crawlernest" / "crawlernest-web" / "src" / "lib" / "caveatMessages.ts"
)

#: Live code paths only. `releases/` and `docs/demo/` describe the state of a
#: packaged demo at a point in the past, and "RC-1 packaging" is the correct
#: thing for a historical record to say.
#:
#: Python is absent deliberately: its caveats are checked as *values* below
#: rather than by reading source. Scanning prose for a phrase cannot tell a
#: disclosure from a comment explaining why that disclosure changed, and the
#: comments naming the old wording are the fix rather than the bug.
LIVE_CODE_ROOTS = (
    REPO_ROOT / "crawlernest" / "servise_for_java" / "src" / "main",
    REPO_ROOT / "crawlernest" / "crawlernest-web" / "src",
)

#: Claims that were true once and are now false. Matched case-insensitively
#: against live source, excluding the comments that explain the correction.
STALE_CLAIMS = (
    "last ingested at RC-1 packaging",
    "not available at RC-1",
    "354 hours",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestCaveatsAgreeAcrossLanguages(unittest.TestCase):
    def test_java_carries_every_python_caveat_verbatim(self) -> None:
        java = _read(ANALYTICS_SERVICE)
        for caveat in (
            CAVEAT_QS_STALE,
            CAVEAT_THE_PARTIAL,
            CAVEAT_ARWU_PARTIAL,
            ESTIMATED_VALUE_CAVEAT,
            DISAGREEMENT_ESTIMATE_CAVEAT,
            UNSUPPORTED_ESTIMATE_CAVEAT,
        ):
            with self.subTest(caveat=caveat[:40]):
                self.assertIn(
                    caveat,
                    java,
                    "AnalyticsService.java and crawlernest/core/caveats.py disclose "
                    "different things; update whichever is wrong so they agree.",
                )

    def test_frontend_carries_every_python_caveat_verbatim(self) -> None:
        typescript = _read(CAVEAT_MESSAGES_TS)
        for caveat in (
            CAVEAT_QS_STALE,
            CAVEAT_THE_PARTIAL,
            CAVEAT_ARWU_PARTIAL,
            ESTIMATED_VALUE_CAVEAT,
            DISAGREEMENT_ESTIMATE_CAVEAT,
            UNSUPPORTED_ESTIMATE_CAVEAT,
        ):
            with self.subTest(caveat=caveat[:40]):
                self.assertIn(caveat, typescript)

    def test_explainability_doc_carries_the_estimate_caveats(self) -> None:
        # The doc is the anchor AnalyticsCaveatContractTest already reads, so a
        # caveat that reaches a user must be documented in the same words.
        doc = _read(EXPLAINABILITY_DOC)
        for caveat in (
            CAVEAT_QS_STALE,
            ESTIMATED_VALUE_CAVEAT,
            DISAGREEMENT_ESTIMATE_CAVEAT,
            UNSUPPORTED_ESTIMATE_CAVEAT,
        ):
            with self.subTest(caveat=caveat[:40]):
                self.assertIn(caveat, doc)

    def test_standard_set_is_the_three_source_caveats(self) -> None:
        self.assertEqual(
            list(STANDARD_CAVEATS),
            [CAVEAT_QS_STALE, CAVEAT_THE_PARTIAL, CAVEAT_ARWU_PARTIAL],
        )


class TestStaleClaimsAreGone(unittest.TestCase):
    """No live surface still asserts the things that stopped being true."""

    def test_no_python_caveat_value_repeats_a_stale_claim(self) -> None:
        # The values, not the source: what a user is shown is the only thing
        # that can be a false disclosure.
        for caveat in (
            *STANDARD_CAVEATS,
            ESTIMATED_VALUE_CAVEAT,
            DISAGREEMENT_ESTIMATE_CAVEAT,
            UNSUPPORTED_ESTIMATE_CAVEAT,
        ):
            for claim in STALE_CLAIMS:
                with self.subTest(caveat=caveat[:30], claim=claim):
                    self.assertNotIn(claim.lower(), caveat.lower())

    def test_no_java_or_frontend_surface_repeats_a_stale_claim(self) -> None:
        offenders: list[str] = []
        for root in LIVE_CODE_ROOTS:
            for path in root.rglob("*"):
                if path.suffix not in {".java", ".ts", ".tsx"} or not path.is_file():
                    continue
                for line in _read(path).splitlines():
                    # Javadoc and // comments recording *why* a string changed
                    # name the old wording on purpose.
                    if _is_comment(line):
                        continue
                    for claim in STALE_CLAIMS:
                        if claim.lower() in line.lower():
                            offenders.append(f"{path.relative_to(REPO_ROOT)}: {line.strip()[:90]}")
        self.assertEqual(
            offenders,
            [],
            "a live surface still claims data is unavailable or names a fixed data age",
        )

    def test_partial_coverage_caveats_do_not_claim_absence(self) -> None:
        for caveat in (CAVEAT_THE_PARTIAL, CAVEAT_ARWU_PARTIAL):
            with self.subTest(caveat=caveat[:30]):
                self.assertNotIn("is not available", caveat)
                self.assertIn("covers part of this dataset", caveat)
                # The distinction the whole caveat exists to make.
                self.assertIn("does not mean", caveat.lower())


def _is_comment(line: str) -> bool:
    """True for a Java/TS comment line, which may quote the old wording."""
    return line.strip().startswith(("*", "//", "/*"))


if __name__ == "__main__":
    unittest.main()
