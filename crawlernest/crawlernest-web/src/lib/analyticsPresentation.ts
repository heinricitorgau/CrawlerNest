// Unified presentation helpers for analytics and recommendation surfaces.
// Centralising here prevents color, label, and wording drift across pages.

export type ConfidenceLevel = "high" | "medium" | "low" | "unknown" | string;

export interface ConfidenceConfig {
  label: string;
  badgeCls: string;
  barCls: string;
  pct: number;
}

export function confidenceConfig(level: ConfidenceLevel): ConfidenceConfig {
  switch ((level ?? "").toLowerCase()) {
    case "high":
      return {
        label: "High",
        badgeCls: "border-emerald-200 bg-emerald-50 text-emerald-700",
        barCls: "bg-emerald-500",
        pct: 85,
      };
    case "medium":
      return {
        label: "Medium",
        badgeCls: "border-amber-200 bg-amber-50 text-amber-700",
        barCls: "bg-amber-400",
        pct: 55,
      };
    case "low":
      return {
        label: "Low",
        badgeCls: "border-red-200 bg-red-50 text-red-700",
        barCls: "bg-red-400",
        pct: 25,
      };
    default:
      return {
        label: level || "Unknown",
        badgeCls: "border-slate-200 bg-slate-50 text-slate-500",
        barCls: "bg-slate-300",
        pct: 0,
      };
  }
}

export type DisagreementSeverity = "high" | "medium" | "low";

export function spreadToSeverity(spread: number): DisagreementSeverity {
  if (spread >= 200) return "high";
  if (spread >= 50) return "medium";
  return "low";
}

export interface SeverityConfig {
  label: string;
  badgeCls: string;
}

export function severityConfig(sev: DisagreementSeverity): SeverityConfig {
  switch (sev) {
    case "high":
      return { label: "High", badgeCls: "border-red-200 bg-red-50 text-red-700" };
    case "medium":
      return { label: "Medium", badgeCls: "border-amber-200 bg-amber-50 text-amber-700" };
    case "low":
      return { label: "Low", badgeCls: "border-emerald-200 bg-emerald-50 text-emerald-700" };
  }
}

export interface SourceAvailabilityConfig {
  statusLabel: string;
  badgeCls: string;
  icon: string;
}

export function sourceAvailabilityConfig(available: boolean): SourceAvailabilityConfig {
  return available
    ? {
        statusLabel: "Available",
        badgeCls: "border-emerald-200 bg-emerald-50 text-emerald-700",
        icon: "✓",
      }
    : {
        statusLabel: "Unavailable",
        badgeCls: "border-slate-200 bg-slate-50 text-slate-400",
        icon: "—",
      };
}

export function stalenessLabel(ageHours: number | null | undefined): string {
  if (ageHours == null) return "Unknown freshness";
  if (ageHours < 24) return `Fresh (${Math.round(ageHours)}h)`;
  const days = Math.round(ageHours / 24);
  if (days <= 3) return `Stale (${days}d)`;
  return `Stale (${days}d — critical)`;
}

export function stalenessBadgeCls(ageHours: number | null | undefined): string {
  if (ageHours == null) return "border-slate-200 bg-slate-50 text-slate-400";
  if (ageHours < 24) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (ageHours < 72) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-red-200 bg-red-50 text-red-700";
}

export function confidencePostureLabel(buckets: Record<string, number>): string {
  const total = Object.values(buckets).reduce((a, b) => a + b, 0);
  if (total === 0) return "Unknown";
  const highPct = ((buckets.high ?? 0) / total) * 100;
  if (highPct >= 60) return "Mostly High";
  if (highPct >= 30) return "Mixed";
  return "Mostly Low";
}
