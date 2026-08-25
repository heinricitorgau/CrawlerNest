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

export function formatToefl(score: number | null | undefined): string {
  if (isMissing(score)) {
    return "Not available";
  }

  return Math.round(score).toString();
}

export function formatDuolingo(score: number | null | undefined): string {
  if (isMissing(score)) {
    return "Not available";
  }

  return Math.round(score).toString();
}

export function formatGpa(gpa: number | null | undefined): string {
  if (isMissing(gpa)) {
    return "Not available";
  }

  // GPAs are quoted to two decimals at most, and a trailing zero reads as
  // precision the source did not claim: 3.5 stays "3.5", 3.45 stays "3.45".
  return String(Number(gpa.toFixed(2)));
}

/**
 * Formats an ISO-8601 `yyyy-MM-dd` deadline for display.
 *
 * Parsed as UTC on purpose. `new Date("2026-01-15")` is already UTC midnight, but
 * formatting it in the viewer's local zone shows 14 January anywhere west of
 * Greenwich, which silently moves an application deadline a day earlier.
 */
export function formatDeadline(deadline: string | null | undefined): string {
  if (deadline === null || deadline === undefined || deadline === "") {
    return "Not available";
  }

  const parsed = new Date(`${deadline}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return "Not available";
  }

  return parsed.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** Turns `postgraduate` into `Postgraduate` for display. */
export function formatDegreeLevel(degreeLevel: string | null | undefined): string {
  if (!degreeLevel) {
    return "All levels";
  }

  return degreeLevel.charAt(0).toUpperCase() + degreeLevel.slice(1);
}
