"""Tests for arwu_crawler.py utility functions (ARWU global rankings acquisition)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

for mod in (
    "crawlernest-core",
    "crawlernest-extractors",
    "crawlernest-jobs",
    "crawlernest-db-writer",
    "crawlernest-analytics",
):
    p = str(PACKAGE_ROOT / mod)
    if p not in sys.path:
        sys.path.insert(0, p)

from arwu_crawler import (  # noqa: E402
    _candidate_pages,
    _extract_rows_from_html_tables,
    _raw_row,
    _rows_from_payload,
    _to_float,
    _to_int,
    _year_of_page,
    arwu_source_id,
)


class TestArwuParsingHelpers(unittest.TestCase):
    def test_to_int(self):
        self.assertEqual(_to_int("7"), 7)
        self.assertEqual(_to_int("101-150"), 101)
        self.assertIsNone(_to_int("N/A"))

    def test_to_float(self):
        self.assertAlmostEqual(_to_float("100.0"), 100.0)
        self.assertAlmostEqual(_to_float("72.3%"), 72.3)
        self.assertIsNone(_to_float(""))

    def test_candidate_pages_are_only_the_requested_edition(self):
        self.assertEqual(_candidate_pages(2026), ["https://www.shanghairanking.com/rankings/arwu/2026"])


class TestArwuHtmlExtraction(unittest.TestCase):
    def test_extract_rows_from_html_table(self):
        html = """
        <table>
          <tr>
            <th>World Rank</th>
            <th>Institution</th>
            <th>National/Regional Rank</th>
            <th>Total Score</th>
          </tr>
          <tr>
            <td>1</td>
            <td><a href="/institutions/harvard-university">Harvard University</a><span>United States</span></td>
            <td>1</td>
            <td>100.0</td>
          </tr>
          <tr>
            <td>6</td>
            <td><a href="/institutions/university-of-oxford">University of Oxford</a><span>United Kingdom</span></td>
            <td>2</td>
            <td>61.0</td>
          </tr>
        </table>
        """
        rows = _extract_rows_from_html_tables(html, 2025, "https://www.shanghairanking.com/rankings/arwu/2025")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "Harvard University")
        self.assertEqual(rows[0]["country"], "United States")
        self.assertEqual(rows[0]["rank"], 1)
        self.assertAlmostEqual(rows[0]["score"], 100.0)
        self.assertEqual(rows[0]["ranking_type"], "world")
        self.assertEqual(rows[1]["url"], "https://www.shanghairanking.com/institutions/university-of-oxford")

    def test_skip_rows_without_valid_rank(self):
        html = """
        <table>
          <tr>
            <th>World Rank</th>
            <th>Institution</th>
            <th>Total Score</th>
          </tr>
          <tr>
            <td>N/A</td>
            <td><a href="/institutions/example">Example University</a><span>Exampleland</span></td>
            <td>12.0</td>
          </tr>
        </table>
        """
        rows = _extract_rows_from_html_tables(html, 2025, "https://www.shanghairanking.com/rankings/arwu/2025")
        self.assertEqual(rows, [])


def _payload(*, rank: str, name: str, region: str, score: str, up: str | None = None) -> str:
    """A minimal Nuxt JSONP payload in the shape the live page serves.

    The last argument is left unquoted on purpose: the crawler strips trailing
    `);"` characters off the argument list, which would eat a closing quote.
    ``univCode`` is an empty string, as it is on every live entry.
    """
    up_arg = "void 0" if up is None else f'"{up}"'
    return (
        '__NUXT_JSONP__("/rankings/arwu/2026", (function(a,b,c,d,e,f,g,h,i){'
        "return {data:[{ranking:a,univNameEn:b,univUp:c,univLogo:d,region:e,"
        "regionLogo:f,regionRanking:g,univCode:h,score:i}]}"
        f'}}("{rank}","{name}",{up_arg},"logo.png","{region}","flag.png","1","",{score})));'
    )


def _payload_of(entries: list[tuple[str, str, str]]) -> str:
    """Several ``(rank, name, univUp)`` entries, each in its own parameters."""
    letters = [f"p{i}" for i in range(len(entries) * 3)]
    objects, args = [], []
    for i, (rank, name, up) in enumerate(entries):
        r, n, u = letters[3 * i: 3 * i + 3]
        objects.append(
            f"{{ranking:{r},univNameEn:{n},univUp:{u},univLogo:lg,region:rg,"
            f"regionLogo:lg,regionRanking:rr,univCode:cd,score:sc}}"
        )
        args += [f'"{rank}"', f'"{name}"', f'"{up}"']
    params = ",".join(letters + ["lg", "rg", "rr", "cd", "sc"])
    values = ",".join(args + ['"logo.png"', '"Japan"', '"1"', '""', "50.0"])
    return (
        f'__NUXT_JSONP__("/rankings/arwu/2026", (function({params}){{'
        f"return {{data:[{','.join(objects)}]}}"
        f"}}({values})));"
    )


class TestArwuPayloadExtraction(unittest.TestCase):
    """The payload path serves ~1,000 rows against the rendered table's 30, so
    it is the one that actually runs -- and it had no coverage at all."""

    PAGE = "https://www.shanghairanking.com/rankings/arwu/2026"

    def _one_row(self, **kwargs):
        rows = _rows_from_payload(_payload(**kwargs), 2026, self.PAGE)
        self.assertEqual(1, len(rows))
        return rows[0]

    def test_payload_row_is_normalized(self):
        row = self._one_row(
            rank="1", name="Harvard University", region="United States", score="100.0"
        )
        self.assertEqual("Harvard University", row["name"])
        self.assertEqual("United States", row["country"])
        self.assertEqual(1, row["rank"])
        self.assertAlmostEqual(100.0, row["score"])

    def test_payload_row_keeps_the_source_row(self):
        # source_university_mapping.metadata carries this through to the entity
        # review screen, which reads raw_row.name and raw_row.location. Without
        # it a reviewer sees the normalized name and no country for ARWU.
        raw = self._one_row(
            rank="1", name="Harvard University", region="United States", score="100.0"
        )["metadata"]["raw_row"]
        self.assertEqual("Harvard University", raw["name"])
        self.assertEqual("United States", raw["location"])

    def test_raw_row_is_a_mapping_not_a_list(self):
        # It used to be a list of cell strings on the other path, which made
        # metadata #>> '{raw_row,name}' return NULL rather than a name.
        raw = self._one_row(rank="1", name="Harvard University", region="US", score="100.0")[
            "metadata"
        ]["raw_row"]
        self.assertIsInstance(raw, dict)

    def test_banded_rank_is_preserved_verbatim(self):
        row = self._one_row(
            rank="101-150", name="Banded University", region="Japan", score="50.0"
        )
        self.assertEqual(101, row["rank"], "the sortable rank takes the band's floor")
        self.assertEqual("101-150", row["rank_display"])
        self.assertEqual("101-150", row["metadata"]["raw_row"]["rank"])

    def test_malformed_payload_yields_nothing(self):
        self.assertEqual([], _rows_from_payload("not a payload", 2026, self.PAGE))


class TestRawRowShape(unittest.TestCase):
    """Both extraction paths must produce one shape, or downstream readers have
    to know which path a row came from."""

    def test_blank_fields_become_null_rather_than_empty_strings(self):
        raw = _raw_row(name="Example University", location="  ", rank_display="", score_text=None)
        self.assertEqual("Example University", raw["name"])
        self.assertIsNone(raw["location"])
        self.assertIsNone(raw["rank"])
        self.assertIsNone(raw["score"])

    def test_values_are_stringified_and_trimmed(self):
        raw = _raw_row(name="Example", location=" Japan ", rank_display=7, score_text=61.5)
        self.assertEqual("Japan", raw["location"])
        self.assertEqual("7", raw["rank"])
        self.assertEqual("61.5", raw["score"])

    def test_html_and_payload_paths_agree_on_keys(self):
        html = """
        <table>
          <tr><th>World Rank</th><th>Institution</th><th>Total Score</th></tr>
          <tr>
            <td>1</td>
            <td><a href="/institutions/harvard">Harvard University</a><span>United States</span></td>
            <td>100.0</td>
          </tr>
        </table>
        """
        html_row = _extract_rows_from_html_tables(
            html, 2026, "https://www.shanghairanking.com/rankings/arwu/2026"
        )[0]
        payload_row = _rows_from_payload(
            _payload(rank="1", name="Harvard University", region="United States", score="100.0"),
            2026,
            "https://www.shanghairanking.com/rankings/arwu/2026",
        )[0]

        self.assertEqual(
            sorted(html_row["metadata"]["raw_row"]),
            sorted(payload_row["metadata"]["raw_row"]),
        )
        self.assertEqual(
            html_row["metadata"]["raw_row"]["name"],
            payload_row["metadata"]["raw_row"]["name"],
        )

    def test_html_path_still_keeps_the_underlying_cells(self):
        html = """
        <table>
          <tr><th>World Rank</th><th>Institution</th><th>Total Score</th></tr>
          <tr>
            <td>1</td>
            <td><a href="/institutions/harvard">Harvard University</a><span>United States</span></td>
            <td>100.0</td>
          </tr>
        </table>
        """
        row = _extract_rows_from_html_tables(
            html, 2026, "https://www.shanghairanking.com/rankings/arwu/2026"
        )[0]
        self.assertIn("100.0", row["metadata"]["raw_cells"])


class TestEntityIdIsTheSourceSlug(unittest.TestCase):
    """warehouse.mapping_review keys human decisions on this id.

    It used to embed the edition year on the payload path and be a profile URL
    on the HTML path, so a new edition -- or a payload parse falling back --
    silently orphaned every decision. It is now ShanghaiRanking's own slug on
    both paths, with no year in it.
    """

    PAGE = "https://www.shanghairanking.com/rankings/arwu/2026"

    def test_payload_id_is_the_univ_up_slug(self):
        row = _rows_from_payload(
            _payload(rank="1", name="Harvard University", region="US", score="100.0",
                     up="harvard-university"),
            2026,
            self.PAGE,
        )[0]
        self.assertEqual("arwu:harvard-university", row["id"])
        self.assertEqual("univ_up", row["metadata"]["id_basis"])

    def test_id_carries_no_year(self):
        ids = {
            _rows_from_payload(
                _payload(rank="1", name="Harvard University", region="US", score="1",
                         up="harvard-university"),
                year,
                f"https://www.shanghairanking.com/rankings/arwu/{year}",
            )[0]["id"]
            for year in (2025, 2026)
        }
        self.assertEqual({"arwu:harvard-university"}, ids,
                         "the same institution must keep one id across editions")

    def test_a_renamed_institution_keeps_its_slug(self):
        # Observed live: ARWU prints the new name over the old slug.
        row = _rows_from_payload(
            _payload(rank="151-200", name="Institute of Science Tokyo", region="Japan", score="1",
                     up="tokyo-institute-of-technology"),
            2026,
            self.PAGE,
        )[0]
        self.assertEqual("arwu:tokyo-institute-of-technology", row["id"])

    def test_missing_slug_falls_back_to_a_marked_name_derived_id(self):
        row = _rows_from_payload(
            _payload(rank="1", name="Harvard University", region="US", score="1"),
            2026,
            self.PAGE,
        )[0]
        self.assertEqual("arwu:name:harvard-university", row["id"])
        self.assertEqual("name", row["metadata"]["id_basis"])

    def test_html_and_payload_paths_emit_the_same_id(self):
        # The fallback firing used to change every id at once.
        for link in ("/institution/harvard-university", "/institutions/harvard-university"):
            html = f"""
            <table>
              <tr><th>World Rank</th><th>Institution</th><th>Total Score</th></tr>
              <tr><td>1</td><td><a href="{link}">Harvard University</a><span>United States</span></td>
                  <td>100.0</td></tr>
            </table>
            """
            html_row = _extract_rows_from_html_tables(html, 2026, self.PAGE)[0]
            self.assertEqual("arwu:harvard-university", html_row["id"], link)
            self.assertEqual(
                "https://www.shanghairanking.com" + link, html_row["url"],
                "the profile link is still kept as the url",
            )

    def test_shared_names_are_two_institutions_and_repeats_are_one(self):
        rows = _rows_from_payload(
            _payload_of(
                [
                    ("51", "Northeastern University", "northeastern-university"),
                    ("401-500", "Northeastern University", "northeastern-university-china"),
                    ("51", "Northeastern University", "northeastern-university"),
                ]
            ),
            2026,
            self.PAGE,
        )
        self.assertEqual(
            ["arwu:northeastern-university", "arwu:northeastern-university-china"],
            [r["id"] for r in rows],
        )

    def test_id_builder_forms(self):
        self.assertEqual("arwu:x-y", arwu_source_id("x-y", "ignored"))
        self.assertEqual("arwu:name:x-y", arwu_source_id(None, "X  Y"))


class TestPageYearIsRecorded(unittest.TestCase):
    """Rows must carry the year of the page they came from, not the year asked for.

    The crawler falls back two years when a table is not published yet. Stamping
    the requested year onto rows from an older page is how
    arwu_rankings_2026.json came to hold the 2025 table -- byte-identical ranks
    and scores to arwu_rankings_2025.json, from the same source_page, under a
    label that made it look like a new edition. Ingesting that would have put a
    year-old third source into the 2026 aggregation and taken those universities
    to "high" confidence on it.
    """

    def test_year_comes_from_the_url_that_was_fetched(self):
        self.assertEqual(_year_of_page("https://x/rankings/arwu/2025", 2026), 2025)
        self.assertEqual(_year_of_page("https://x/rankings/arwu/2026", 2026), 2026)

    def test_requested_year_is_the_fallback_only_when_the_url_says_nothing(self):
        self.assertEqual(_year_of_page("https://x/rankings/arwu/", 2026), 2026)
        self.assertEqual(_year_of_page("", 2024), 2024)

    def test_no_fallback_to_an_older_edition(self):
        """A request for one edition must not produce another, even correctly labelled."""
        years = [int(p.rsplit("/", 1)[-1]) for p in _candidate_pages(2026)]
        self.assertEqual(years, [2026])


if __name__ == "__main__":
    unittest.main()
