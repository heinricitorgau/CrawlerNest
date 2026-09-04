"use client";

import { useEffect, useState } from "react";
import {
  confidenceConfig,
  confidencePostureLabel,
  severityConfig,
  sourceAvailabilityConfig,
  spreadToSeverity,
} from "@/lib/analyticsPresentation";

// ── Types ─────────────────────────────────────────────────────────────────────

interface RankingTrendItem {
  canonical_university_id: number;
  university_name: string;
  slug: string;
  country_name: string | null;
  current_year: number;
  current_rank: number | null;
  previous_year: number | null;
  previous_rank: number | null;
  rank_delta: number | null;
  source_count_current: number;
  source_count_previous: number | null;
}

interface RankingTrendsData {
  available_years: number[];
  single_year_only: boolean;
  total_count: number;
  items: RankingTrendItem[];
  evaluation_timestamp: string;
}

interface SourceCoverageItem {
  missing_count: number;
  missing_pct: number;
  covered_count: number;
  covered_pct: number;
}

interface SourceAgreementOutlier {
  canonical_university_id: number;
  university_name: string;
  slug: string;
  aggregated_rank: number | null;
  source_ranks: Record<string, number | null>;
  rank_spread: number;
  confidence: string;
}

interface SourceDisagreementData {
  qs_the_average_rank_difference: number | null;
  universities_with_largest_disagreement: SourceAgreementOutlier[];
  missing_source_coverage: Record<string, SourceCoverageItem>;
  source_overlap: {
    total_universities: number;
    qs_the_overlap_count: number;
    qs_the_overlap_pct: number;
    multi_source_overlap_count: number;
    multi_source_overlap_pct: number;
  };
  confidence_buckets: Record<string, number>;
  analytics_caveats: string[];
  evaluation_timestamp: string;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

type ApiLoadState<T> =
  | { status: "loading" }
  | { status: "ok"; data: T; caveats: string[] }
  | { status: "error"; message: string };

function useApiFetch<T>(path: string): ApiLoadState<T> {
  const [state, setState] = useState<ApiLoadState<T>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    fetch(path, { cache: "no-store" })
      .then(async (res) => {
        const json = (await res.json()) as {
          success?: boolean;
          data?: T;
          metadata?: { caveats?: string[] };
          error?: string;
        };
        if (cancelled) return;
        if (!res.ok || json.success === false) {
          setState({ status: "error", message: json.error ?? `HTTP ${res.status}` });
        } else {
          setState({
            status: "ok",
            data: json.data as T,
            caveats: json.metadata?.caveats ?? [],
          });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof Error ? err.message : "Fetch failed",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [path]);

  return state;
}

// ── UI primitives ─────────────────────────────────────────────────────────────

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-4 border-b border-slate-200 pb-2">
      <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-700">{title}</h2>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-black tracking-tight text-slate-950">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

function LoadingBlock() {
  return <div className="h-24 animate-pulse rounded bg-slate-100" />;
}

function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      {message}
    </div>
  );
}

function DeltaChip({ delta }: { delta: number | null }) {
  if (delta === null) {
    return <span className="text-slate-400">—</span>;
  }
  if (delta > 0) {
    return (
      <span className="rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-xs font-semibold text-emerald-700">
        +{delta}
      </span>
    );
  }
  if (delta < 0) {
    return (
      <span className="rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-xs font-semibold text-red-700">
        {delta}
      </span>
    );
  }
  return <span className="text-xs text-slate-400">0</span>;
}

function formatTs(ts: string | null | undefined): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const trendsState = useApiFetch<RankingTrendsData>("/api/analytics/ranking-trends");
  const disagreementState = useApiFetch<SourceDisagreementData>(
    "/api/analytics/source-disagreement"
  );

  const trends = trendsState.status === "ok" ? trendsState.data : null;
  const trendsCaveats = trendsState.status === "ok" ? trendsState.caveats : [];
  const disagreement = disagreementState.status === "ok" ? disagreementState.data : null;
  const disagreementCaveats =
    disagreementState.status === "ok" ? disagreementState.caveats : [];

