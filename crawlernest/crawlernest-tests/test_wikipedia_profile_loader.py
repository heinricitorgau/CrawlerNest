"""Tests for wikipedia_profile_loader: which Wikipedia article a university gets, and what is kept of it.

No test touches the network; Wikipedia and Wikidata are canned answers behind the
loader's ``ApiClient``. What these pin down is the refusals. Showing another
university's article is worse than showing none, so most cases here are a match that
must *not* be made.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
for _p in (str(PACKAGE_ROOT / "crawlernest-jobs"), str(PACKAGE_ROOT.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import wikipedia_profile_loader as W  # noqa: E402


def university(name: str, country: str | None = "United States", *, slug: str = "u", ident: int = 1, **kw: Any):
    return W.University(ident, slug, name, country, **kw)


def entity(qid: str, label: str, *, country: str = "United States", types=("university",), title: str | None = None,
           aliases=(), has_id: bool = False) -> W.Entity:
    return W.Entity(qid, label, list(aliases), [country], list(types), has_id, title or label)


class FakeClient:
    """Answers ``get_json`` from the request's action; records nothing, fails on a surprise."""

    def __init__(self, *, pages: dict[str, dict[str, Any]] | None = None, redirects: dict[str, Any] | None = None,
                 extract: dict[str, Any] | None = None) -> None:
        self.pages = pages or {}
        self.redirects = redirects or {}
        self.extract = extract
        self.title_batches: list[list[str]] = []

    def get_json(self, url: str, params: dict[str, Any], *, post: bool = False) -> Any:
        if params.get("prop") == "pageprops":
            titles = params["titles"].split("|")
            self.title_batches.append(titles)
            redirects = [
                {"from": t, **(self.redirects[t] if isinstance(self.redirects[t], dict) else {"to": self.redirects[t]})}
                for t in titles if t in self.redirects
            ]
            targets = {r["to"] for r in redirects} | {t for t in titles if t not in self.redirects}
            pages = [self.pages.get(t, {"title": t, "missing": True}) for t in sorted(targets)]
            return {"query": {"redirects": redirects, "pages": pages}}
        if "extracts" in str(params.get("prop")):
            return {"query": {"pages": [self.extract] if self.extract else []}}
        raise AssertionError(f"unexpected request: {params}")


def page(title: str, qid: str, **props: Any) -> dict[str, Any]:
    return {"title": title, "pageid": 1, "pageprops": {"wikibase_item": qid, **props}}


class TestNames(unittest.TestCase):
    def test_word_order_is_kept(self) -> None:
        self.assertNotEqual(W.strict_name("Miami University"), W.strict_name("University of Miami"))

    def test_case_accents_and_punctuation_are_not(self) -> None:
        self.assertEqual(W.strict_name("UNIVERSIDAD DE MÁLAGA"), W.strict_name("Universidad de Malaga"))
        self.assertEqual(W.strict_name("Texas A&M University"), W.strict_name("Texas A and M University"))
        self.assertEqual(W.strict_name("The University of Tokyo"), W.strict_name("University of Tokyo"))

    def test_an_appended_short_form_is_dropped(self) -> None:
        self.assertIn("Massachusetts Institute of Technology", W.name_variants("Massachusetts Institute of Technology (MIT)"))
        self.assertIn(
            "Skolkovo Institute of Science and Technology",
            W.name_variants("Skolkovo Institute of Science and Technology Skoltech"),
        )

    def test_a_word_that_distinguishes_two_universities_is_not(self) -> None:
        # "UWM" is not spelled by "University of Wisconsin": it names a campus.
        self.assertEqual(["University of Wisconsin UWM"], W.name_variants("University of Wisconsin UWM"))
        self.assertEqual(["Indian Institute of Technology Bombay"], W.name_variants("Indian Institute of Technology Bombay"))
        self.assertEqual(["University of California, Berkeley"], W.name_variants("University of California, Berkeley"))

    def test_display_name_spellings_come_first(self) -> None:
        u = university("Amherst College", other_names=["University of Massachusetts"])
        self.assertEqual(["Amherst College", "University of Massachusetts"], u.names())
        self.assertEqual(["Amherst College"], u.own_names())


