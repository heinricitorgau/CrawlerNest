/**
 * Canonical caveat strings for the frontend.
 * Used across the analytics page, recommendations page, and explain endpoint responses.
 * Centralising here prevents wording drift between surfaces.
 *
 * These are one of four copies of the same text. The others are
 * `AnalyticsService` / `RecommendationEvidenceService` (Java),
 * `crawlernest/core/caveats.py` (Python), and
 * `docs/analytics/ANALYTICS_EXPLAINABILITY.md` (prose). Python's
 * `test_caveat_contract` reads this file and fails if the strings drift apart,
 * so a change here needs the same change there.
 *
 * Two of these were true when written and became false without anything
 * complaining, which is why the contract test now exists:
 *
 * - The stale caveat named a fixed age ("RC-1 packaging"). All three sources
 *   were re-ingested on 2026-09-04, so it was overstating the data's age by
 *   about two weeks. It no longer claims a distance from the snapshot.
 * - THE and ARWU were described as unavailable. The warehouse carries 1,637 THE
 *   and 838 ARWU ranks for 2026, so that told users a source was missing while
 *   the API served its figures. They now describe partial coverage, matching
 *   what AnalyticsService.appendSourceCoverageCaveats generates per source.
 */

export const CAVEAT_QS_STALE =
  "QS ranking data is a point-in-time snapshot of the 2026 published tables. Figures may not reflect rankings republished since this snapshot was ingested.";

export const CAVEAT_THE_PARTIAL =
  "THE (Times Higher Education) covers part of this dataset. A missing THE rank means either that the THE data ingested here does not include the university or that this platform could not match it. It does not mean THE declines to rank it.";

export const CAVEAT_ARWU_PARTIAL =
  "ARWU (Academic Ranking of World Universities) covers part of this dataset. A missing ARWU rank means either that the ARWU data ingested here does not include the university or that this platform could not match it. It does not mean ARWU declines to rank it.";

export const CAVEAT_SINGLE_SOURCE =
  "This university has single-source ranking coverage (QS only). Multi-source agreement analysis is not available.";

export const CAVEAT_IELTS_MISSING =
  "No IELTS requirement was found in stored admission data for this university. Language fit cannot be assessed.";

export const CAVEAT_SUBJECT_NO_DATA =
  "No subject ranking row was found for this university and subject. A neutral fallback was applied.";

export const CAVEAT_SUBJECT_QS_ONLY =
  "Subject rankings are QS-sourced only. THE and ARWU subject data is not available.";

export const CAVEAT_ADMISSION_DATA_STALE =
  "Admission requirements are scraped and may not reflect the current year's entry conditions.";

/**
 * Disclosure for any surface showing a value from the modelling layer.
 * Byte-identical to `AnalyticsService.ESTIMATED_SCORE_CAVEAT` and to
 * `ESTIMATED_VALUE_CAVEAT` in `crawlernest/core/caveats.py`.
 */
export const CAVEAT_MODEL_ESTIMATE =
  "Some values in this response are model estimates produced by CrawlerNest, not figures published by the ranking source. Estimated values are labelled as estimates, carry a support flag, and never replace a published rank.";

export const CAVEAT_DISAGREEMENT_ESTIMATE =
  "Cross-source disagreement probability is a model estimate of how likely QS and THE are to disagree about a university, not an observed difference between published ranks. A probability is not a rank gap, and most scored universities carry no THE rank to compare against.";

/** Standard caveats present on every recommendation and analytics response. */
export const STANDARD_CAVEATS: string[] = [
  CAVEAT_QS_STALE,
  CAVEAT_THE_PARTIAL,
  CAVEAT_ARWU_PARTIAL,
];

/**
 * @deprecated RC-1 naming, kept so existing imports keep working.
 * Prefer {@link STANDARD_CAVEATS}.
 */
export const RC1_STANDARD_CAVEATS: string[] = STANDARD_CAVEATS;
