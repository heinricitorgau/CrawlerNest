function isMissing(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined || Number.isNaN(value);
}

export function formatScore(score: number | null | undefined): string {
  if (isMissing(score)) {
    return "Not available";
  }

  return score.toFixed(1);
}

export function formatRank(rank: number | null | undefined): string {
  if (isMissing(rank)) {
    return "Not available";
  }

  return Math.round(rank).toLocaleString();
}

export function formatRankingScore(score: number | null | undefined): string {
  if (isMissing(score)) {
    return "Not available";
  }

  return Math.round(score).toLocaleString();
}

export function formatIelts(score: number | null | undefined): string {
  if (isMissing(score)) {
    return "Not available";
  }

  return score.toFixed(1);
}