  const allCaveats = [
    ...new Set([
      ...trendsCaveats,
      ...disagreementCaveats,
      ...(disagreement?.analytics_caveats ?? []),
    ]),
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <div className="mb-8">
          <h1 className="text-2xl font-black tracking-tight text-slate-950">Analytics</h1>
          <p className="mt-1 text-sm text-slate-500">
            Ranking trends, source agreement, and coverage analysis across aggregated universities.
          </p>
          {trends && (
            <p className="mt-0.5 text-xs text-slate-400">
              Evaluated at {formatTs(trends.evaluation_timestamp)}
            </p>
          )}
        </div>

        {/* ── Single-year notice ── */}
        {trendsState.status === "ok" && trends?.single_year_only && (
          <div className="mb-6 border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Only one year of aggregated data is available. Year-over-year rank deltas are not
            shown. Multiple aggregation runs are required for trend analysis.
          </div>
        )}

        {/* ── Ranking Trends ── */}
        <section className="mb-8">
          <SectionHeader
            title="Ranking Trends"
            sub={
              trends
                ? `${trends.total_count.toLocaleString()} universities · years: ${trends.available_years.join(", ")}`
                : "Year-over-year rank movement across aggregated universities"
            }
          />
          {trendsState.status === "loading" && <LoadingBlock />}
          {trendsState.status === "error" && <ErrorBlock message={trendsState.message} />}
          {trends && (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <StatCard
                  label="Universities"
                  value={trends.total_count.toLocaleString()}
                  sub="with display rank"
                />
                <StatCard
                  label="Years Available"
                  value={trends.available_years.length}
                  sub={trends.available_years.join(", ")}
                />
                <StatCard
                  label="Trend Coverage"
                  value={trends.single_year_only ? "Single year" : "Multi-year"}
                  sub={trends.single_year_only ? "no delta available" : "delta computed"}
                />
              </div>

              {trends.items.length > 0 && (
                <table className="w-full border border-slate-200 bg-white text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      {[
                        "Rank",
                        "University",
                        "Country",
                        trends.single_year_only ? null : "Prev Rank",
                        trends.single_year_only ? null : "Delta",
                        "Sources",
                      ]
                        .filter(Boolean)
                        .map((h) => (
                          <th
                            key={h as string}
                            className="border-b border-slate-200 px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-slate-500"
                          >
                            {h}
                          </th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {trends.items.slice(0, 30).map((row) => (
                      <tr
                        key={row.canonical_university_id}
                        className="border-b border-slate-100 last:border-0"
                      >
                        <td className="px-3 py-2 font-mono text-slate-700">
                          {row.current_rank ?? "—"}
                        </td>
                        <td className="px-3 py-2 font-medium text-slate-900">
                          {row.university_name}
                        </td>
                        <td className="px-3 py-2 text-slate-500">{row.country_name ?? "—"}</td>
                        {!trends.single_year_only && (
                          <>
                            <td className="px-3 py-2 font-mono text-slate-500">
                              {row.previous_rank ?? "—"}
                            </td>
                            <td className="px-3 py-2">
                              <DeltaChip delta={row.rank_delta} />
                            </td>
                          </>
                        )}
                        <td className="px-3 py-2 font-mono text-xs text-slate-400">
                          {row.source_count_current}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {trends.total_count > 30 && (
                <p className="mt-2 text-xs text-slate-400">
                  Showing top 30 of {trends.total_count.toLocaleString()} ranked universities.
                </p>
              )}
            </>
          )}
        </section>

        {/* ── Source Disagreement ── */}
        <section className="mb-8">
          <SectionHeader
            title="Source Disagreement"
            sub="Rank spread between available sources; universities with largest divergence"
          />
          {disagreementState.status === "loading" && <LoadingBlock />}
          {disagreementState.status === "error" && (
            <ErrorBlock message={disagreementState.message} />
          )}
          {disagreement && (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard
                  label="QS/THE Avg Diff"
                  value={
                    disagreement.qs_the_average_rank_difference != null
                      ? disagreement.qs_the_average_rank_difference.toFixed(1)
                      : "—"
                  }
                  sub="rank positions"
                />
                <StatCard
                  label="Total Universities"
                  value={(disagreement.source_overlap.total_universities ?? 0).toLocaleString()}
                  sub="in aggregated set"
                />
                <StatCard
                  label="High Confidence"
                  value={(disagreement.confidence_buckets.high ?? 0).toLocaleString()}
                  sub="agreement bucket"
                />
                <StatCard
                  label="Low Confidence"
                  value={(disagreement.confidence_buckets.low ?? 0).toLocaleString()}
                  sub="agreement bucket"
                />
              </div>

              {disagreement.universities_with_largest_disagreement.length > 0 && (
                <table className="w-full border border-slate-200 bg-white text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      {["University", "Aggregated", "QS", "THE", "ARWU", "Spread", "Confidence"].map(
                        (h) => (
                          <th
                            key={h}
                            className="border-b border-slate-200 px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-slate-500"
                          >
                            {h}
                          </th>
                        )
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {disagreement.universities_with_largest_disagreement.slice(0, 10).map((row) => (
                      <tr
                        key={row.canonical_university_id}
                        className="border-b border-slate-100 last:border-0"
                      >
                        <td className="px-3 py-2 font-medium text-slate-900">
                          {row.university_name}
                        </td>
                        <td className="px-3 py-2 font-mono">{row.aggregated_rank ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{row.source_ranks.QS ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{row.source_ranks.THE ?? "—"}</td>
                        <td className="px-3 py-2 font-mono">{row.source_ranks.ARWU ?? "—"}</td>
                        <td className="px-3 py-2">
                          <span className="font-mono text-slate-700">{row.rank_spread}</span>
                          <span
                            className={`ml-2 rounded border px-1.5 py-0.5 text-xs font-semibold ${severityConfig(spreadToSeverity(row.rank_spread)).badgeCls}`}
                          >
                            {severityConfig(spreadToSeverity(row.rank_spread)).label}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`rounded border px-1.5 py-0.5 text-xs font-semibold uppercase ${confidenceConfig(row.confidence).badgeCls}`}
                          >
                            {confidenceConfig(row.confidence).label}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </section>

        {/* ── Source Coverage ── */}
        <section className="mb-8">
          <SectionHeader
            title="Source Coverage"
            sub="Percentage of aggregated universities covered by each ranking source"
          />
          {disagreementState.status === "loading" && <LoadingBlock />}
          {disagreementState.status === "error" && (
            <ErrorBlock message={disagreementState.message} />
          )}
          {disagreement && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {Object.entries(disagreement.missing_source_coverage).map(([source, item]) => {
                const available = item.covered_pct > 0;
                const availCfg = sourceAvailabilityConfig(available);
                return (
                  <div key={source} className="border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                        {source} Coverage
                      </div>
                      <span
                        className={`rounded border px-2 py-0.5 text-xs font-semibold ${availCfg.badgeCls}`}
                      >
                        {availCfg.icon} {availCfg.statusLabel}
                      </span>
                    </div>
                    <div className="mt-3">
                      <div className="mb-1 text-xs text-slate-500">
                        {item.covered_pct.toFixed(1)}% covered
                      </div>
                      <div className="h-2 bg-slate-100">
                        <div
                          className={`h-2 ${available ? "bg-blue-600" : "bg-slate-200"}`}
                          style={{ width: `${Math.max(0, Math.min(100, item.covered_pct))}%` }}
                        />
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-slate-500">
                      {item.covered_count.toLocaleString()} covered,{" "}
                      {item.missing_count.toLocaleString()} missing
                    </div>
                    {!available && (
                      <div className="mt-2 text-xs text-slate-500">
                        No ranks ingested from this source.
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {disagreement &&
            Object.keys(disagreement.missing_source_coverage).length === 0 && (
              <p className="text-sm text-slate-500">No source coverage data available.</p>
            )}
        </section>

        {/* ── Operational Posture ── */}
        <section className="mb-8">
          <SectionHeader
            title="Operational Posture"
            sub="System self-assessment: source coverage, confidence distribution, and data posture"
          />
          {disagreementState.status === "loading" && <LoadingBlock />}
          {disagreement && (
            <div className="space-y-4">
              <div className="border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                  Source Availability
                </div>
                <div className="flex flex-wrap gap-2">
                  {(["QS", "THE", "ARWU"] as const).map((src) => {
                    const item = disagreement.missing_source_coverage[src];
                    const available = item != null && item.covered_pct > 0;
                    const cfg = sourceAvailabilityConfig(available);
                    return (
                      <span
                        key={src}
                        className={`rounded border px-3 py-1 text-xs font-semibold ${cfg.badgeCls}`}
                      >
                        {src} {cfg.icon} {cfg.statusLabel}
                      </span>
                    );
                  })}
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  QS, THE and ARWU are all ingested, with partial coverage: most universities
                  carry a QS rank and far fewer carry THE or ARWU. Where a university has only
                  one source, no agreement analysis is possible for it. A missing rank is a gap
                  in what was ingested and matched here, not the source declining to rank it.
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <StatCard
                  label="Confidence Posture"
                  value={confidencePostureLabel(disagreement.confidence_buckets)}
                  sub="derived from source coverage and data completeness"
                />
                <StatCard
                  label="Freshness Detail"
                  value="/system-status"
                  sub="ingestion timestamps and pipeline state"
                />
              </div>
            </div>
          )}
        </section>

        {/* ── Analytics Caveats ── */}
        <section className="mb-8">
          <SectionHeader
            title="Analytics Caveats"
            sub="Known data limitations. Read before interpreting any analytics."
          />
          {(trendsState.status === "loading" || disagreementState.status === "loading") && (
            <LoadingBlock />
          )}
          {trendsState.status !== "loading" && disagreementState.status !== "loading" && (
            <>
              {allCaveats.length === 0 ? (
                <p className="text-sm text-slate-500">No caveats returned by the API.</p>
              ) : (
                <ul className="space-y-2">
                  {allCaveats.map((caveat, i) => (
                    <li
                      key={i}
                      className="border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
                    >
                      {caveat}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
