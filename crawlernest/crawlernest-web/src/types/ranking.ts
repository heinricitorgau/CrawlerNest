export type RankingUniverse = "global" | "region" | "subject" | "special";

export type RankingScope = "global" | "region";

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
};
