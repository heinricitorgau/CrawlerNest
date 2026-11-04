"""US federal institutional data: which UNITID a university gets, and what a value's status means.

Most of these are refusals. A university is tied to a UNITID only through identifiers,
so the tests that matter are the ones where an identifier is missing, doubled or shared.
The rest hold the value statuses apart: privacy-suppressed, imputed, not available and
not applicable are different things, and none of them is zero. No test touches the network.

The PostgreSQL test is opt-in, like the others:

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
      python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import unittest
import zipfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
for _p in (str(PACKAGE_ROOT / "crawlernest-jobs"), str(PACKAGE_ROOT.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import us_institution_loader as L  # noqa: E402

DDL = (PACKAGE_ROOT / "crawlernest-schema" / "us_institution_postgresql.sql").read_text(encoding="utf-8")


def ddl_values(column: str) -> set[str]:
    return set(re.findall(r"'(\w+)'", re.search(rf"{column} IN \(([^)]*)\)", DDL).group(1)))


def scorecard_dictionary(**periods: str) -> L.ScorecardDictionary:
    base = {m.field: "Fall 2024, reported in IPEDS DCY2024-25" for m in L.SCORECARD_METRICS}
    base.update({"NPT4_PUB": "AcadYr 2024-25", "NPT4_PRIV": "AcadYr 2024-25"})
    base.update(periods)
    return L.ScorecardDictionary(base, {"CONTROL": {"1": "Public", "2": "Private nonprofit"}}, "Released October 15, 2026")


def ipeds_dictionary(title: str = "Admissions Data File, 2023-24 (Provisional release)") -> L.IpedsDictionary:
    return L.IpedsDictionary(
        title,
        {"ADMCON7": {"1": "Required to be considered for admission"}, "CARNEGIERSCH": {"1": "Research 1"}},
        {"R": "Reported", "A": "Not applicable", "B": "Institution left item blank",
         "L": "Imputed using the Group Median procedure", "C": "Analyst corrected reported value"},
    )


METRIC = {m.key: m for m in L.SCORECARD_METRICS + L.IPEDS_METRICS}


class TestReadingFiles(unittest.TestCase):
    def test_a_csv_loses_its_bom_and_the_padding_ipeds_leaves(self) -> None:
        data = "﻿UNITID,ACTMT75   ,F1SYSNAM\r\n166683,36,-2        \r\n".encode("utf-8")
        self.assertEqual([{"UNITID": "166683", "ACTMT75": "36", "F1SYSNAM": "-2"}], L.read_csv_rows(data))

    def test_a_zip_member_is_found_whatever_its_case(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("adm2023.csv", "UNITID\n1\n")
        self.assertEqual(b"UNITID\n1\n", L.zip_member(buffer.getvalue(), "ADM2023.csv"))

    def test_a_workbook_is_read_with_the_standard_library(self) -> None:
        buffer = io.BytesIO()
        main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("xl/workbook.xml", f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets>'
                                          '<sheet name="Most_Recent_Inst_Cohort_Map" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels",
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{main}"><si><t>ADM_RATE</t></si><si><t>Fall 2024</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{main}"><sheetData><row r="2">'
                                                   '<c r="A2" t="s"><v>0</v></c><c r="B2" t="s"><v>1</v></c>'
                                                   '<c r="C2"><v>7</v></c></row></sheetData></worksheet>')
        sheets = L.read_xlsx(buffer.getvalue())
        self.assertEqual([{"A": "ADM_RATE", "B": "Fall 2024", "C": "7"}], sheets["Most_Recent_Inst_Cohort_Map"])

    def test_an_ipeds_title_is_taken_verbatim_with_its_release(self) -> None:
        sheets = {
            "Introduction": [{"A": "File Documentation for the Admissions Data File, 2023-24"}, {"A": "(Provisional release)"}],
            "Frequencies": [{"B": "varname"}, {"B": "ADMCON7", "C": "5", "D": "Not required for admission,  but considered"}],
            "Imputation values": [{"A": "Code values for item imputation variables Xvarname"}, {"A": "R", "B": "Reported"},
                                  {"A": "Z", "B": "Implied zero;"}],
        }
        d = L.parse_ipeds_dictionary(sheets)
        self.assertEqual("Admissions Data File, 2023-24 (Provisional release)", d.title)
        self.assertEqual("Not required for admission, but considered", d.labels["ADMCON7"]["5"])
        self.assertEqual({"R": "Reported", "Z": "Implied zero"}, d.flags)


class TestScorecardValues(unittest.TestCase):
    def value(self, key: str, raw: str) -> dict:
        m = METRIC[key]
        return L.scorecard_value(m, raw, field=m.field, dictionary=scorecard_dictionary(), release="release")

    def test_privacy_suppressed_is_not_missing_and_not_zero(self) -> None:
        row = self.value("median_earnings_10yr", "PS")
        self.assertEqual(("privacy_suppressed", None), (row["status"], row["value_number"]))

    def test_na_and_blank_are_not_available(self) -> None:
        self.assertEqual("not_available", self.value("admission_rate", "NA")["status"])
        self.assertEqual("not_available", self.value("admission_rate", "")["status"])

    def test_a_number_keeps_its_exact_decimal_text(self) -> None:
        self.assertEqual("0.0455", self.value("admission_rate", "0.0455")["value_number"])
        self.assertEqual("85960", self.value("cost_of_attendance", "85960.0")["value_number"])

    def test_a_code_carries_the_dictionary_label(self) -> None:
        row = self.value("control", "2")
        self.assertEqual(("2", "Private nonprofit"), (row["value_number"], row["value_text"]))

    def test_every_value_carries_the_period_the_dictionary_gives_its_field(self) -> None:
        dictionary = scorecard_dictionary(MD_EARN_WNE_P10="Treasury AY2011-12, AY2012-13 pooled cohort")
        m = METRIC["median_earnings_10yr"]
        row = L.scorecard_value(m, "100", field=m.field, dictionary=dictionary, release="r")
        self.assertEqual("Treasury AY2011-12, AY2012-13 pooled cohort", row["period"])

    def test_a_field_the_dictionary_does_not_date_is_refused(self) -> None:
        m = METRIC["admission_rate"]
        with self.assertRaises(ValueError):
            L.scorecard_value(m, "0.5", field=m.field, dictionary=L.ScorecardDictionary({}, {}, ""), release="r")

    def test_net_price_is_read_from_the_field_for_the_institutions_control(self) -> None:
        public = {m.field: "1" for m in L.SCORECARD_METRICS} | {"CONTROL": "1", "NPT4_PUB": "14538", "NPT4_PRIV": "NA"}
        private = public | {"CONTROL": "2", "NPT4_PUB": "NA", "NPT4_PRIV": "14815"}
        for row, field, value in ((public, "NPT4_PUB", "14538"), (private, "NPT4_PRIV", "14815")):
            net = [m for m in L.scorecard_metrics(row, scorecard_dictionary(), "r") if m["key"] == "average_net_price"][0]
            self.assertEqual((field, value, "reported"), (net["field"], net["value_number"], net["status"]))


class TestIpedsValues(unittest.TestCase):
    def value(self, key: str, row: dict | None) -> dict:
        return L.ipeds_value(METRIC[key], row, ipeds_dictionary(), file_label="IPEDS ADM2023")

    def test_a_reported_flag_is_reported(self) -> None:
        row = self.value("applicants_total", {"APPLCN": "26904", "XAPPLCN": "R"})
        self.assertEqual(("reported", "26904"), (row["status"], row["value_number"]))

    def test_an_imputed_or_corrected_value_is_kept_and_labelled_with_ncess_flag(self) -> None:
        for flag, label in (("L", "Imputed using the Group Median procedure"), ("C", "Analyst corrected reported value")):
            row = self.value("applicants_total", {"APPLCN": "500", "XAPPLCN": flag})
            self.assertEqual(("imputed", "500", f"{flag}: {label}"), (row["status"], row["value_number"], row["status_detail"]))

    def test_not_applicable_and_blank_are_told_apart(self) -> None:
        self.assertEqual("not_applicable", self.value("applicants_total", {"APPLCN": "", "XAPPLCN": "A"})["status"])
        self.assertEqual("not_available", self.value("applicants_total", {"APPLCN": "", "XAPPLCN": "B"})["status"])
        self.assertEqual("not_applicable", self.value("carnegie_research_2025", {"CARNEGIERSCH": "-2"})["status"])

    def test_an_institution_missing_from_the_file_is_not_available_and_says_so(self) -> None:
        row = self.value("applicants_total", None)
        self.assertEqual("not_available", row["status"])
        self.assertIn("no row in IPEDS ADM2023", row["status_detail"])

    def test_a_code_carries_its_label(self) -> None:
        row = self.value("test_score_policy", {"ADMCON7": "1"})
        self.assertEqual(("1", "Required to be considered for admission"), (row["value_number"], row["value_text"]))

    def test_the_period_is_the_files_own_title(self) -> None:
        self.assertEqual("Admissions Data File, 2023-24 (Provisional release)",
                         self.value("applicants_total", {"APPLCN": "1", "XAPPLCN": "R"})["period"])

    def test_a_standalone_institution_has_no_system_name(self) -> None:
        tables = {"hd": {"1": {"F1SYSTYP": "2", "F1SYSNAM": "-2"}}, "effy": {}, "adm": {}}
        dictionaries = {t: ipeds_dictionary() for t in ("hd", "effy", "adm")}
        labels = {t: f"IPEDS {t}" for t in ("hd", "effy", "adm")}
        rows = {m["key"]: m for m in L.ipeds_metrics("1", tables, dictionaries, labels)}
        self.assertEqual("not_applicable", rows["system_name"]["status"])

    def test_the_two_enrollment_figures_read_their_own_level_rows(self) -> None:
        tables = {"hd": {}, "adm": {}, "effy": {("1", "1"): {"EFYTOTLT": "12915", "XEYTOTLT": "R"},
                                                ("1", "4"): {"EFYTOTLT": "8127", "XEYTOTLT": "R"}}}
        dictionaries = {t: ipeds_dictionary() for t in ("hd", "effy", "adm")}
        rows = {m["key"]: m for m in L.ipeds_metrics("1", tables, dictionaries, {t: t for t in ("hd", "effy", "adm")})}
        self.assertEqual("12915", rows["total_enrollment_12mo"]["value_number"])
        self.assertEqual("8127", rows["graduate_enrollment_12mo"]["value_number"])

    def test_a_value_and_a_status_that_says_there_is_none_cannot_be_written_together(self) -> None:
        with self.assertRaises(ValueError):
            L.value_row(METRIC["admission_rate"], status="not_available", number="0.5", period="p", release="r")
        with self.assertRaises(ValueError):
            L.value_row(METRIC["admission_rate"], status="reported", period="p", release="r")


def uni(slug: str) -> L.University:
    return L.University(slug, slug.replace("-", " ").title(), "United States")


class TestMatching(unittest.TestCase):
    def test_one_ipeds_id_on_the_universitys_own_wikidata_item_is_a_match(self) -> None:
        report = L.build_matches([uni("mit")], {"mit": "Q49108"}, {"Q49108": ["166683"]}, {})
        self.assertEqual([("mit", "166683", "wikidata_ipeds_id")],
                         [(r["canonical_slug"], r["unitid"], r["method"]) for r in report["matched"]])

    def test_no_wikidata_item_is_no_match(self) -> None:
        report = L.build_matches([uni("pace")], {}, {}, {})
        self.assertEqual([], report["matched"])
        self.assertIn("no Wikidata item", report["unmatched"][0]["reason"])

    def test_an_item_without_an_ipeds_id_is_no_match(self) -> None:
        report = L.build_matches([uni("cuny")], {"cuny": "Q762266"}, {}, {})
        self.assertIn("no IPEDS ID", report["unmatched"][0]["reason"])

    def test_an_item_with_two_ipeds_ids_is_no_match(self) -> None:
        report = L.build_matches([uni("x")], {"x": "Q1"}, {"Q1": ["100", "200"]}, {})
        self.assertIn("several IPEDS IDs", report["unmatched"][0]["reason"])

    def test_an_item_two_records_share_attaches_to_neither(self) -> None:
        # One university carried as two records: federal data on either would be a guess.
        report = L.build_matches([uni("ub-suny"), uni("university-at-buffalo")],
                                 {"ub-suny": "Q681025", "university-at-buffalo": "Q681025"}, {"Q681025": ["196088"]}, {})
        self.assertEqual([], report["matched"])
        self.assertEqual(2, len(report["unmatched"]))
        self.assertTrue(all("also matched to" in r["reason"] for r in report["unmatched"]))

    def test_a_unitid_two_records_would_share_attaches_to_neither(self) -> None:
        report = L.build_matches([uni("a"), uni("b")], {"a": "Q1", "b": "Q2"}, {"Q1": ["100"], "Q2": ["100"]}, {})
        self.assertEqual([], report["matched"])
        self.assertTrue(all("would also go to" in r["reason"] for r in report["unmatched"]))

    def test_an_override_can_withhold_a_match_or_make_one(self) -> None:
        report = L.build_matches(
            [uni("st-thomas"), uni("rutgers-nb")],
            {"st-thomas": "Q1"}, {"Q1": ["174914"]},
            {"st-thomas": {"unitid": None, "why": "two universities of this name"},
             "rutgers-nb": {"unitid": "186380", "why": "the New Brunswick campus"}},
        )
        self.assertEqual([("rutgers-nb", "186380", "reviewed_override")],
                         [(r["canonical_slug"], r["unitid"], r["method"]) for r in report["matched"]])
        self.assertIn("withheld by overrides.json", report["unmatched"][0]["reason"])

    def test_a_university_is_matched_or_unmatched_never_both(self) -> None:
        report = L.build_matches([uni("a"), uni("b"), uni("c")], {"a": "Q1", "b": "Q2"}, {"Q1": ["1"]}, {})
        slugs = [r["canonical_slug"] for r in report["matched"] + report["unmatched"]]
        self.assertEqual(sorted(slugs), ["a", "b", "c"])


class TestRecordsFile(unittest.TestCase):
    def test_a_fields_period_is_stated_once_and_put_back_on_read(self) -> None:
        metric = L.value_row(METRIC["admission_rate"], status="reported", number="0.1", period="Fall 2024", release="r")
        document = L.records_document({"1": {"name": "x", "metrics": [metric]}}, {"files": {}})
        self.assertNotIn("period", document["institutions"]["1"]["metrics"][0])
        self.assertEqual("Fall 2024", L.expand_metrics(document, "1")[0]["period"])

    def test_one_field_with_two_periods_is_refused(self) -> None:
        a = L.value_row(METRIC["admission_rate"], status="reported", number="0.1", period="Fall 2024", release="r")
        b = L.value_row(METRIC["admission_rate"], status="reported", number="0.2", period="Fall 2023", release="r")
        with self.assertRaises(ValueError):
            L.records_document({"1": {"metrics": [a]}, "2": {"metrics": [b]}}, {"files": {}})


class TestTheCommittedFiles(unittest.TestCase):
    """The files in crawlernest-kb/us_institutions agree with one another and with the DDL."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.matches = json.loads(L.MATCHES_PATH.read_text(encoding="utf-8"))
        cls.records = json.loads(L.RECORDS_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(L.MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.overrides = json.loads(L.OVERRIDES_PATH.read_text(encoding="utf-8"))

    def test_the_counts_add_up(self) -> None:
        counts = self.matches["counts"]
        self.assertEqual(counts["matched"], len(self.matches["matched"]))
        self.assertEqual(counts["universities"], counts["matched"] + counts["unmatched"])

    def test_every_unmatched_university_says_why(self) -> None:
        self.assertEqual([], [r["canonical_slug"] for r in self.matches["unmatched"] if not r["reason"].strip()])

    def test_no_unitid_and_no_university_is_matched_twice(self) -> None:
        for key in ("unitid", "canonical_slug"):
            values = [r[key] for r in self.matches["matched"]]
            self.assertEqual(len(values), len(set(values)), key)

    def test_every_method_status_and_unit_is_one_the_schema_allows(self) -> None:
        self.assertLessEqual({r["method"] for r in self.matches["matched"]}, ddl_values("match_method"))
        values = [m for r in self.records["institutions"].values() for m in r["metrics"]]
        self.assertLessEqual({m["status"] for m in values}, ddl_values("status"))
        self.assertLessEqual({m["unit"] for m in values}, ddl_values("unit"))
        self.assertLessEqual({m["source"] for m in values}, ddl_values("source"))

    def test_a_value_is_present_exactly_when_the_status_says_there_is_one(self) -> None:
        wrong = [(u, m["key"]) for u, r in self.records["institutions"].items() for m in r["metrics"]
                 if (m["status"] in ("reported", "imputed")) != (m["value_number"] is not None or m["value_text"] is not None)]
        self.assertEqual([], wrong)

    def test_every_value_has_a_period_and_a_release(self) -> None:
        for unitid in self.records["institutions"]:
            for m in L.expand_metrics(self.records, unitid):
                self.assertTrue(m["period"].strip() and m["release"].strip(), (unitid, m["key"]))

    def test_the_records_were_built_from_the_committed_manifest(self) -> None:
        import hashlib
        self.assertEqual(hashlib.sha256(json.dumps(self.manifest, sort_keys=True).encode()).hexdigest(),
                         self.records["manifest_sha256"])
        self.assertEqual(set(L.FILES), set(self.manifest["files"]))
        for key, entry in self.manifest["files"].items():
            self.assertEqual(L.FILES[key]["url"], entry["url"], key)
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    def test_only_matched_institutions_are_stored(self) -> None:
        matched = {r["unitid"] for r in self.matches["matched"]}
        self.assertLessEqual(set(self.records["institutions"]), matched)

    def test_every_override_says_why(self) -> None:
        self.assertEqual([], [slug for slug, o in self.overrides.items() if not str(o.get("why", "")).strip()])


class _NoCommit:
    """Hands ingest a connection whose commit does nothing, so the test can roll it all back."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def cursor(self):
        return self._conn.cursor()

    def commit(self) -> None:
        pass


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestIngestAgainstPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import psycopg2

        cls.conn = psycopg2.connect(
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"), port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            dbname=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"), user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        )
        with cls.conn.cursor() as cur:
            cur.execute(DDL)
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.close()

    def tearDown(self) -> None:
        self.conn.rollback()

    def _university(self, slug: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized)"
                        " VALUES (%s, %s, %s) RETURNING canonical_university_id", (slug, slug, slug))
            return cur.fetchone()[0]

    def _documents(self, slug: str, unitid: str):
        rows = [
            L.value_row(METRIC["admission_rate"], status="reported", number="0.0455", period="Fall 2024", release="r"),
            L.value_row(METRIC["median_earnings_10yr"], status="privacy_suppressed", detail="PS", period="AY2011-13",
                        release="r"),
        ]
        records = L.records_document({unitid: {"unitid": unitid, "name": "Test U", "opeid": None, "city": "X",
                                               "state": "MA", "website": None, "in_scorecard": True,
                                               "in_ipeds_directory": True, "metrics": rows}}, {"files": {}})
        matches = {"matched": [{"canonical_slug": slug, "unitid": unitid, "wikidata_id": "Q1",
                                "method": "wikidata_ipeds_id", "evidence": {"property": "P1771"}}]}
        return matches, records

    def test_ingest_loads_values_with_their_status_and_a_withdrawn_match_removes_them(self) -> None:
        canonical = self._university("zz-us-institution-test")
        matches, records = self._documents("zz-us-institution-test", "999901")
        counts = L.ingest(_NoCommit(self.conn), matches, records)
        self.assertEqual((1, 2), (counts["loaded"], counts["metrics"]))
        with self.conn.cursor() as cur:
            cur.execute("SELECT metric_key, value_number::text, status, reference_period FROM warehouse.us_institution_metric"
                        " WHERE canonical_university_id = %s ORDER BY metric_key", (canonical,))
            self.assertEqual([("admission_rate", "0.0455", "reported", "Fall 2024"),
                              ("median_earnings_10yr", None, "privacy_suppressed", "AY2011-13")], cur.fetchall())
        L.ingest(_NoCommit(self.conn), {"matched": []}, records)
        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM warehouse.us_institution_metric WHERE canonical_university_id = %s",
                        (canonical,))
            self.assertEqual(0, cur.fetchone()[0])

    def test_the_table_refuses_a_figure_on_a_row_that_says_there_is_none(self) -> None:
        import psycopg2

        canonical = self._university("zz-us-institution-test-2")
        matches, records = self._documents("zz-us-institution-test-2", "999902")
        L.ingest(_NoCommit(self.conn), matches, records)
        with self.assertRaises(psycopg2.errors.CheckViolation), self.conn.cursor() as cur:
            cur.execute("UPDATE warehouse.us_institution_metric SET value_number = 0"
                        " WHERE canonical_university_id = %s AND status = 'privacy_suppressed'", (canonical,))


if __name__ == "__main__":
    unittest.main()