class TestSourceIds(unittest.TestCase):
    def test_keys_are_the_publishers_own_slugs(self) -> None:
        self.assertEqual(["university-oxford"], W.source_id_keys("QS", "/universities/university-oxford", None))
        self.assertEqual(
            ["uppsala-university"], W.source_id_keys("THE", "551", "/world-university-rankings/uppsala-university")
        )
        self.assertEqual(["sunway-university"], W.source_id_keys("ARWU", "arwu:sunway-university", None))

    def test_an_id_that_is_not_a_slug_gives_no_key(self) -> None:
        self.assertEqual([], W.source_id_keys("QS", "/node/309745", None))
        self.assertEqual([], W.source_id_keys("QS", "N/A", None))
        self.assertEqual([], W.source_id_keys("THE", "551", None))

    def test_one_article_named_by_every_id_is_a_match(self) -> None:
        mit = W.Candidate("Q49108", "Massachusetts Institute of Technology")
        indexes = {"QS": {"mit": [mit]}, "THE": {"massachusetts-institute-technology": [mit]}}
        u = university("MIT", source_ids={"QS": ["mit"], "THE": ["massachusetts-institute-technology"]})
        match, conflict = W.match_by_source_id(u, indexes)
        self.assertIsNone(conflict)
        self.assertEqual(("Q49108", "wikidata_source_id"), (match.wikidata_id, match.method))
        self.assertEqual(["QS:mit", "THE:massachusetts-institute-technology"], match.evidence["source_ids"])

    def test_ids_naming_different_articles_match_nothing(self) -> None:
        indexes = {
            "QS": {"umass-amherst": [W.Candidate("Q15142", "University of Massachusetts Amherst")]},
            "THE": {"university-massachusetts": [W.Candidate("Q1061122", "University of Massachusetts")]},
        }
        u = university("UMass Amherst", source_ids={"QS": ["umass-amherst"], "THE": ["university-massachusetts"]})
        match, conflict = W.match_by_source_id(u, indexes)
        self.assertIsNone(match)
        self.assertIn("different articles", conflict)

    def test_an_id_two_wikidata_items_claim_identifies_neither(self) -> None:
        indexes = {"QS": {"x": [W.Candidate("Q1", "A"), W.Candidate("Q2", "B")]}}
        self.assertEqual((None, None), W.match_by_source_id(university("X", source_ids={"QS": ["x"]}), indexes))


class TestTitleResolution(unittest.TestCase):
    def test_exact_title_and_whole_article_redirect_resolve(self) -> None:
        client = FakeClient(
            pages={"University of Trier": page("University of Trier", "Q1")},
            redirects={"Universität Trier": "University of Trier"},
        )
        resolved = W.resolve_titles(client, ["University of Trier", "Universität Trier", "No Such University"])
        self.assertEqual({"University of Trier", "Universität Trier"}, set(resolved))
        self.assertEqual("Q1", resolved["Universität Trier"].wikidata_id)

    def test_a_redirect_into_a_section_is_refused(self) -> None:
        # How a college points at the paragraph about it in its parent's article.
        client = FakeClient(
            pages={"University of London": page("University of London", "Q1")},
            redirects={"Heythrop College": {"to": "University of London", "tofragment": "Former colleges"}},
        )
        self.assertEqual({}, W.resolve_titles(client, ["Heythrop College"]))

    def test_a_disambiguation_page_is_refused(self) -> None:
        client = FakeClient(pages={"National University": page("National University", "Q1", disambiguation="")})
        self.assertEqual({}, W.resolve_titles(client, ["National University"]))

    def test_a_name_holding_the_title_separator_is_never_sent(self) -> None:
        # One such name used to make a 51-title batch, which the API refuses whole.
        client = FakeClient(pages={"Lincoln University": page("Lincoln University", "Q1")})
        resolved = W.resolve_titles(client, ["University of Canterbury | Te Whare Wānanga", "Lincoln University"])
        self.assertEqual(["Lincoln University"], list(resolved))
        self.assertEqual([["Lincoln University"]], client.title_batches)


