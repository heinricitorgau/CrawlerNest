"""Every serving read of a multi-edition relation names exactly one edition.

``analytics.aggregated_rankings``, its ``_latest`` view, the recommendation
candidates view, ``warehouse.ranking_record``, the model predictions and the
ranking decision preview all hold one row per university *per edition*. A read
that does not constrain ``ranking_year`` reads every edition, and the day a
second one is loaded -- a 2025 shadow ingest, not yet released -- three things
break at once: each university is listed once per edition, "the newest row for
this university" becomes an older or unreleased edition's rank for any
university the current edition lacks, and unreleased rows are served as live.

The audit on 2026-09-13 found all three. The recommendations endpoint read the
candidates view through ``(? IS NULL OR ranking_year = ?)`` and passed no year;
the university detail, source comparison, explain and recommendation-evidence
reads took ``ORDER BY ranking_year DESC LIMIT 1``; the trends endpoint listed
whatever editions had finished runs and computed a composite delta against the
older one.

This test is what keeps that fixed. It reads the SQL literals of every serving
module -- the Java API, ``crawlernest/core``, ``crawlernest/agent`` and the
recommendation and comparison repositories -- and requires each one that reads a
multi-edition relation to carry an explicit, non-null ``ranking_year``
predicate. The nullable form is refused outright wherever it appears on such a
read, because it looks like a filter and is not one.

Reads that legitimately span editions are listed in :data:`ALLOWED` with the
reason, and an entry that no longer matches any query fails the test too, so the
list cannot rot into a blanket exemption. Writers (the pipeline, the analytics
bridge, ingestion) are out of scope: they own the edition they write.

Subject rankings are out of scope as well. ``DATASET_YEARS`` describes the world
ranking editions; subject editions are published on their own cycle, and their
readers deliberately pick the latest subject edition.
"""

from __future__ import annotations

import re
import unittest
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "crawlernest"

MULTI_EDITION = re.compile(
    r"(?:FROM|JOIN)\s+("
    r"analytics\.aggregated_rankings|analytics\.v_aggregated_rankings_latest|"
    r"analytics\.v_recommendation_candidates_latest|warehouse\.ranking_record|"
    r"analytics\.v_ml_predictions_latest|analytics\.ml_predictions|"
    r"warehouse\.ranking_decision_preview"
    r")\b",
    re.IGNORECASE,
)

#: ranking_year = ?, = %s, = CAST(...), = ANY(...), IN (...).
EXPLICIT_YEAR = re.compile(r"\branking_year\s*(?:=\s*(?:\?|%s|CAST\s*\(|ANY\s*\()|IN\s*\()", re.IGNORECASE)

#: (? IS NULL OR ranking_year = ?) and its CAST(...) variants.
NULLABLE_YEAR = re.compile(r"IS\s+NULL\s+OR\s+[\w.]*ranking_year\s*=", re.IGNORECASE)

JAVA_TEXT_BLOCK = re.compile(r'"""(.*?)"""', re.DOTALL)
JAVA_STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
PY_TRIPLE = re.compile(r'(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', re.DOTALL)


@dataclass(frozen=True)
class Allowed:
    path: str
    snippet: str
    reason: str
    #: A substring the file must contain, for reads whose year predicate is
    #: assembled outside the literal.
    requires: str | None = None


ALLOWED: tuple[Allowed, ...] = (
    Allowed(
        "crawlernest/servise_for_java/src/main/java/clawer/service/DataQualityService.java",
        "WHERE rr.ranking_source_id = rs.ranking_source_id",
        "operational: does an active source have any row at all, in any edition",
    ),
    Allowed(
        "crawlernest/servise_for_java/src/main/java/clawer/repository/UniversityPreviewRepository.java",
        "AS matched_by",
        "identity lookup: EXISTS on a ranking row only orders candidate records; no rank is read",
    ),
    Allowed(
        "crawlernest/core/services/ranking_service.py",
        "WHERE {where_sql}",
        "the year predicate is the first of where_clauses, and list_rankings refuses an unheld "
        "year before querying",
        requires='"rr.ranking_year = %s",',
    ),
    Allowed(
        "crawlernest/core/services/ml_service.py",
        "WHERE {' AND '.join(where)}",
        "the year predicate is in the where list, and fetch refuses an unheld year before querying",
        requires='"p.ranking_year = %s"',
    ),
)


@dataclass(frozen=True)
class Literal:
    path: str
    line: int
    sql: str


def _java_literals(path: Path) -> list[Literal]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(REPO).as_posix()
    found: list[Literal] = []
    for match in JAVA_TEXT_BLOCK.finditer(text):
        found.append(Literal(rel, text.count("\n", 0, match.start()) + 1, match.group(1)))
    without_blocks = JAVA_TEXT_BLOCK.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    for line_no, line in enumerate(without_blocks.splitlines(), start=1):
        if line.strip().startswith(("//", "*", "/*")):
            continue
        for match in JAVA_STRING.finditer(line):
            found.append(Literal(rel, line_no, match.group(1)))
    return found


