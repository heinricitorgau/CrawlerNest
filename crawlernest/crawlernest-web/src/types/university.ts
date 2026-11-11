/**
 * One source's movement between two editions (clawer.dto.RankDeltaDTO).
 *
 * Always per source; there is no composite equivalent. `value` is current minus
 * prior (negative = up) and is set only for two exact ranks; `min`/`max` bound a
 * banded movement. Render `direction`, never the sign.
 */
export type RankDeltaDirection = "up" | "down" | "unchanged" | "indeterminate";

/**
 * Why `rankDelta` is null, or "banded" when it is an interval
 * (clawer.service.SourceRankDelta / RankComparisonPolicy reason codes).
 * `entity_changed` covers a lineage merger, split or rename and a source
 * re-keying its entry; the code does not say which.
 */
export type RankDeltaReason =
  | "banded"
  | "single_year_dataset"
  | "no_prior_row"
  | "no_current_row"
  | "entity_changed"
  | "suspicious_merge"
  | "rank_display_missing"
  | "composite_rank_not_comparable";

export type RankDelta = {
  priorYear: number | null;
  currentYear: number | null;
  /** The prior edition's rank as printed: "601–610". */
  priorRankDisplay: string | null;
  value: number | null;
  min: number | null;
  max: number | null;
  direction: RankDeltaDirection | null;
};

export type UniversityRanking = {
  source: string;
  year: number | null;
  /** A band's lower bound; show `rankDisplay` when present. */
  rank: number | null;
  /** The rank as the source printed it: "=98", "201–250". */
  rankDisplay?: string | null;
  score: number | null;
  /** Null when no movement is shown; `rankDeltaReason` says why. */
  rankDelta?: RankDelta | null;
  /**
   * Why `rankDelta` is null, or "banded". Null for an exact change. Typed as
   * string too: a code the API adds later must still render, as withheld.
   */
  rankDeltaReason?: RankDeltaReason | (string & {}) | null;
};

export type AggregatedRanking = {
  displayRank: number | null;
  compositeScore: number | null;
  rankingYear: number | null;
  aggregationMethodVersion: string | null;
};

export type DataQuality = {
  recommendationConfidence: number | null;
  confidenceLabel: string | null;
  confidenceReason: string | null;
};

/**
 * One degree level's entry requirements, mirroring the columns of
 * warehouse.admission_record.
 *
 * Every requirement is `| null` rather than optional: the API always emits the
 * key and sets it to null when the source published no value. Typing these as
 * `?` would let call sites treat a missing key and a published-as-null value as
 * the same thing, and would not stop `undefined` reaching the DOM.
 */
export type AdmissionRequirement = {
  /** Null on a cross-level summary, which by definition names no single level. */
  degreeLevel: string | null;
  ieltsRequirement: number | null;
  toeflRequirement: number | null;
  duolingoRequirement: number | null;
  gpaRequirement: number | null;
  /** ISO-8601 date, `yyyy-MM-dd`. */
  applicationDeadline: string | null;
  sourceUrl: string | null;
  /**
   * What the figures apply to: `institution_minimum`, `unspecified` (one figure
   * whose scope the page did not establish), `programme` or `faculty`. Optional
   * only so a cached response from before the field existed still type-checks.
   */
  requirementScope?: string | null;
  faculty?: string | null;
  programmeName?: string | null;
  intakeYear?: number | null;
  /** `page_stated`, `deadline_inferred` or `unknown`. */
  intakeYearBasis?: string | null;
  /** University-level rows disagreed and the lowest bar is shown. */
  valuesDiffer?: boolean | null;
};

/**
 * The admission block on a university detail response.
 *
 * `hasData` distinguishes "no crawled admission page exists" from "one exists
 * and every field on it was blank". Branch on it before rendering, because the
 * two cases deserve different copy and only the second is worth showing a
 * source link for.
 *
 * `summary` is the lowest published bar across all degree levels, so when
 * `degreeLevelCount > 1` a UI quoting it should say "from" or name the level.
 * It is always an object, never null, even when `hasData` is false.
 */
export type AdmissionRequirements = {
  hasData: boolean;
  degreeLevelCount: number;
  summary: AdmissionRequirement;
  /** University-level figures only; programme rows are never folded in. */
  byDegreeLevel: AdmissionRequirement[];
  /** Requirements a source attributed to a named programme or faculty. */
  programmeRequirements?: AdmissionRequirement[];
  /** CAVEAT_IELTS_MISSING / CAVEAT_ADMISSION_DATA_STALE, rendered by the API. Show them verbatim. */
  caveats?: string[];
  fetchDatesRecorded?: boolean | null;
  oldestFetchedOn?: string | null;
  oldestExtractedOn?: string | null;
};

