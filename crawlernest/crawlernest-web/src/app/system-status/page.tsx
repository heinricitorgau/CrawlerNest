"use client";

import { useEffect, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface HealthData {
  postgres_connected: boolean;
  aggregated_rankings_count: number;
  subject_rankings_count: number;
  latest_ranking_year: number | null;
  latest_subject_year: number | null;
  sources: Array<{ source_code: string; year: number; count: number }>;
}

interface IngestionLogEntry {
  source_code: string;
  batch_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  records_in: number;
  matched_count: number;
  unresolved_count: number;
  inserted_count: number;
  updated_count: number;
}

interface RankingsDiagData {
  source_counts: Array<{ source_code: string; year: number; count: number }>;
  unresolved_university_count: number;
  duplicate_resolution_count: number;
  aggregated_latest_count: number;
  ingestion_log: IngestionLogEntry[];
  latest_aggregation_run_id: number | null;
  latest_aggregation_year: number | null;
  latest_aggregation_status: string | null;
  latest_aggregation_timestamp: string | null;
  latest_aggregation_output_count: number;
}

interface SubjectEntry {
  subject_key: string;
  subject_name: string;
  row_count: number;
  university_count: number;
  latest_year: number | null;
}

interface SubjectsDiagData {
  by_subject: SubjectEntry[];
  country_coverage: Array<{ subject_key: string; country_name: string; count: number }>;
  top_missing_countries: Array<{ country_name: string; global_ranking_count: number }>;
}

interface SourceFreshness {
  source_code: string;
  latest_ingested_at: string | null;
  latest_updated_at: string | null;
  latest_year: number | null;
  record_count: number;
  age_hours: number | null;
  stale: boolean;
  missing: boolean;
}

interface SubjectFreshness {
  subject_key: string;
  subject_name: string;
  latest_ingested_at: string | null;
  latest_year: number | null;
  record_count: number;
  age_hours: number | null;
  stale: boolean;
  missing: boolean;
}

interface AggregationFreshness {
  latest_run_id: number | null;
  ranking_year: number | null;
  status: string | null;
  latest_at: string | null;
  age_hours: number | null;
  stale: boolean;
  behind_ingestion: boolean;
  output_count: number;
}

interface FreshnessData {
  global_rankings: SourceFreshness[];
  missing_sources: string[];
  subject_rankings: SubjectFreshness[];
  aggregation: AggregationFreshness;
  overall_stale: boolean;
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

type LoadState<T> =
  | { status: "loading" }
  | { status: "ok"; data: T }
  | { status: "error"; message: string };

function useJsonFetch<T>(path: string): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    fetch(path, { cache: "no-store" })
      .then(async (res) => {
        const json = (await res.json()) as {
          success?: boolean;
          data?: T;
          error?: string;
        };
        if (cancelled) return;
        if (!res.ok || json.success === false) {
          setState({ status: "error", message: json.error ?? `HTTP ${res.status}` });
        } else {
          setState({ status: "ok", data: json.data as T });
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

// ── Shared UI primitives ───────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-black tracking-tight text-slate-950">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-4 border-b border-slate-200 pb-2">
      <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-700">{title}</h2>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
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

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`}
    />
  );
}

function StaleChip({ stale, missing }: { stale: boolean; missing: boolean }) {
  if (missing) {
    return (
      <span className="rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-xs font-semibold text-red-700">
        MISSING
      </span>
    );
  }
  if (stale) {
    return (
      <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-xs font-semibold text-amber-700">
        STALE
      </span>
    );
  }
  return (
    <span className="rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-xs font-semibold text-emerald-700">
      FRESH
    </span>
  );
}

function formatTs(ts: string | null | undefined): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function formatAge(hours: number | null | undefined): string {
  if (hours == null) return "—";
  if (hours < 1) return "< 1 hour ago";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h ago`;
}

// ── Operational context types ─────────────────────────────────────────────────

interface LastPipelineRun {
  run_id: number | null;
  ranking_year: number | null;
  status: string | null;
  finished_at: string | null;
  age_hours: number | null;
  output_count: number;
}

interface LastIngestion {
  source_code: string | null;
  batch_id: string | null;
  started_at: string | null;
  age_hours: number | null;
  records_in: number;
  unresolved_count: number;
}

interface UnresolvedTrend {
  total: number;
  last_7d: number;
  prior_7d: number;
  trend_pct: number | null;
  trend_direction: "increasing" | "decreasing" | "stable";
}

interface OperationalStatusData {
  last_pipeline_run: LastPipelineRun;
  last_ingestion: LastIngestion;
  unresolved_trend: UnresolvedTrend;
}

interface SnapshotInfo {
  has_snapshot: boolean;
  snapshot_timestamp: string | null;
  snapshot_file: string | null;
  drift_warning_count: number | null;
  unresolved_total: number | null;
  unresolved_last_7d: number | null;
  unresolved_trend_pct: number | null;
  last_aggregation_at: string | null;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SystemStatusPage() {
  const healthState = useJsonFetch<HealthData>("/api/health");
  const rankingsDiagState = useJsonFetch<RankingsDiagData>("/api/diagnostics/rankings");
  const subjectsDiagState = useJsonFetch<SubjectsDiagData>("/api/diagnostics/subjects");
  const freshnessState = useJsonFetch<FreshnessData>("/api/freshness");
  const opsState = useJsonFetch<OperationalStatusData>("/api/diagnostics/operational-status");
  const snapshotState = useJsonFetch<SnapshotInfo>("/api/snapshot-info");

  const health = healthState.status === "ok" ? healthState.data : null;
  const rankingsDiag = rankingsDiagState.status === "ok" ? rankingsDiagState.data : null;
  const subjectsDiag = subjectsDiagState.status === "ok" ? subjectsDiagState.data : null;
  const freshness = freshnessState.status === "ok" ? freshnessState.data : null;
  const ops = opsState.status === "ok" ? opsState.data : null;
  const snapshot = snapshotState.status === "ok" ? snapshotState.data : null;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-blue-700">
            Internal
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
            System Status
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Product-level health, data freshness, and ingestion diagnostics.
          </p>
        </div>
      </div>

      <div className="mx-auto max-w-7xl space-y-10 px-6 py-8 lg:px-8">

        {/* ── Operational Context ─────────────────────────── */}
        <section>
          <SectionHeader
            title="Operational Context"
            sub="Last pipeline run, ingestion batch, unresolved trend, and latest snapshot."
          />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Last pipeline run */}
            <StatCard
              label="Last Pipeline Run"
              value={
                ops?.last_pipeline_run?.run_id != null
                  ? `Run #${ops.last_pipeline_run.run_id}`
                  : opsState.status === "loading" ? "…" : "—"
              }
              sub={
                ops?.last_pipeline_run?.finished_at
                  ? `${formatTs(ops.last_pipeline_run.finished_at)} · ${formatAge(ops.last_pipeline_run.age_hours)}`
                  : ops?.last_pipeline_run?.status === "never_run"
                  ? "No pipeline run recorded yet"
                  : opsState.status === "error"
                  ? "API unavailable"
                  : undefined
              }
            />

            {/* Last ingestion */}
            <StatCard
              label="Last Ingestion"
              value={
                ops?.last_ingestion?.source_code
                  ? ops.last_ingestion.source_code
                  : opsState.status === "loading" ? "…" : "—"
              }
              sub={
                ops?.last_ingestion?.started_at
                  ? `${formatTs(ops.last_ingestion.started_at)} · ${ops.last_ingestion.records_in} records`
                  : undefined
              }
            />

            {/* Unresolved trend */}
            <StatCard
              label="Unresolved (7d trend)"
              value={
                ops?.unresolved_trend != null
                  ? ops.unresolved_trend.total.toLocaleString()
                  : opsState.status === "loading" ? "…" : "—"
              }
              sub={
                ops?.unresolved_trend
                  ? (() => {
                      const t = ops.unresolved_trend;
                      const arrow =
                        t.trend_direction === "increasing" ? "▲"
                        : t.trend_direction === "decreasing" ? "▼"
                        : "→";
                      const pct = t.trend_pct != null ? ` ${Math.abs(t.trend_pct).toFixed(1)}%` : "";
                      return `${arrow}${pct} vs prior 7 days · ${t.last_7d} new`;
                    })()
                  : undefined
              }
            />

            {/* Latest snapshot */}
            <StatCard
              label="Latest Snapshot"
              value={
                snapshot?.has_snapshot
                  ? "Available"
                  : snapshotState.status === "loading" ? "…" : "No snapshot"
              }
              sub={
                snapshot?.has_snapshot && snapshot.snapshot_timestamp
                  ? formatTs(snapshot.snapshot_timestamp)
                  : snapshot?.has_snapshot === false
                  ? "Run export_system_snapshot.py to generate"
                  : undefined
              }
            />
          </div>

          {/* Snapshot drift banner */}
          {snapshot?.has_snapshot && (snapshot.drift_warning_count ?? 0) > 0 && (
            <div className="mt-3 border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {snapshot.drift_warning_count} drift warning
              {snapshot.drift_warning_count !== 1 ? "s" : ""} in latest snapshot — see{" "}
              <a href="/data-quality" className="underline">Data Quality</a> for details.
            </div>
          )}
        </section>

        {/* ── Data Freshness ──────────────────────────────── */}
        <section>
          <SectionHeader
            title="Data Freshness"
            sub="Staleness detection: sources older than 30 days are flagged. Aggregation lag is shown when it trails ingestion."
          />

          {freshnessState.status === "loading" && <LoadingBlock />}
          {freshnessState.status === "error" && (
            <ErrorBlock message={`Freshness API unavailable: ${freshnessState.message}`} />
          )}
          {freshness && (
            <div className="space-y-4">
              {/* Overall stale banner */}
              {freshness.overall_stale && (
                <div className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-800">
                  One or more data sources are stale or missing.{" "}
                  <a href="#freshness-table" className="underline hover:text-amber-900">
                    Review the table below.
                  </a>
                </div>
              )}
              {!freshness.overall_stale && (
                <div className="border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">
                  All active data sources are fresh. No stale warnings.
                </div>
              )}

              {/* Global ranking sources */}
              <div id="freshness-table" className="border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-100 px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                  Global Ranking Sources
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <th className="px-4 py-2 text-left">Source</th>
                      <th className="px-4 py-2 text-left">Status</th>
                      <th className="px-4 py-2 text-left">Last Ingested</th>
                      <th className="px-4 py-2 text-right">Age</th>
                      <th className="px-4 py-2 text-right">Records</th>
                      <th className="px-4 py-2 text-right">Year</th>
                    </tr>
                  </thead>
                  <tbody>
                    {freshness.global_rankings.map((src) => (
                      <tr key={src.source_code} className="border-b border-slate-50">
                        <td className="px-4 py-2 font-bold">{src.source_code}</td>
                        <td className="px-4 py-2">
                          <StaleChip stale={src.stale} missing={src.missing} />
                        </td>
                        <td className="px-4 py-2 text-xs text-slate-500">
                          {formatTs(src.latest_ingested_at)}
                        </td>
                        <td className="px-4 py-2 text-right text-xs text-slate-500">
                          {formatAge(src.age_hours)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono">
                          {Number(src.record_count).toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right text-slate-500">
                          {src.latest_year ?? "—"}
                        </td>
                      </tr>
                    ))}
                    {freshness.missing_sources.length > 0 && (
                      freshness.missing_sources
                        .filter((s) => !freshness.global_rankings.some((r) => r.source_code === s))
                        .map((src) => (
                          <tr key={`missing-${src}`} className="border-b border-slate-50 bg-red-50">
                            <td className="px-4 py-2 font-bold text-red-700">{src}</td>
                            <td className="px-4 py-2">
                              <StaleChip stale missing />
                            </td>
                            <td colSpan={4} className="px-4 py-2 text-xs text-red-600">
                              No data ingested yet
                            </td>
                          </tr>
                        ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Subject rankings freshness */}
              <div className="border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-100 px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                  Subject Rankings
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <th className="px-4 py-2 text-left">Subject</th>
                      <th className="px-4 py-2 text-left">Status</th>
                      <th className="px-4 py-2 text-left">Last Ingested</th>
                      <th className="px-4 py-2 text-right">Age</th>
                      <th className="px-4 py-2 text-right">Records</th>
                    </tr>
                  </thead>
                  <tbody>
                    {freshness.subject_rankings.map((subj) => (
                      <tr key={subj.subject_key} className="border-b border-slate-50">
                        <td className="px-4 py-2 font-medium">{subj.subject_name}</td>
                        <td className="px-4 py-2">
                          <StaleChip stale={subj.stale} missing={subj.missing} />
                        </td>
                        <td className="px-4 py-2 text-xs text-slate-500">
                          {formatTs(subj.latest_ingested_at)}
                        </td>
                        <td className="px-4 py-2 text-right text-xs text-slate-500">
                          {formatAge(subj.age_hours)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono">
                          {Number(subj.record_count).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Aggregation freshness */}
              <div className="grid gap-4 sm:grid-cols-3">
                <StatCard
                  label="Last Aggregation"
                  value={freshness.aggregation.latest_run_id != null
                    ? `Run #${freshness.aggregation.latest_run_id}` : "—"}
                  sub={freshness.aggregation.latest_at
                    ? formatTs(freshness.aggregation.latest_at)
                    : "No aggregation run recorded"}
                />
                <StatCard
                  label="Aggregation Age"
                  value={formatAge(freshness.aggregation.age_hours)}
                  sub={freshness.aggregation.stale ? "Stale (> 30 days)" : "Within threshold"}
                />
                <StatCard
                  label="Aggregation Lag"
                  value={freshness.aggregation.behind_ingestion ? "Behind" : "Current"}
                  sub={freshness.aggregation.behind_ingestion
                    ? "Aggregation finished before the latest ingestion"
                    : "Aggregation reflects latest ingestion"}
                />
              </div>
            </div>
          )}
        </section>

        {/* ── Health Overview ─────────────────────────────── */}
        <section>
          <SectionHeader
            title="Health Overview"
            sub="Live summary from the Spring Boot API and PostgreSQL."
          />

          {healthState.status === "loading" && <LoadingBlock />}
          {healthState.status === "error" && (
            <ErrorBlock message={`Health API unavailable: ${healthState.message}`} />
          )}
          {health && (
            <>
              <div className="mb-4 flex items-center gap-2">
                <StatusDot ok={health.postgres_connected} />
                <span className="text-sm font-medium text-slate-700">
                  PostgreSQL {health.postgres_connected ? "connected" : "not connected"}
                </span>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                  label="Aggregated Rankings"
                  value={health.aggregated_rankings_count.toLocaleString()}
                  sub={
                    health.latest_ranking_year
                      ? `Latest year: ${health.latest_ranking_year}`
                      : "No data yet"
                  }
                />
                <StatCard
                  label="Subject Rankings"
                  value={health.subject_rankings_count.toLocaleString()}
                  sub={
                    health.latest_subject_year
                      ? `Latest year: ${health.latest_subject_year}`
                      : "No subject data loaded"
                  }
                />
                {health.sources.map((src) => (
                  <StatCard
                    key={`${src.source_code}-${src.year}`}
                    label={`${src.source_code} Source Records`}
                    value={Number(src.count).toLocaleString()}
                    sub={`Year: ${src.year}`}
                  />
                ))}
              </div>
            </>
          )}
        </section>

        {/* ── Rankings Diagnostics ────────────────────────── */}
        <section>
          <SectionHeader
            title="Rankings Diagnostics"
            sub="Ingestion volume, resolution quality, and aggregation status."
          />

          {rankingsDiagState.status === "loading" && <LoadingBlock />}
          {rankingsDiagState.status === "error" && (
            <ErrorBlock message={`Diagnostics unavailable: ${rankingsDiagState.message}`} />
          )}
          {rankingsDiag && (
            <div className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard
                  label="Aggregated (Latest)"
                  value={rankingsDiag.aggregated_latest_count.toLocaleString()}
                />
                <StatCard
                  label="Unresolved Universities"
                  value={rankingsDiag.unresolved_university_count.toLocaleString()}
                  sub="From missing_entity_log"
                />
                <StatCard
                  label="Duplicate Saves"
                  value={rankingsDiag.duplicate_resolution_count.toLocaleString()}
                  sub="From merge_diagnostics"
                />
                <StatCard
                  label="Latest Aggregation Run"
                  value={
                    rankingsDiag.latest_aggregation_run_id != null
                      ? `#${rankingsDiag.latest_aggregation_run_id}`
                      : "—"
                  }
                  sub={
                    rankingsDiag.latest_aggregation_status
                      ? `${rankingsDiag.latest_aggregation_status} · ${formatTs(rankingsDiag.latest_aggregation_timestamp)}`
                      : "No run recorded"
                  }
                />
              </div>

              {rankingsDiag.source_counts.length > 0 && (
                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                    Source Record Counts
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <th className="px-4 py-2 text-left">Source</th>
                        <th className="px-4 py-2 text-left">Year</th>
                        <th className="px-4 py-2 text-right">Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rankingsDiag.source_counts.map((row) => (
                        <tr
                          key={`${row.source_code}-${row.year}`}
                          className="border-b border-slate-50"
                        >
                          <td className="px-4 py-2 font-medium">{row.source_code}</td>
                          <td className="px-4 py-2 text-slate-500">{row.year}</td>
                          <td className="px-4 py-2 text-right font-mono">
                            {Number(row.count).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {rankingsDiag.ingestion_log.length > 0 && (
                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                    Recent Ingestion Runs
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                          <th className="px-4 py-2 text-left">Source</th>
                          <th className="px-4 py-2 text-left">Batch</th>
                          <th className="px-4 py-2 text-left">Started</th>
                          <th className="px-4 py-2 text-right">In</th>
                          <th className="px-4 py-2 text-right">Matched</th>
                          <th className="px-4 py-2 text-right">Unresolved</th>
                          <th className="px-4 py-2 text-right">Inserted</th>
                          <th className="px-4 py-2 text-right">Updated</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rankingsDiag.ingestion_log.map((row, i) => (
                          <tr key={i} className="border-b border-slate-50">
                            <td className="px-4 py-2 font-medium">{row.source_code}</td>
                            <td className="px-4 py-2 font-mono text-xs text-slate-500">
                              {row.batch_id ?? "—"}
                            </td>
                            <td className="px-4 py-2 text-xs text-slate-500">
                              {formatTs(row.started_at)}
                            </td>
                            <td className="px-4 py-2 text-right font-mono">{row.records_in}</td>
                            <td className="px-4 py-2 text-right font-mono text-emerald-700">
                              {row.matched_count}
                            </td>
                            <td className="px-4 py-2 text-right font-mono text-amber-700">
                              {row.unresolved_count}
                            </td>
                            <td className="px-4 py-2 text-right font-mono">{row.inserted_count}</td>
                            <td className="px-4 py-2 text-right font-mono">{row.updated_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── Subject Coverage ────────────────────────────── */}
        <section>
          <SectionHeader
            title="Subject Coverage"
            sub="Subject ranking ingestion status and country coverage gaps."
          />

          {subjectsDiagState.status === "loading" && <LoadingBlock />}
          {subjectsDiagState.status === "error" && (
            <ErrorBlock
              message={`Subject diagnostics unavailable: ${subjectsDiagState.message}`}
            />
          )}
          {subjectsDiag && (
            <div className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {subjectsDiag.by_subject.map((s) => (
                  <div key={s.subject_key} className="border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                      {s.subject_name}
                    </div>
                    <div className="mt-2 flex items-end gap-3">
                      <div>
                        <div className="text-2xl font-black tracking-tight text-slate-950">
                          {Number(s.row_count).toLocaleString()}
                        </div>
                        <div className="text-xs text-slate-400">rows</div>
                      </div>
                      <div className="pb-0.5 text-slate-400">·</div>
                      <div>
                        <div className="text-xl font-bold text-slate-700">
                          {Number(s.university_count).toLocaleString()}
                        </div>
                        <div className="text-xs text-slate-400">universities</div>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-slate-400">
                      {s.latest_year ? `Latest year: ${s.latest_year}` : "No data loaded yet"}
                    </div>
                    {s.row_count === 0 && (
                      <div className="mt-2 border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
                        Run the subject pipeline to load data.
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {subjectsDiag.country_coverage.length > 0 && (
                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                    Country Coverage (Top 20)
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <th className="px-4 py-2 text-left">Subject</th>
                        <th className="px-4 py-2 text-left">Country</th>
                        <th className="px-4 py-2 text-right">Universities</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subjectsDiag.country_coverage.map((row, i) => (
                        <tr key={i} className="border-b border-slate-50">
                          <td className="px-4 py-2 font-mono text-xs text-slate-500">
                            {row.subject_key}
                          </td>
                          <td className="px-4 py-2 font-medium">{row.country_name}</td>
                          <td className="px-4 py-2 text-right font-mono">
                            {Number(row.count).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {subjectsDiag.top_missing_countries.length > 0 && (
                <div className="border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-100 px-4 py-3 text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
                    Top Missing Countries
                  </div>
                  <p className="px-4 pt-2 text-xs text-slate-400">
                    Countries with universities in global rankings but no subject ranking records.
                  </p>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <th className="px-4 py-2 text-left">Country</th>
                        <th className="px-4 py-2 text-right">Global Ranking Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subjectsDiag.top_missing_countries.map((row) => (
                        <tr key={row.country_name} className="border-b border-slate-50">
                          <td className="px-4 py-2 font-medium">{row.country_name}</td>
                          <td className="px-4 py-2 text-right font-mono text-amber-700">
                            {Number(row.global_ranking_count).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
