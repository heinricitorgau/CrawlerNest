"use client";

import { useEffect, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface UnresolvedExample {
  source_code: string;
  raw_name: string;
  country_hint: string | null;
  ranking_year: number | null;
}

interface UnresolvedSection {
  total: number;
  by_source: Array<{ source_code: string; count: number }>;
  top_examples: UnresolvedExample[];
}

interface DuplicatesSection {
  total_duplicate_saves: number;
  by_source: Array<{ source_code: string; duplicate_resolution_saves: number }>;
}

interface DriftWarning {
  source_code: string;
  warning_type: string;
  message: string;
  previous_count?: number;
  current_count?: number;
  drop_pct?: number;
  previous_unresolved?: number;
  current_unresolved?: number;
}

interface RegressionSummary {
  aggregated_count: number;
  score_min: number | null;
  score_max: number | null;
  score_avg: number | null;
  low_coverage_count: number;
}

interface LowConfidenceMatch {
  source_name: string;
  confidence_score: number;
  match_method: string;
  canonical_slug: string;
  display_name: string;
}

interface LowConfidenceSection {
  threshold: number;
  count: number;
  examples: LowConfidenceMatch[];
}

interface DataQualityData {
  unresolved: UnresolvedSection;
  duplicates: DuplicatesSection;
  drift_warnings: DriftWarning[];
  regression_summary: RegressionSummary;
  low_confidence_matches: LowConfidenceSection;
  evaluation_timestamp: string;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

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

    return () => { cancelled = true; };
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

function WarnChip({ type }: { type: string }) {
  const colors: Record<string, string> = {
    count_drop: "border-red-200 bg-red-50 text-red-700",
    unresolved_spike: "border-amber-200 bg-amber-50 text-amber-700",
    source_empty: "border-red-200 bg-red-50 text-red-700",
    rank_range_shrink: "border-amber-200 bg-amber-50 text-amber-700",
    score_distribution_shift: "border-amber-200 bg-amber-50 text-amber-700",
    country_disappearance: "border-orange-200 bg-orange-50 text-orange-700",
  };
  const cls = colors[type] ?? "border-slate-200 bg-slate-50 text-slate-700";
  return (
    <span className={`rounded border px-1.5 py-0.5 text-xs font-semibold ${cls}`}>
      {type.replace(/_/g, " ").toUpperCase()}
    </span>
  );
}

function formatTs(ts: string | null | undefined): string {
  if (!ts) return "—";
  try { return new Date(ts).toLocaleString(); } catch { return ts; }
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DataQualityPage() {
  const dqState = useJsonFetch<DataQualityData>("/api/diagnostics/data-quality");
  const dq = dqState.status === "ok" ? dqState.data : null;

  const hasDriftWarnings = (dq?.drift_warnings?.length ?? 0) > 0;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <div className="mb-8">
          <h1 className="text-2xl font-black tracking-tight text-slate-950">Data Quality</h1>
          <p className="mt-1 text-sm text-slate-500">
            Canonical matching confidence, source drift, unresolved universities, and regression
            coverage.
          </p>
          {dq && (
            <p className="mt-0.5 text-xs text-slate-400">
              Evaluated at {formatTs(dq.evaluation_timestamp)}
            </p>
          )}
        </div>

        {/* ── Drift banner ── */}
        {dqState.status === "ok" && hasDriftWarnings && (
          <div className="mb-6 border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {dq!.drift_warnings.length} source drift warning
            {dq!.drift_warnings.length !== 1 ? "s" : ""} detected. Review the table below.
          </div>
        )}
        {dqState.status === "ok" && !hasDriftWarnings && (
          <div className="mb-6 border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            No source drift warnings.
          </div>
        )}

        {/* ── Regression Summary ── */}
        <section className="mb-8">
          <SectionHeader
            title="Regression Summary"
            sub="Aggregated rankings coverage and score distribution"
          />
          {dqState.status === "loading" && <LoadingBlock />}
          {dqState.status === "error" && <ErrorBlock message={dqState.message} />}
          {dq && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard
                label="Aggregated"
                value={dq.regression_summary.aggregated_count.toLocaleString()}
                sub="universities in latest view"
              />
              <StatCard
                label="Score Min"
                value={dq.regression_summary.score_min != null
                  ? dq.regression_summary.score_min.toFixed(2) : "—"}
                sub="composite score"
              />
              <StatCard
                label="Score Max"
                value={dq.regression_summary.score_max != null
                  ? dq.regression_summary.score_max.toFixed(2) : "—"}
                sub="composite score"
              />
              <StatCard
                label="Low Coverage"
                value={dq.regression_summary.low_coverage_count}
                sub="coverage_ratio < 0.5"
              />
            </div>
          )}
        </section>

        {/* ── Source Drift Warnings ── */}
        <section className="mb-8">
          <SectionHeader
            title="Source Drift Warnings"
            sub="Detected by comparing consecutive ingestion batches"
          />
          {dqState.status === "loading" && <LoadingBlock />}
          {dqState.status === "error" && <ErrorBlock message={dqState.message} />}
          {dq && dq.drift_warnings.length === 0 && (
            <p className="text-sm text-slate-500">No warnings detected.</p>
          )}
          {dq && dq.drift_warnings.length > 0 && (
            <table className="w-full border border-slate-200 bg-white text-sm">
              <thead className="bg-slate-50">
                <tr>
                  {["Source", "Type", "Message"].map((h) => (
                    <th
                      key={h}
                      className="border-b border-slate-200 px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-slate-500"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dq.drift_warnings.map((w, i) => (
                  <tr key={i} className="border-b border-slate-100 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs">{w.source_code}</td>
                    <td className="px-3 py-2">
                      <WarnChip type={w.warning_type} />
                    </td>
                    <td className="px-3 py-2 text-slate-600">{w.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {/* ── Unresolved Universities ── */}
        <section className="mb-8">
          <SectionHeader
            title="Unresolved Universities"
            sub="Source entities that could not be matched to a canonical university"
          />
          {dqState.status === "loading" && <LoadingBlock />}
          {dqState.status === "error" && <ErrorBlock message={dqState.message} />}
          {dq && (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <StatCard
                  label="Total Unresolved"
                  value={dq.unresolved.total.toLocaleString()}
                  sub="in missing_entity_log"
                />
                {dq.unresolved.by_source.map((s) => (
                  <StatCard
                    key={s.source_code}
                    label={s.source_code}
                    value={s.count.toLocaleString()}
                    sub="unresolved entities"
                  />
                ))}
              </div>
              {dq.unresolved.top_examples.length > 0 && (
                <table className="w-full border border-slate-200 bg-white text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      {["Source", "Raw Name", "Country Hint", "Year"].map((h) => (
                        <th
                          key={h}
                          className="border-b border-slate-200 px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-slate-500"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dq.unresolved.top_examples.map((ex, i) => (
                      <tr key={i} className="border-b border-slate-100 last:border-0">
                        <td className="px-3 py-2 font-mono text-xs">{ex.source_code}</td>
                        <td className="px-3 py-2">{ex.raw_name}</td>
                        <td className="px-3 py-2 text-slate-500">{ex.country_hint ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-500">{ex.ranking_year ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </section>

        {/* ── Low-Confidence Matches ── */}
        <section className="mb-8">
          <SectionHeader
            title="Low-Confidence Canonical Matches"
            sub={`Entity matches with confidence score below ${dq?.low_confidence_matches?.threshold ?? 0.80}`}
          />
          {dqState.status === "loading" && <LoadingBlock />}
          {dqState.status === "error" && <ErrorBlock message={dqState.message} />}
          {dq && (
            <>
              <p className="mb-3 text-sm text-slate-600">
                Total: <strong>{dq.low_confidence_matches.count}</strong> low-confidence
                match{dq.low_confidence_matches.count !== 1 ? "es" : ""} (threshold:{" "}
                {dq.low_confidence_matches.threshold})
              </p>
              {dq.low_confidence_matches.examples.length > 0 && (
                <table className="w-full border border-slate-200 bg-white text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      {["Source", "Confidence", "Method", "Canonical"].map((h) => (
                        <th
                          key={h}
                          className="border-b border-slate-200 px-3 py-2 text-left text-xs font-bold uppercase tracking-wider text-slate-500"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dq.low_confidence_matches.examples.map((m, i) => (
                      <tr key={i} className="border-b border-slate-100 last:border-0">
                        <td className="px-3 py-2 font-mono text-xs">{m.source_name}</td>
                        <td className="px-3 py-2">
                          <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-xs font-semibold text-amber-700">
                            {Number(m.confidence_score).toFixed(3)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-500">{m.match_method}</td>
                        <td className="px-3 py-2">
                          <span className="font-medium">{m.display_name}</span>
                          <span className="ml-1 text-xs text-slate-400">{m.canonical_slug}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {dq.low_confidence_matches.count === 0 && (
                <p className="text-sm text-slate-500">
                  No low-confidence matches found. All canonical mappings are above the threshold.
                </p>
              )}
            </>
          )}
        </section>

        {/* ── Duplicate Resolution ── */}
        <section className="mb-8">
          <SectionHeader
            title="Duplicate Resolution"
            sub="Saved by de-duplication during ingestion"
          />
          {dqState.status === "loading" && <LoadingBlock />}
          {dqState.status === "error" && <ErrorBlock message={dqState.message} />}
          {dq && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard
                label="Total Saves"
                value={dq.duplicates.total_duplicate_saves.toLocaleString()}
                sub="duplicate_resolution_saves"
              />
              {dq.duplicates.by_source.map((s) => (
                <StatCard
                  key={s.source_code}
                  label={s.source_code}
                  value={(s.duplicate_resolution_saves ?? 0).toLocaleString()}
                  sub="saves"
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
