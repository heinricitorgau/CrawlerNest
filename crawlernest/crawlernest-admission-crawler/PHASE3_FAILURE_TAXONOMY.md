# Phase 3 — Reality Validation: Failure Taxonomy

Generated from snapshot-based crawl of 8 universities.
Date: 2026-04-18

---

## Crawl Results Summary

| University | IELTS | TOEFL | Duolingo | GPA | Deadline | Degree Level | is_usable |
|---|---|---|---|---|---|---|---|
| UCL | 6.5 ✓ | ✗ missed | ✗ | ✗ | 2026-03-31 ✓ | postgraduate ✓ | ✓ |
| Melbourne | 6.5 ✓ | 79 ✓ | 105 ✓ | 3.0 ✓ | 2025-10-30 ✓ | postgraduate ✓ | ✓ |
| Toronto | 7.0 ✓ | 93 ✓ | ✗ | 3.3 ✓ | 2026-01-15 ✓ | postgraduate ✓ | ✓ |
| NUS | 6.0 ✓ | ✗ missed | ✗ | ✗ | 2025-11-15 ✓ | postgraduate ✓ | ✓ |
| Manchester | 7.0 (wrong) | ✗ missed | ✗ | 3.0 ✓ | 2026-01-31 ✓ | postgraduate ✓ | ✓ |
| Oxford | 7.0 ✓ | ✗ missed | ✗ | ✗ | 2025-10-15 ✓ | postgraduate ✓ | ✓ |
| Imperial | 6.5 ✓ | 92 ✓ | ✗ | 3.5 ✓ | 2026-02-28 ✓ | postgraduate ✓ | ✓ |
| MIT | ✗ | 90 ✓ | ✗ | ✗ | 2025-12-15 ✓ | postgraduate ✓ | ✓ |

required_fill_rate (IELTS or TOEFL present): 8/8 = 1.00
IELTS exact match: 7/8 (Manchester wrong)
TOEFL coverage: 3/6 pages that mention TOEFL = 50%

---

## Failure Pattern 1 — TOEFL/IELTS "X: Overall N" format

**Pattern:** `IELTS: Overall 6.5` or `TOEFL iBT: Overall 90`

**Root cause:** The extractor requires the score digit to immediately follow
the separator (`:`, `=`, space). The word "Overall" between separator and
digit is not handled.

**Affected universities:** UCL (TOEFL), NUS (TOEFL), Manchester (IELTS+TOEFL),
Oxford (TOEFL)

**Example from Manchester:**
```
<li><strong>IELTS:</strong> Overall 6.5, with no component below 6.0</li>
```
After HTML stripping → `IELTS: Overall 6.5`
Extractor skips this match, then finds `IELTS 7.0` later in the "Higher
Requirements" section → returns 7.0 instead of 6.5.

**Fix direction:** Add `Overall`, `band`, `Academic` etc. to the set of
allowed intermediate words between separator and score number.

**Severity:** HIGH — produces wrong value (not just missing)

---

## Failure Pattern 2 — TOEFL "score is N" format

**Pattern:** `TOEFL iBT score is 85`

**Root cause:** "is" is not a recognized optional keyword in the TOEFL pattern.
After `TOEFL iBT score`, the separator class `[\s:=–"'()\[\]{}-]*` matches
one space, then tries to match digit but finds `i` (from "is").

**Affected universities:** UCL, NUS, Oxford (all use "score is N" phrasing)

**Example from NUS:**
```
The minimum accepted TOEFL iBT score is 85.
```
Extractor finds no match. TOEFL returns None.

**Fix direction:** Add `is` to the optional-keyword group, OR use a more
permissive `[^0-9]{0,30}` gap approach similar to the GPA fix.

**Severity:** MEDIUM — missing value (not wrong, just absent)

---

## Failure Pattern 3 — First-match wins on multi-tier pages

**Pattern:** Pages that list multiple IELTS requirements (standard + higher tier)