class TestValidation(unittest.TestCase):
    def test_same_name_in_another_country_is_refused(self) -> None:
        u = university("Xavier University", "Philippines")
        candidate = W.Candidate("Q1", "Xavier University")
        chosen, reason = W._pick_validated(u, [("Xavier University", candidate)], {"Q1": entity("Q1", "Xavier University")})
        self.assertIsNone(chosen)
        self.assertIn("country is United States, not Philippines", reason)

    def test_a_page_that_is_not_an_institution_is_refused(self) -> None:
        u = university("Changzhou University", "China (mainland)")
        city = entity("Q1", "Changzhou", country="People's Republic of China", types=["prefecture-level city of China"])
        chosen, reason = W._pick_validated(u, [("Changzhou University", W.Candidate("Q1", "Changzhou"))], {"Q1": city})
        self.assertIsNone(chosen)
        self.assertIn("not an educational institution", reason)

    def test_warehouse_country_names_are_read_as_wikidata_has_them(self) -> None:
        for ours, theirs in (
            ("China (mainland)", "People's Republic of China"),
            ("Hong Kong Sar", "Hong Kong"),
            ("Türkiye", "Turkey"),
            ("Czechia", "Czech Republic"),
            ("United States", "United States of America"),
        ):
            with self.subTest(ours=ours):
                self.assertTrue(W.country_agrees(entity("Q1", "X", country=theirs), ours))
        self.assertFalse(W.country_agrees(entity("Q1", "X", country="India"), "Indonesia"))

    def test_no_country_in_the_warehouse_means_no_match_by_name(self) -> None:
        u = university("N/A", "N A")
        chosen, reason = W._pick_validated(u, [("N/A", W.Candidate("Q1", "N/A"))], {"Q1": entity("Q1", "N/A")})
        self.assertIsNone(chosen)
        self.assertIn("no country", reason)

    def test_the_display_name_outranks_a_source_spelling(self) -> None:
        u = university("University of Massachusetts Amherst", other_names=["University of Massachusetts"])
        entities = {
            "Q15142": entity("Q15142", "University of Massachusetts Amherst"),
            "Q1061122": entity("Q1061122", "University of Massachusetts"),
        }
        options = [
            ("University of Massachusetts", W.Candidate("Q1061122", "University of Massachusetts")),
            ("University of Massachusetts Amherst", W.Candidate("Q15142", "University of Massachusetts Amherst")),
        ]
        chosen, _reason = W._pick_validated(u, options, entities)
        self.assertEqual("Q15142", chosen[1].wikidata_id)

    def test_two_articles_for_one_name_is_an_ambiguity_not_a_choice(self) -> None:
        u = university("Sage University", "India")
        entities = {q: entity(q, "Sage University", country="India") for q in ("Q1", "Q2")}
        options = [("Sage University", W.Candidate("Q1", "SAGE University, Indore")),
                   ("Sage University", W.Candidate("Q2", "SAGE University, Bhopal"))]
        chosen, reason = W._pick_validated(u, options, entities)
        self.assertIsNone(chosen)
        self.assertIn("more than one article", reason)


class TestSections(unittest.TestCase):
    EXTRACT = "\n".join([
        "Lead paragraph one.", "Lead paragraph two.", "",
        "== History ==", "Founded in 1861.", "",
        "=== Early years ===", "Classes began in 1865.", "",
        "== Rankings ==", "",
        "== Campus ==", "",
        "=== Main campus ===", "By the river.", "",
        "== See also ==", "List of universities",
        "== References ==", "",
        "=== Citations ===", "Smith 2001.",
        "== External links ==", "Official website",
    ])

    def test_lead_then_sections_with_their_levels(self) -> None:
        sections = W.split_sections(self.EXTRACT)
        self.assertEqual(
            [(1, None), (2, "History"), (3, "Early years"), (2, "Campus"), (3, "Main campus")],
            [(s["level"], s["heading"]) for s in sections],
        )
        self.assertEqual("Lead paragraph one.\nLead paragraph two.", sections[0]["text"])

    def test_apparatus_sections_go_with_their_subsections(self) -> None:
        text = json.dumps(W.split_sections(self.EXTRACT))
        for gone in ("See also", "References", "Citations", "Smith 2001", "External links", "Official website"):
            self.assertNotIn(gone, text)

    def test_an_emptied_section_goes_but_an_empty_parent_of_text_stays(self) -> None:
        headings = [s["heading"] for s in W.split_sections(self.EXTRACT)]
        self.assertNotIn("Rankings", headings)  # held only a table
        self.assertIn("Campus", headings)  # empty itself, but "Main campus" has text

    def test_an_article_with_no_text_has_no_sections(self) -> None:
        self.assertEqual([], W.split_sections("== References ==\nSmith 2001."))


