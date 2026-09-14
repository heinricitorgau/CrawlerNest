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
 *
 * The snapshot caveat names the editions held, so it is rendered from a
 * template rather than written out: a year in a constant expires the same way
 * the old "RC-1 packaging" age did.
 */

import { DATASET_YEARS } from "@/lib/datasetScope";

/**
 * Byte-identical to `SNAPSHOT_CAVEAT_TEMPLATE` in `crawlernest/core/caveats.py`,
 * `AnalyticsService.SNAPSHOT_CAVEAT_TEMPLATE`, and the copy in
 * `ANALYTICS_EXPLAINABILITY.md`. `{years}` is replaced literally.
 */
export const SNAPSHOT_CAVEAT_TEMPLATE =
  "QS ranking data is a point-in-time snapshot of the {years} published tables. Figures may not reflect rankings republished since this snapshot was ingested.";

/**
 * Held editions as prose: `2026`, `2025 and 2026`, `2024, 2025 and 2026`.
 * Ascending and de-duplicated whatever order they arrive in. The rows in
 * ANALYTICS_EXPLAINABILITY.md are the specification; Python and Java test their
 * renderers against the same rows.
 */
export function formatEditionYears(years: readonly number[]): string {
  const ordered = [...new Set(years)].sort((a, b) => a - b).map(String);
  if (ordered.length === 0) {
    throw new Error("a snapshot caveat has to name at least one edition");
  }
  if (ordered.length === 1) {
    return ordered[0];
  }
  return `${ordered.slice(0, -1).join(", ")} and ${ordered[ordered.length - 1]}`;
}

/** The snapshot disclosure for the editions held. */
export function snapshotCaveat(years: readonly number[] = DATASET_YEARS): string {
  return SNAPSHOT_CAVEAT_TEMPLATE.replace("{years}", formatEditionYears(years));
}

export const CAVEAT_QS_STALE = snapshotCaveat();

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

/**
 * CAVEAT_ADMISSION_DATA_STALE names a date, so it is a pair of templates rather
 * than a constant. Byte-identical to ADMISSION_STALE_*_TEMPLATE in
 * crawlernest/core/caveats.py and AnalyticsService.java. The API renders these;
 * the frontend renders only when it holds the staleness fields itself.
 */
export const ADMISSION_STALE_FETCHED_TEMPLATE =
  "Admission requirements were read from university pages fetched on {date} and may not reflect the current year's entry conditions.";

export const ADMISSION_STALE_UNDATED_TEMPLATE =
  "Admission requirements were read from university pages whose fetch date was not recorded. They were extracted on {date}, the pages may be older than that, and they may not reflect the current year's entry conditions.";

/**
 * The staleness disclosure for the admission rows behind a view: every fetch
 * date recorded, the oldest fetch, the oldest extraction (UTC ISO dates).
 * Null when there is no admission data. Same rule as admission_stale_caveat.
 */
export function admissionStaleCaveat(staleness: {
  fetchDatesRecorded: boolean;
  oldestFetchedOn: string | null;
  oldestExtractedOn: string | null;
}): string | null {
  if (staleness.fetchDatesRecorded && staleness.oldestFetchedOn) {
    return ADMISSION_STALE_FETCHED_TEMPLATE.replace("{date}", staleness.oldestFetchedOn.slice(0, 10));
  }
  if (staleness.oldestExtractedOn) {
    return ADMISSION_STALE_UNDATED_TEMPLATE.replace("{date}", staleness.oldestExtractedOn.slice(0, 10));
  }
  return null;
}

/**
 * Disclosure for any surface showing a value from the modelling layer.
 * Byte-identical to `AnalyticsService.ESTIMATED_SCORE_CAVEAT` and to
 * `ESTIMATED_VALUE_CAVEAT` in `crawlernest/core/caveats.py`.
 */
export const CAVEAT_MODEL_ESTIMATE =
  "Some values in this response are model estimates produced by CrawlerNest, not figures published by the ranking source. Estimated values are labelled as estimates, carry a support flag, and never replace a published rank.";

export const CAVEAT_UNSUPPORTED_ESTIMATE =
  "Some estimates here fall outside the data the model was fitted on and are marked unsupported. The model has seen no comparable cases for them. That is a statement about the evidence behind the estimate, not a measurement of how wrong it is.";

/** Shown wherever a per-source rank change (rankDelta) is rendered. */
export const CAVEAT_RANK_CHANGE =
  "Rank changes compare one source's published ranks between two editions. They are not changes in a composite or platform rank, a banded rank gives a range rather than a number, and no change is shown when the institution or its source entry changed between editions.";

/** Shown on ranking trends when more than one edition is held. */
export const CAVEAT_COMPOSITE_RANK_NOT_COMPARED =
  "Composite ranks are not compared between editions. A university's composite position moves whenever source coverage changes, so rank movement is reported per source on each university's page instead.";

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
