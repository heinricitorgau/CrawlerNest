"""Tests for the admission crawl summary.

These used to assert ``"invalid_ielts" in output and any(s in output for s in
["1", "invalid_ielts: 1"])``. The second half matches the digit ``1`` anywhere
in the output, so it passed because the engine returned a single hardcoded
record and printed ``total_records: 1`` -- not because any anomaly was
detected. Against real crawl output, which contains no ``1`` at all, every one
of them failed.

They now check the structure the summary promises: which counters it reports,
that each one is a number, and that the crawl produced usable records.
"""

import contextlib
import io
import re

from crawlernest_admission_crawler.engine import AdmissionCrawlerEngine

ANOMALY_FIELDS = (
    "input_truncated",
    "invalid_ielts",
    "invalid_toefl",
    "invalid_duolingo",
    "invalid_gpa",
    "invalid_deadline",
    "invalid_degree_level",
    "source_host_mismatch",
)

_CACHED = None


def run_and_capture():
    """Run the offline crawl once and reuse it.

    AdmissionCrawlerEngine reads the checked-in snapshots unless asked for
    live=True, so this stays offline. It used to be a live crawl of eight real
    university sites, once per test -- five minutes, and load on those sites
    every time anyone ran pytest.
    """
    global _CACHED
    if _CACHED is None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            records = AdmissionCrawlerEngine().run()
        _CACHED = (buf.getvalue(), records)
    return _CACHED


def _reported_value(output: str, field: str):
    match = re.search(rf"^\s*{re.escape(field)}:\s*(\S+)\s*$", output, re.MULTILINE)
    return None if match is None else match.group(1)


def test_every_anomaly_counter_is_reported():
    output, _ = run_and_capture()
    missing = [f for f in ANOMALY_FIELDS if _reported_value(output, f) is None]
    assert not missing, f"summary omitted {missing}\n{output}"


def test_every_anomaly_counter_is_a_number():
    output, _ = run_and_capture()
    for field in ANOMALY_FIELDS:
        value = _reported_value(output, field)
        assert value.isdigit(), f"{field} reported {value!r}\n{output}"


def test_summary_reports_page_outcomes():
    # "suspicious_mapping" used to be asserted here. It is an entity-resolution
    # statistic and the crawl step reported it as a hardcoded 0, by reading
    # attributes AdmissionRecord has never had. It is now reported where it is
    # measured, by resolve-admission-entities from warehouse.source_mapping.
    output, _ = run_and_capture()
    assert _reported_value(output, "pages_attempted") is not None, output
    assert _reported_value(output, "pages_usable") is not None, output


def test_total_records_matches_what_was_returned():
    output, records = run_and_capture()
    assert _reported_value(output, "total_records") == str(len(records)), output


def test_the_crawl_produces_usable_records():
    _, records = run_and_capture()
    assert records, "the snapshot crawl produced nothing"


def test_records_carry_extracted_values_not_just_diagnostics():
    # The gap this closed: the crawler computed these and threw them away, so
    # the pipeline only ever saw one hardcoded record.
    _, records = run_and_capture()
    assert any(r.toefl_requirement is not None for r in records)
    assert any(r.ielts_requirement is not None for r in records)
    assert any(r.application_deadline is not None for r in records)


def test_records_carry_a_country_for_entity_resolution():
    _, records = run_and_capture()
    assert all(r.country for r in records), "country blocking needs this"
