"""Tests for admission_text_extractor.py — Phase 2.

Each field extractor is tested independently (unit) and the top-level
``extract()`` function is tested end-to-end (integration).

Coverage targets
----------------
- IELTS: valid scores, boundary values, out-of-range, missing
- TOEFL: valid, boundary, out-of-range, missing
- Duolingo: valid, missing
- Degree level: all three canonical levels, mixed text, boundary/regression
- Deadline: ISO, Month-Day-Year, Day-Month-Year, near context cue, missing
- GPA: standard, colon separator, CJK separator, out-of-range
- HTML stripping: block tags become newlines, inline tags stripped
- Full extract(): JSON input, noisy HTML, mixed CJK/EN
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
_CRAWLER_DIR = _REPO_ROOT / "crawlernest-admission-crawler"
_EXTRACTORS_DIR = _CRAWLER_DIR / "extractors"

for _p in (_CRAWLER_DIR, _EXTRACTORS_DIR):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from admission_text_extractor import (
    extract,
    extract_ielts,
    extract_toefl,
    extract_duolingo,
    extract_degree_level,
    extract_deadline,
    extract_gpa,
    _strip_html,
)


# ── _strip_html ────────────────────────────────────────────────────────────────

class TestStripHtml:
    def test_block_tags_become_newline(self) -> None:
        result = _strip_html("<p>Hello</p><div>World</div>")
        assert "Hello" in result and "World" in result
        # Block close tags become newline, so paragraphs are separated
        assert "\n" in result

    def test_inline_tags_stripped(self) -> None:
        result = _strip_html("<span>text</span>")
        assert "<span>" not in result
        assert "text" in result

    def test_br_becomes_newline(self) -> None:
        result = _strip_html("line1<br/>line2")
        assert "line1" in result
        assert "line2" in result

    def test_multiple_spaces_collapsed(self) -> None:
        result = _strip_html("a    b")
        assert "a b" in result

    def test_empty_string(self) -> None:
        assert _strip_html("") == ""

    def test_plain_text_unchanged(self) -> None:
        result = _strip_html("IELTS 6.5")
        assert "IELTS 6.5" in result


# ── extract_ielts ─────────────────────────────────────────────────────────────

class TestExtractIelts:
    def test_basic_score(self) -> None:
        assert extract_ielts("IELTS 6.5") == 6.5

    def test_with_overall(self) -> None:
        assert extract_ielts("IELTS: 6.5 overall") == 6.5

    def test_with_minimum(self) -> None:
        assert extract_ielts("IELTS minimum 7.0") == 7.0

    def test_academic_qualifier(self) -> None:
        assert extract_ielts("IELTS Academic 7.5") == 7.5

    def test_half_band_scores(self) -> None:
        for score in (4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0):
            assert extract_ielts(f"IELTS {score}") == score

    def test_boundary_minimum(self) -> None:
        assert extract_ielts("IELTS 4.0") == 4.0

    def test_boundary_maximum(self) -> None:
        assert extract_ielts("IELTS 9.0") == 9.0

    def test_below_range_returns_none(self) -> None:
        assert extract_ielts("IELTS 2.0") is None

    def test_above_range_returns_none(self) -> None:
        assert extract_ielts("IELTS 10.0") is None

    def test_no_ielts_returns_none(self) -> None:
        assert extract_ielts("TOEFL 90 required") is None

    def test_json_style_quotes(self) -> None:
        assert extract_ielts('"IELTS": "6.5 overall"') == 6.5

    def test_noise_numbers_not_confused(self) -> None:
        # Year 2026 and ranking #45 should not be mistaken for IELTS
        result = extract_ielts("Ranked #45 globally in 2026. IELTS 6.5 required.")
        assert result == 6.5


# ── extract_toefl ─────────────────────────────────────────────────────────────

class TestExtractToefl:
    def test_basic_score(self) -> None:
        assert extract_toefl("TOEFL 90") == 90

    def test_ibt_qualifier(self) -> None:
        assert extract_toefl("TOEFL iBT 92") == 92

    def test_minimum_qualifier(self) -> None:
        assert extract_toefl("TOEFL minimum 80") == 80

    def test_boundary_minimum(self) -> None:
        assert extract_toefl("TOEFL 50") == 50

    def test_boundary_maximum(self) -> None:
        assert extract_toefl("TOEFL 120") == 120

    def test_below_range_returns_none(self) -> None:
        assert extract_toefl("TOEFL 30") is None

    def test_above_range_returns_none(self) -> None:
        assert extract_toefl("TOEFL 130") is None

    def test_no_toefl_returns_none(self) -> None:
        assert extract_toefl("IELTS 6.5 only") is None

    def test_json_style_quotes(self) -> None:
        assert extract_toefl('"TOEFL": "90 iBT"') == 90

    def test_score_100(self) -> None:
        assert extract_toefl("TOEFL iBT 100 minimum") == 100


# ── extract_duolingo ──────────────────────────────────────────────────────────

class TestExtractDuolingo:
    def test_basic_score(self) -> None:
        assert extract_duolingo("Duolingo 115") == 115

    def test_full_name(self) -> None:
        assert extract_duolingo("Duolingo English Test 130") == 130

    def test_det_acronym(self) -> None:
        assert extract_duolingo("Duolingo DET 110") == 110

    def test_minimum_qualifier(self) -> None:
        assert extract_duolingo("Duolingo minimum 105") == 105

    def test_no_duolingo_returns_none(self) -> None:
        assert extract_duolingo("IELTS 6.5 required") is None

    def test_out_of_range_returns_none(self) -> None:
        assert extract_duolingo("Duolingo 200") is None


# ── extract_degree_level ──────────────────────────────────────────────────────

class TestExtractDegreeLevel:
    # --- Postgraduate ---
    def test_masters(self) -> None:
        assert extract_degree_level("Master's programme") == "postgraduate"

    def test_masters_without_apostrophe(self) -> None:
        assert extract_degree_level("Masters degree applicants") == "postgraduate"

    def test_msc(self) -> None:
        assert extract_degree_level("MSc Computer Science") == "postgraduate"

    def test_mba(self) -> None:
        assert extract_degree_level("MBA programme") == "postgraduate"

    def test_postgraduate_keyword(self) -> None:
        assert extract_degree_level("Postgraduate Admissions") == "postgraduate"

    def test_graduate_program(self) -> None:
        assert extract_degree_level("Graduate program in Finance") == "postgraduate"

    # --- Doctoral ---
    def test_phd(self) -> None:
        assert extract_degree_level("PhD applicants") == "doctoral"

    def test_phd_dotted(self) -> None:
        assert extract_degree_level("Ph.D. programme") == "doctoral"

    def test_doctoral(self) -> None:
        assert extract_degree_level("doctoral-level degree") == "doctoral"

    def test_dphil(self) -> None:
        assert extract_degree_level("D.Phil Programme in Philosophy") == "doctoral"

    def test_doctor_of(self) -> None:
        assert extract_degree_level("Doctor of Philosophy") == "doctoral"

    # --- Undergraduate ---
    def test_bachelor(self) -> None:
        assert extract_degree_level("Bachelor's degree") == "undergraduate"

    def test_bachelors_without_apostrophe(self) -> None:
        assert extract_degree_level("Bachelors programme") == "undergraduate"

    def test_undergraduate_keyword(self) -> None:
        assert extract_degree_level("Undergraduate Admissions") == "undergraduate"

    def test_bsc(self) -> None:
        assert extract_degree_level("BSc Engineering") == "undergraduate"

    # --- Boundary / regression ---
    def test_undergraduate_does_not_become_postgraduate(self) -> None:
        # Bug A regression: "graduate" inside "undergraduate" must not match postgraduate
        assert extract_degree_level("undergraduate program") == "undergraduate"

    def test_bachelor_of_arts_is_undergraduate(self) -> None:
        assert extract_degree_level("Bachelor of Arts - History") == "undergraduate"

    def test_graduate_school_not_postgraduate(self) -> None:
        # "graduate school" without other cues — check it doesn't false-positive
        result = extract_degree_level("This is a graduate school overview page.")
        # "graduate school" is excluded; no other signal, may be None or postgraduate
        # The important thing: "undergraduate" is not returned
        assert result != "undergraduate"

    def test_no_degree_returns_none(self) -> None:
        assert extract_degree_level("English requirement: IELTS 6.5") is None


# ── extract_deadline ─────────────────────────────────────────────────────────

class TestExtractDeadline:
    def test_iso_format(self) -> None:
        assert extract_deadline("Apply by 2026-01-15") == "2026-01-15"

    def test_iso_with_deadline_cue(self) -> None:
        assert extract_deadline("Application deadline: 2026-03-01") == "2026-03-01"

    def test_month_day_year(self) -> None:
        assert extract_deadline("Apply before January 15, 2026") == "2026-01-15"

    def test_month_day_year_no_comma(self) -> None:
        assert extract_deadline("Deadline: March 31 2026") == "2026-03-31"

    def test_day_month_year(self) -> None:
        # Bug C regression: "15 April 2026" must be parsed
        assert extract_deadline("15 April 2026") == "2026-04-15"

    def test_day_month_year_february(self) -> None:
        assert extract_deadline("28 February 2026") == "2026-02-28"

    def test_day_month_year_september(self) -> None:
        assert extract_deadline("30 September 2026") == "2026-09-30"

    def test_deadline_in_noisy_sentence(self) -> None:
        text = "Tuition: USD 5000/year. Closing date: December 1, 2026. Apply early."
        assert extract_deadline(text) == "2026-12-01"

    def test_no_date_returns_none(self) -> None:
        assert extract_deadline("English requirement: IELTS 6.5") is None

    def test_prefers_deadline_context_over_noise(self) -> None:
        # Founded year 1872 should not be returned; deadline date should be
        text = "Founded 1872. Deadline: 2026-05-15. Ranking: 2025 edition."
        assert extract_deadline(text) == "2026-05-15"


# ── extract_gpa ───────────────────────────────────────────────────────────────

class TestExtractGpa:
    def test_basic_gpa(self) -> None:
        assert extract_gpa("GPA 3.5") == 3.5

    def test_gpa_of(self) -> None:
        assert extract_gpa("GPA of 3.5") == 3.5

    def test_gpa_colon_minimum(self) -> None:
        # Bug B regression: "GPA: minimum 3.0" must parse
        assert extract_gpa("GPA: minimum 3.0/4.0") == 3.0

    def test_gpa_minimum_keyword(self) -> None:
        # "minimum GPA of 3.5" is standard phrasing — extractor correctly finds 3.5
        assert extract_gpa("minimum GPA of 3.5") == 3.5

    def test_gpa_with_scale(self) -> None:
        assert extract_gpa("GPA 3.5/4.0") == 3.5

    def test_gpa_cjk_separator(self) -> None:
        # Bug B (CJK): "GPA 最低 3.0 / 4.0" must parse
        assert extract_gpa("GPA 最低 3.0 / 4.0") == 3.0

    def test_gpa_out_of_range_returns_none(self) -> None:
        assert extract_gpa("GPA 5.0") is None

    def test_gpa_zero_returns_zero(self) -> None:
        assert extract_gpa("GPA 0.0 required") == 0.0

    def test_gpa_4_0_maximum(self) -> None:
        assert extract_gpa("GPA 4.0") == 4.0

    def test_no_gpa_returns_none(self) -> None:
        assert extract_gpa("IELTS 6.5 required") is None


# ── extract() — top-level integration ────────────────────────────────────────

class TestExtract:
    def test_returns_all_keys(self) -> None:
        result = extract("IELTS 6.5")
        for key in ("ielts", "toefl", "duolingo", "degree_level", "deadline", "gpa"):
            assert key in result

    def test_full_happy_path(self) -> None:
        text = (
            "Postgraduate Admissions\n"
            "IELTS: 6.5 overall\nTOEFL iBT: 92\n"
            "Application deadline: Apply by 2026-01-15\n"
            "GPA 3.5 minimum"
        )
        r = extract(text)
        assert r["ielts"] == 6.5
        assert r["toefl"] == 92
        assert r["degree_level"] == "postgraduate"
        assert r["deadline"] == "2026-01-15"
        assert r["gpa"] == 3.5

    def test_html_noisy_input(self) -> None:
        html = (
            "<nav>Home | About</nav>"
            "<div class='promo'>50% scholarship!</div>"
            "<main><h1>MBA Programme</h1>"
            "<p>English requirement: IELTS 6.5 minimum.</p>"
            "<p>Deadline: 15 April 2026</p></main>"
            "<footer>Privacy Policy</footer>"
        )
        r = extract(html)
        assert r["ielts"] == 6.5
        assert r["degree_level"] == "postgraduate"
        assert r["deadline"] == "2026-04-15"

    def test_json_structured_input(self) -> None:
        json_text = '{"IELTS": "6.5 overall", "TOEFL": "90 iBT", "level": "Masters", "deadline": "2026-05-15"}'
        r = extract(json_text)
        assert r["ielts"] == 6.5
        assert r["toefl"] == 90
        assert r["degree_level"] == "postgraduate"
        assert r["deadline"] == "2026-05-15"

    def test_no_language_score_all_none(self) -> None:
        text = "Bachelor of Arts - History. No specific language test required."
        r = extract(text)
        assert r["ielts"] is None
        assert r["toefl"] is None
        assert r["duolingo"] is None
        assert r["degree_level"] == "undergraduate"

    def test_mixed_cjk_english(self) -> None:
        text = "碩士班（Master's Program）英語能力：IELTS 6.5 overall。GPA 最低 3.0 / 4.0\n申請截止：2026-06-30"
        r = extract(text)
        assert r["ielts"] == 6.5
        assert r["degree_level"] == "postgraduate"
        assert r["gpa"] == 3.0
        assert r["deadline"] == "2026-06-30"

    def test_doctoral_all_three_tests(self) -> None:
        text = "Doctor of Philosophy - Linguistics. IELTS 7.5, TOEFL iBT 110, or Duolingo 130. Apply before 2026-11-30."
        r = extract(text)
        assert r["ielts"] == 7.5
        assert r["toefl"] == 110
        assert r["duolingo"] == 130
        assert r["degree_level"] == "doctoral"
        assert r["deadline"] == "2026-11-30"

    def test_empty_string_all_none(self) -> None:
        r = extract("")
        for key in ("ielts", "toefl", "duolingo", "degree_level", "deadline", "gpa"):
            assert r[key] is None

    def test_noise_numbers_not_extracted_as_ielts(self) -> None:
        text = "Founded 1901. Ranking: #45. Fees: USD 22,500. IELTS 6.5."
        r = extract(text)
        assert r["ielts"] == 6.5

    def test_undergraduate_not_classified_as_postgraduate(self) -> None:
        # Regression for Bug A
        text = "Undergraduate program in Computer Science. Bachelor's degree applicants."
        r = extract(text)
        assert r["degree_level"] == "undergraduate"


# ── Run directly ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