**Root cause:** `_IELTS_RE.search()` returns the first regex match, which on
multi-tier pages may be in the "Higher Requirements" section rather than the
standard section, depending on page structure.

**Affected universities:** Manchester (6.5 standard, but 7.0 extracted)

**Example from Manchester:**
```
Standard: IELTS: Overall 6.5  (Pattern 1 — not matched)
Higher: some courses require IELTS 7.0  (matched → 7.0 returned)
```

**Fix direction:**
1. Fix Pattern 1 first (most impactful, may resolve this automatically)
2. If multiple matches exist, prefer the one in "standard" or "minimum" context
3. OR return a list of all found values and let the normalizer choose

**Severity:** MEDIUM — wrong value returned; impacts downstream recommendation

---

## Failure Pattern 4 — Degree level always "postgraduate" on ELR pages

**Pattern:** All 8 universities returned `degree_level=postgraduate`

**Observation:** English Language Requirements pages are typically scoped to
postgraduate programs (or cover all programs generically). The `degree_level`
extractor correctly identifies "Masters", "postgraduate", "PhD" etc. when
mentioned explicitly. On generic ELR pages, it returns the first match which
tends to be postgraduate.

**Issue:** For universities like Oxford and MIT where PhD requirements differ
from Masters, a single degree_level is not accurate. The real admission
structure is program-specific.

**Fix direction (Phase 4+):** Model degree_level as a list or map rather than
a single string. Or crawl program-specific pages instead of general ELR pages.

**Severity:** LOW for now (postgraduate is correct for these pages); HIGH for
program-specific accuracy.

---

## Failure Pattern 5 — Sandbox HTTP blocking (environment constraint)

**Pattern:** All live HTTP requests return `crawl_status="blocked"` with
`Tunnel connection failed: 403 Forbidden`.

**Root cause:** The development/CI sandbox environment blocks outbound HTTP via
its proxy. This is NOT a bug in the crawler code.

**Affected all universities:** All second-candidate URLs (no snapshot) →
blocked.

**Fix direction:** Run live crawls from a network-accessible environment.
The snapshot mechanism allows full pipeline testing in restricted environments.
The `UniversityAdmissionCrawler(snapshot_dir=...)` parameter is the correct
interface for CI.

**Severity:** ENVIRONMENT ONLY — not a code issue.

---

## Failure Pattern 6 — Multi-program pages not segmented

**Pattern:** Pages covering multiple programs (e.g. "Masters require 6.5, PhD
requires 7.0") return a single record per URL.

**Root cause:** The current design: 1 URL → 1 AdmissionRecord. No segmentation
logic exists to split a page into per-program records.

**Example (Oxford):**
> Most courses require IELTS 7.0. Some Humanities/Social Sciences courses
> require IELTS 7.5.

Currently: one record with IELTS=7.0, missing the 7.5 variant.

**Fix direction (Phase 4+):** Segment page content by program headings and
emit multiple records per URL. Requires structural HTML analysis beyond regex.

**Severity:** LOW for current use case (single-value extraction); HIGH for
program-specific recommendation accuracy.

---

## Priority Fix Order for Phase 4

1. **Fix Pattern 1** (IELTS/TOEFL "X: Overall N") — affects 4/8 universities,
   causes wrong values. Small regex change with high impact.

2. **Fix Pattern 2** (TOEFL "score is N") — affects 3/8 universities, causes
   missing TOEFL. Add "is" to optional keyword group.

3. **Fix Pattern 3** (first-match wrong on multi-tier) — depends on Pattern 1
   fix; may resolve automatically. If not, add context-priority scoring.

4. **Patterns 4 and 6** — require architectural decisions, defer to Phase 5+.

---

## Phase 4 Gating Rule

Every fix in Phase 4 MUST:
1. Be applied to `admission_text_extractor.py`
2. Be validated against `crawlernest-autoeval/datasets/admission_goldens/samples.json`
3. Score >= current baseline (0.866) before accepting the change
4. Document "before vs after" per fix
