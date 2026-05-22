/**
 * Canonical caveat strings for RC-1 data limitations.
 * Used across the analytics page, recommendations page, and explain endpoint responses.
 * Centralising here prevents wording drift between surfaces.
 */

export const CAVEAT_QS_STALE =
  "QS ranking data was last ingested at RC-1 packaging. Data may not reflect the current published rankings.";

export const CAVEAT_THE_UNAVAILABLE =
  "THE (Times Higher Education) data is not available at RC-1. Rankings reflect QS source only.";

export const CAVEAT_ARWU_UNAVAILABLE =
  "ARWU (Academic Ranking of World Universities) data is not available at RC-1. Rankings reflect QS source only.";

export const CAVEAT_SINGLE_SOURCE =
  "This university has single-source ranking coverage (QS only). Multi-source agreement analysis is not available.";

export const CAVEAT_IELTS_MISSING =
  "No IELTS requirement was found in stored admission data for this university. Language fit cannot be assessed.";

export const CAVEAT_SUBJECT_NO_DATA =
  "No subject ranking row was found for this university and subject. A neutral fallback was applied.";

export const CAVEAT_SUBJECT_QS_ONLY =
  "Subject rankings are QS-sourced only at RC-1. THE and ARWU subject data is not available.";

export const CAVEAT_ADMISSION_DATA_STALE =
  "Admission requirements are scraped and may not reflect the current year's entry conditions.";

/** Standard RC-1 caveats present on every recommendation and analytics response. */
export const RC1_STANDARD_CAVEATS: string[] = [
  CAVEAT_QS_STALE,
  CAVEAT_THE_UNAVAILABLE,
  CAVEAT_ARWU_UNAVAILABLE,
];
