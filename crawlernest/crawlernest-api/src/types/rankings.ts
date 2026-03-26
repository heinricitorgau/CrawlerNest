export interface RankingItem {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  compositeScore: number;
  rankingYear: number;
  primarySource: string;
  sourceCount: number;
  slug: string;
}

export interface RankingsResponse {
  success: boolean;
  data: {
    items: RankingItem[];
  };
  metadata: {
    timestamp: string;
  };
}