export type UniversityDetail = {
  canonicalUniversityId: number;
  slug: string;
  universityName: string;
  country: string;
  aggregatedRanking: AggregatedRanking | null;
  sourceRankings: UniversityRanking[];
  rankingEvidence?: UniversityRanking[];
  admissionRequirements: AdmissionRequirements;
  dataQuality: DataQuality | null;
  /**
   * The edition this response was read for, set whether or not the university has
   * a row in it (`aggregatedRanking` is null when it has none). Optional: absent
   * from older API builds.
   */
  rankingYear?: number | null;
};

export type UniversityDetailResponse = {
  success: boolean;
  data: UniversityDetail | null;
  metadata?: {
    timestamp?: string;
  };
};

/** One section of a Wikipedia article. The lead comes first: level 1, no heading. */
export type WikipediaSection = {
  level: number;
  heading: string | null;
  text: string;
};

/**
 * The Wikipedia article matched to a university (`/api/v1/universities/{id}/wikipedia`).
 *
 * Wikipedia's text under `license`, not CrawlerNest data: whatever renders
 * `sections` must show `pageUrl`, the licence and `notice` with it.
 */
export type WikipediaArticle = {
  canonicalUniversityId: number;
  language: string;
  wikidataId: string;
  pageTitle: string;
  pageUrl: string;
  revisionId: number;
  revisionUrl: string;
  revisionTimestamp: string | null;
  matchMethod: string;
  license: string;
  licenseUrl: string;
  fetchedAt: string | null;
  notice: string;
  sections: WikipediaSection[];
};

export type WikipediaArticleResponse = {
  success: boolean;
  /** Null when no article is matched to the university. */
  data: WikipediaArticle | null;
};

/** A US federal value's status. Only "reported" and "imputed" carry a value; none of the others is zero. */
export type UsFederalStatus = "reported" | "imputed" | "privacy_suppressed" | "not_available" | "not_applicable";

export type UsFederalMetric = {
  source: "COLLEGE_SCORECARD" | "IPEDS" | (string & {});
  key: string;
  /** The column in the federal file (ADM_RATE, NPT4_PRIV, APPLCN). */
  sourceField: string;
  unit: "ratio" | "percent" | "usd" | "count" | "score" | "code" | "text" | (string & {});
  value: number | null;
  /** A code's label, or a text field's value. */
  valueText: string | null;
  status: UsFederalStatus | (string & {});
  statusDetail: string | null;
  /** Verbatim from the source's documentation; differs from value to value. */
  referencePeriod: string;
  release: string;
};

export type UsFederalSource = { code: string; name: string; publisher: string; url: string; license: string };

/**
 * US federal institutional data (`/api/v1/universities/{id}/us-institution`). Not ranking
 * data: render `caveats` with it, and each value's `referencePeriod` beside the value.
 */
export type UsInstitution = {
  canonicalUniversityId: number;
  unitid: number;
  institutionName: string;
  city: string | null;
  stateCode: string | null;
  website: string | null;
  matchMethod: string;
  wikidataId: string | null;
  sources: UsFederalSource[];
  metrics: UsFederalMetric[];
  caveats: string[];
};

export type UsInstitutionResponse = {
  success: boolean;
  /** Null when no federal record is matched to the university. */
  data: UsInstitution | null;
};

/** One source's place in one edition (GET /api/v1/universities/{id}/rank-history). */
export type RankHistoryPoint = {
  year: number;
  /**
   * ranked: the source's printed rank. edition_not_held: this warehouse holds no edition of the source that
   * year. not_in_edition: the edition is held and this university has no rank in it here (not ingested, or
   * not matched). Neither gap means the source declined to rank it.
   */
  status: "ranked" | "edition_not_held" | "not_in_edition";
  rankDisplay?: string;
  rankLower?: number;
  /** Null for an open band ("1001+"); equal to rankLower for an exact rank. */
  rankUpper?: number | null;
  archived?: boolean;
  suspiciousMerge?: boolean;
  /** The source's entry for this university differs from the previous ranked point's: the line breaks here. */
  sourceIdentityChanged?: boolean;
};

export type RankHistorySeries = {
  source: string;
  rankedEditions: number;
  points: RankHistoryPoint[];
};

export type RankHistory = {
  years: number[];
  series: RankHistorySeries[];
  caveats: string[];
};

export type RankHistoryResponse = {
  success: boolean;
  data: RankHistory | null;
};
