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

export type UniversityDetail = {
  canonicalUniversityId: number;
  slug: string;
  universityName: string;
  country: string;
  aggregatedRanking: AggregatedRanking | null;
  sourceRankings: UniversityRanking[];
  admissionRequirements: Record<string, unknown>;
  dataQuality: DataQuality | null;
};

export type UniversityDetailResponse = {
  success: boolean;
  data: UniversityDetail | null;
  metadata?: {
    timestamp?: string;
  };
};
