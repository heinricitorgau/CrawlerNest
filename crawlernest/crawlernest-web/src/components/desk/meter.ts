/** Small helpers shared by the score ring and the progress bars. */

export function clampPercent(value: number, max = 100): number {
  if (!Number.isFinite(value) || max <= 0) return 0;
  return Math.min(100, Math.max(0, (value / max) * 100));
}

export type MeterTone = "strong" | "steady" | "weak";

/** One threshold table for every meter, so a ring and a bar never disagree on what "weak" means. */
export function toneFor(percent: number): MeterTone {
  if (percent >= 80) return "strong";
  if (percent >= 60) return "steady";
  return "weak";
}

export const TONE_STROKE: Record<MeterTone, string> = {
  strong: "stroke-emerald-500",
  steady: "stroke-blue-500",
  weak: "stroke-amber-500",
};

export const TONE_FILL: Record<MeterTone, string> = {
  strong: "bg-emerald-500",
  steady: "bg-blue-500",
  weak: "bg-amber-500",
};

const DAY_MS = 24 * 60 * 60 * 1000;

/** Whole days from `today` to `isoDate` (negative when past). Both are read as UTC dates. */
export function daysUntil(isoDate: string, today: Date): number {
  const due = Date.parse(`${isoDate}T00:00:00Z`);
  const base = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.round((due - base) / DAY_MS);
}

export function formatShortDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
