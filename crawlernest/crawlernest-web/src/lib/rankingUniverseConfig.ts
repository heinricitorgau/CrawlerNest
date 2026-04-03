import type { RankingUniverse } from "@/types/ranking";

export type RankingUniverseConfig = {
  label: string;
  primaryRankField: "aggregatedRank" | "scopeRank";
  rankHeading: string;
  scoreHeading: string;
  scoreCaption: string;
  badgeTone: "accent" | "muted";
};

export const rankingUniverseConfig: Record<
  RankingUniverse,
  RankingUniverseConfig
> = {
  global: {
    label: "Global",
    primaryRankField: "aggregatedRank",
    rankHeading: "Global Rank",
    scoreHeading: "Agg. Score",
    scoreCaption: "Strong global position",
    badgeTone: "accent",
  },
  region: {
    label: "Regional",
    primaryRankField: "scopeRank",
    rankHeading: "Region Rank",
    scoreHeading: "Agg. Score",
    scoreCaption: "Regional standing across sources",
    badgeTone: "muted",
  },
  subject: {
    label: "Subject",
    primaryRankField: "scopeRank",
    rankHeading: "Subject Rank",
    scoreHeading: "Subject Score",
    scoreCaption: "Subject-level standing",
    badgeTone: "muted",
  },
  special: {
    label: "Special",
    primaryRankField: "scopeRank",
    rankHeading: "Special Rank",
    scoreHeading: "Score",
    scoreCaption: "Universe-specific standing",
    badgeTone: "muted",
  },
};
