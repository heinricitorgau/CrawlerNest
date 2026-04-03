import { formatRank, formatScore } from "@/lib/format";
import { rankingUniverseConfig } from "@/lib/rankingUniverseConfig";
import type {
  RankingApiRow,
  RankingPresentationRow,
  RankingScope,
  RankingUniverse,
} from "@/types/ranking";

type BuildRankingViewModelOptions = {
  scope: RankingScope;
  region?: string;
};

function resolveUniverse(scope: RankingScope): RankingUniverse {
  return scope === "region" ? "region" : "global";
}

export function buildRankingViewModel(
  row: RankingApiRow,
  options: BuildRankingViewModelOptions
): RankingPresentationRow {
  const universe = resolveUniverse(options.scope);
  const config = rankingUniverseConfig[universe];
  const primaryRank =
    config.primaryRankField === "scopeRank" ? row.scopeRank : row.aggregatedRank;

  const secondaryRankLabel =
    universe === "region" && row.globalRank
      ? `Global #${formatRank(row.globalRank)}`
      : undefined;

  const rankingUniverseLabel =
    universe === "region" && options.region
      ? `${options.region} Regional Ranking`
      : `${config.label} Ranking`;

  const subtitle =
    universe === "region" && options.region
      ? `${row.country} · ${options.region} ranking view`
      : row.country;

  return {
    canonicalUniversityId: row.canonicalUniversityId,
    slug: row.slug,
    universityName: row.universityName,
    country: row.country,
    shortlistRank: row.aggregatedRank,
    primaryRankLabel: `#${formatRank(primaryRank)}`,
    secondaryRankLabel,
    title: row.universityName,
    subtitle,
    scoreLabel: formatScore(row.compositeScore),
    scoreCaption: config.scoreCaption,
    sourceCoverageLabel: `${row.sourceCount} source${row.sourceCount === 1 ? "" : "s"}`,
    badgeLabel:
      universe === "region" && options.region
        ? `${options.region} scope`
        : `${config.label} scope`,
    badgeTone: config.badgeTone,
    rankingUniverseLabel,
    aggregationExplain: row.aggregationExplain,
    trustScore: row.trustScore,
    trustLevel: row.trustLevel,
    trustExplain: row.trustExplain,
  };
}