def _python_literals(path: Path) -> list[Literal]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(REPO).as_posix()
    return [
        Literal(rel, text.count("\n", 0, match.start()) + 1, match.group(1))
        for match in PY_TRIPLE.finditer(text)
    ]


def serving_literals() -> list[Literal]:
    literals: list[Literal] = []
    for path in sorted((PACKAGE / "servise_for_java" / "src" / "main").rglob("*.java")):
        literals.extend(_java_literals(path))
    python_roots = (
        PACKAGE / "core",
        PACKAGE / "agent",
        PACKAGE / "crawlernest-core" / "recommendation_engine",
        PACKAGE / "crawlernest-core" / "comparison",
    )
    for root in python_roots:
        for path in sorted(root.rglob("*.py")):
            literals.extend(_python_literals(path))
    return [literal for literal in literals if MULTI_EDITION.search(literal.sql)]


class TestServingReadsNameOneEdition(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.literals = serving_literals()

    def test_the_scan_actually_finds_the_reads(self) -> None:
        # A regex that silently stopped matching would pass everything below.
        paths = {literal.path.rsplit("/", 1)[-1] for literal in self.literals}
        for expected in (
            "JdbcScopedRankingReadAdapter.java",
            "AnalyticsService.java",
            "ComparisonService.java",
            "repository.py",
        ):
            self.assertIn(expected, paths)

    def test_no_read_uses_the_nullable_year_filter(self) -> None:
        offenders = [
            f"{literal.path}:{literal.line}"
            for literal in self.literals
            if NULLABLE_YEAR.search(literal.sql)
        ]
        self.assertEqual(
            [],
            offenders,
            "(? IS NULL OR ranking_year = ?) reads every edition when no year is passed; resolve "
            "the edition first (DatasetScope / resolve_ranking_year) and filter ranking_year = ?",
        )

    def test_every_read_constrains_ranking_year_or_says_why_not(self) -> None:
        offenders: list[str] = []
        for literal in self.literals:
            if EXPLICIT_YEAR.search(literal.sql):
                continue
            if any(entry.path == literal.path and entry.snippet in literal.sql for entry in ALLOWED):
                continue
            first_line = next((line.strip() for line in literal.sql.splitlines() if line.strip()), "")
            offenders.append(f"{literal.path}:{literal.line}  {first_line[:70]}")
        self.assertEqual(
            [],
            offenders,
            "a serving read of a multi-edition relation has no ranking_year predicate. Filter to "
            "one edition, or add it to ALLOWED with the reason it must span editions.",
        )

    def test_every_allowance_still_matches_a_read(self) -> None:
        stale: list[str] = []
        for entry in ALLOWED:
            if not any(lit.path == entry.path and entry.snippet in lit.sql for lit in self.literals):
                stale.append(f"{entry.path}: {entry.snippet!r}")
            if entry.requires and entry.requires not in (REPO / entry.path).read_text(encoding="utf-8"):
                stale.append(f"{entry.path}: requires {entry.requires!r}, which is gone")
        self.assertEqual([], stale, "an ALLOWED entry no longer describes the code; remove or fix it")


class TestTheResolverRule(unittest.TestCase):
    """crawlernest.core.dataset.resolve_ranking_year and DatasetScope agree."""

    def test_python_rule(self) -> None:
        from crawlernest.core import dataset

        self.assertEqual(dataset.DEFAULT_RANKING_YEAR, dataset.resolve_ranking_year(None))
        for year in dataset.DATASET_YEARS:
            self.assertEqual(year, dataset.resolve_ranking_year(year))
        self.assertIsNone(dataset.resolve_ranking_year(min(dataset.DATASET_YEARS) - 1))
        self.assertIsNone(dataset.resolve_ranking_year(max(dataset.DATASET_YEARS) + 1))

    def test_serving_services_read_nothing_for_an_unheld_year(self) -> None:
        # No database is touched: the refusal happens before a connection.
        from crawlernest.core import dataset
        from crawlernest.core.services.ml_service import MlPredictionQuery, MlService, TARGET_OVERALL_SCORE
        from crawlernest.core.services.ranking_service import RankingQuery, RankingService

        shadow = min(dataset.DATASET_YEARS) - 1
        listing = RankingService().list_rankings(RankingQuery(year=shadow))
        self.assertEqual([], listing["items"])
        self.assertEqual(0, listing["metadata"]["totalCount"])
        self.assertEqual([], MlService().fetch(MlPredictionQuery(target=TARGET_OVERALL_SCORE, year=shadow)))

    def test_repositories_refuse_to_read_every_edition(self) -> None:
        import sys

        core = str(PACKAGE / "crawlernest-core")
        if core not in sys.path:
            sys.path.insert(0, core)
        from comparison.repository import ComparisonRepository
        from recommendation_engine.repository import RecommendationRepository

        with self.assertRaises(ValueError):
            RecommendationRepository(conn=None).fetch_candidates(ranking_year=None)
        with self.assertRaises(ValueError):
            ComparisonRepository(conn=None).resolve_university("MIT", ranking_year=None)


if __name__ == "__main__":
    unittest.main()
