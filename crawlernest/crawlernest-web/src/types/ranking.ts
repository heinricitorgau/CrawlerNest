export type RankingUniverse = "global" | "region" | "subject" | "special";

export type RankingScope = "global" | "region";

export type RankingCountryOption = {
  code: string | null;
  name: string;
  count: number;
};

export type RankingApiRow = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  globalRank?: number;
  scopeRank?: number;
  compositeScore: number;
  rankingYear?: number;
  primarySource?: string;
  sourceCount: number;
  slug: string;
  aggregationExplain?: {
    sources: {
      QS: number | null;
      THE: number | null;
      ARWU: number | null;
    };
    weights: {
      QS: number;
      THE: number;
      ARWU: number;
    };
    aggregatedRankValue: number;
    availableSourceCount: number;
  };
  trustScore?: number;
  trustLevel?: "high" | "medium" | "low";
  trustExplain?: {
    sources: {
      QS: number | null;
      THE: number | null;
      ARWU: number | null;
    };
    coverageScore: number;
    consistencyScore: number;
    stdDeviation: number;
    notes: string[];
  };
};

export type RankingPresentationRow = {
  canonicalUniversityId: number;
  slug: string;
  universityName: string;
  country: string;
  shortlistRank: number;
  primaryRankLabel: string;
  secondaryRankLabel?: string;
  title: string;
  subtitle?: string;
  scoreLabel: string;
  scoreCaption: string;
  sourceCoverageLabel: string;
  badgeLabel: string;
  badgeTone: "accent" | "muted";
  rankingUniverseLabel: string;
  aggregationExplain?: RankingApiRow["aggregationExplain"];
  trustScore?: number;
  trustLevel?: RankingApiRow["trustLevel"];
  trustExplain?: RankingApiRow["trustExplain"];
};

export type RankingsApiMetadata = {
  timestamp?: string;
  totalCount?: number;
  page?: number;
  pageSize?: number;
  countryOptions?: RankingCountryOption[];
};
