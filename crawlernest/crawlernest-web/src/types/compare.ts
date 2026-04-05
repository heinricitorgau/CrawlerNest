export type ShortlistItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  slug: string;
};

export type CompareUniversityPayload = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number | null;
  aggregatedScore: number | null;
  ieltsMin: number | null;
  sourceRanks: Partial<Record<"QS" | "THE" | "ARWU", number>>;
  dataCompleteness: {
    hasAggregatedRank: boolean;
    hasIeltsRequirement: boolean;
    availableSourceCount: number;
    sourceCoverageRatio: number;
    coverageRatio: number;
  };
  aggregationMethodVersion: string | null;
  evidenceSummary: {
    availableSourceCount: number;
    bestRank: number | null;
    worstRank: number | null;
    spread: number | null;
    agreementLevel: "strong" | "moderate" | "weak" | "limited";
    note: string;
  };
  trustScore: number;
  trustLevel: "high" | "medium" | "low";
  trustExplain: {
    sources: Partial<Record<"QS" | "THE" | "ARWU", number | null>>;
    coverageScore: number;
    consistencyScore: number;
    stdDeviation: number;
    notes: string[];
  };
  warnings: string[];
};

export type CompareResponse = {
  success: boolean;
  data: {
    betterUniversity?: {
      canonicalUniversityId: number;
      universityName: string;
    } | null;
    summary: string;
    order: string[];
    comparison: {
      universities: Record<string, CompareUniversityPayload>;
      ranking: {
        winner: string;
        explanation: string;
      };
      ielts: {
        winner: string;
        explanation: string;
      };
      dataCompleteness: {
        winner: string;
        explanation: string;
      };
      sources: Record<
        "QS" | "THE" | "ARWU",
        {
          winner: string;
          explanation: string;
        }
      >;
      decisionFactors: string[];
    };
  } | null;
};
