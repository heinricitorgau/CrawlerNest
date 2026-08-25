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

/**
 * Formats an ISO-8601 timestamp for a "last edited" label.
 *
 * Recent entries read as a relative age, because "3 minutes ago" answers the
 * question a saved-conversation list actually raises -- which of these did I
 * just touch -- faster than a wall-clock time does. Anything older than a day
 * falls back to a date, where the exact time stops carrying information.
 *
 * Rendered in the viewer's own timezone on purpose: unlike an application
 * deadline, this describes something the viewer did themselves.
 */
export function formatTimestamp(
  timestamp: string | null | undefined,
  now: Date = new Date()
): string {
  if (!timestamp) {
    return "Unknown";
  }

  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return "Unknown";
  }

  const elapsedMs = now.getTime() - parsed.getTime();
  const minutes = Math.floor(elapsedMs / 60_000);

  // A clock skew of a few seconds should not read as "in the future".
  if (minutes < 1) {
    return "Just now";
  }
  if (minutes < 60) {
    return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  }

  return parsed.toLocaleDateString("en-CA", { dateStyle: "medium" });
}