class TestArticles(unittest.TestCase):
    PAGE = {
        "pageid": 18879, "title": "Massachusetts Institute of Technology",
        "canonicalurl": "https://en.wikipedia.org/wiki/Massachusetts_Institute_of_Technology",
        "pageprops": {"wikibase_item": "Q49108"},
        "revisions": [{"revid": 123, "timestamp": "2026-10-01T00:00:00Z"}],
        "extract": "MIT is a university.\n== History ==\nFounded in 1861.",
    }
    MATCHES = {"matched": [{"wikidata_id": "Q49108", "title": "Massachusetts Institute of Technology"}]}

    def test_an_article_keeps_the_revision_it_was_read_at(self) -> None:
        article = W.fetch_article(FakeClient(extract=self.PAGE), "Massachusetts Institute of Technology")
        self.assertEqual((123, "2026-10-01T00:00:00Z"), (article["revision_id"], article["revision_timestamp"]))
        self.assertEqual(self.PAGE["canonicalurl"], article["url"])
        self.assertEqual(2, len(article["sections"]))

    def test_fetch_stores_and_reads_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fetched, problems = W.fetch_articles(
                self.MATCHES, FakeClient(extract=self.PAGE), Path(tmp), fetched_at="2026-10-12T00:00:00Z"
            )
            self.assertEqual((1, []), (fetched, problems))
            stored = W.read_articles(Path(tmp))
            self.assertEqual("2026-10-12T00:00:00Z", stored["Q49108"]["fetched_at"])

    def test_a_title_now_held_by_another_item_is_not_stored(self) -> None:
        # The page was moved and its old title reused for something else.
        moved = {**self.PAGE, "pageprops": {"wikibase_item": "Q999"}}
        with tempfile.TemporaryDirectory() as tmp:
            fetched, problems = W.fetch_articles(
                self.MATCHES, FakeClient(extract=moved), Path(tmp), fetched_at="2026-10-12T00:00:00Z"
            )
            self.assertEqual(0, fetched)
            self.assertIn("now belongs to Q999", problems[0])
            self.assertEqual({}, W.read_articles(Path(tmp)))

    def test_a_disambiguation_page_is_not_an_article(self) -> None:
        dab = {**self.PAGE, "pageprops": {"wikibase_item": "Q49108", "disambiguation": ""}}
        self.assertIsNone(W.fetch_article(FakeClient(extract=dab), "X"))

    def test_the_same_articles_write_the_same_bytes(self) -> None:
        article = W.fetch_article(FakeClient(extract=self.PAGE), "X") | {"fetched_at": "2026-10-12T00:00:00Z"}
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            (path_a,) = W.write_articles(Path(a), {"Q49108": article})
            (path_b,) = W.write_articles(Path(b), {"Q49108": dict(reversed(list(article.items())))})
            self.assertEqual(path_a.read_bytes(), path_b.read_bytes())

    def test_an_article_no_longer_matched_leaves_the_store(self) -> None:
        article = W.fetch_article(FakeClient(extract=self.PAGE), "X") | {"fetched_at": "2026-10-12T00:00:00Z"}
        with tempfile.TemporaryDirectory() as tmp:
            W.write_articles(Path(tmp), {"Q49108": article})
            W.fetch_articles({"matched": []}, FakeClient(), Path(tmp), fetched_at="2026-10-13T00:00:00Z")
            self.assertEqual({}, W.read_articles(Path(tmp)))


class TestTheCommittedFiles(unittest.TestCase):
    """``matches.json`` and the article shards are loaded into the warehouse as they are, so they must agree."""

    @classmethod
    def setUpClass(cls) -> None:
        if not W.MATCHES_PATH.exists():
            raise unittest.SkipTest("no committed Wikipedia matches")
        cls.matches = json.loads(W.MATCHES_PATH.read_text(encoding="utf-8"))
        cls.articles = W.read_articles(W.ARTICLES_DIR)

    def test_counts_describe_the_lists(self) -> None:
        counts = self.matches["counts"]
        self.assertEqual(counts["matched"], len(self.matches["matched"]))
        self.assertEqual(counts["unmatched"], len(self.matches["unmatched"]))
        self.assertEqual(counts["universities"], counts["matched"] + counts["unmatched"])
        self.assertEqual(sum(counts["by_method"].values()), counts["matched"])

    def test_a_university_is_matched_once_or_unmatched_never_both(self) -> None:
        matched = [row["canonical_slug"] for row in self.matches["matched"]]
        unmatched = [row["canonical_slug"] for row in self.matches["unmatched"]]
        self.assertEqual(len(matched), len(set(matched)))
        self.assertEqual(set(), set(matched) & set(unmatched))

    def test_every_unmatched_university_says_why(self) -> None:
        self.assertEqual([], [row["canonical_slug"] for row in self.matches["unmatched"] if not row["reason"].strip()])

    def test_every_method_is_one_the_schema_allows(self) -> None:
        ddl = (PACKAGE_ROOT / "crawlernest-schema" / "wikipedia_article_postgresql.sql").read_text(encoding="utf-8")
        allowed = set(re.findall(r"'(\w+)'", re.search(r"match_method IN \(([^)]*)\)", ddl).group(1)))
        self.assertLessEqual({row["method"] for row in self.matches["matched"]}, allowed)

    def test_no_stored_article_is_unmatched(self) -> None:
        self.assertEqual(set(), set(self.articles) - {row["wikidata_id"] for row in self.matches["matched"]})

    def test_almost_every_match_has_its_text(self) -> None:
        # A few pages are deleted or moved between matching and fetching; a large gap means the fetch was not run.
        missing = [row["title"] for row in self.matches["matched"] if row["wikidata_id"] not in self.articles]
        self.assertLessEqual(len(missing), max(5, len(self.matches["matched"]) // 100), missing[:20])

    def test_every_article_can_be_attributed(self) -> None:
        for qid, article in self.articles.items():
            with self.subTest(wikidata_id=qid):
                self.assertTrue(article["url"].startswith("https://en.wikipedia.org/wiki/"))
                self.assertIsInstance(article["revision_id"], int)
                self.assertTrue(article["sections"] and all(s["text"] or s["heading"] for s in article["sections"]))


if __name__ == "__main__":
    unittest.main()
