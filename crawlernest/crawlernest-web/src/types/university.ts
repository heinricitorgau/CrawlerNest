export type UniversityRanking = {
  source: string;
  year: number | null;
  rank: number | null;
  score: number | null;
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
  byDegreeLevel: AdmissionRequirement[];
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
};

export type UniversityDetailResponse = {
  success: boolean;
  data: UniversityDetail | null;
  metadata?: {
    timestamp?: string;
  };
};
