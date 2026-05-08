import type { Metadata } from "next";
import Link from "next/link";

import { fetchJson } from "@/lib/api";
import { formatRank, formatRankingScore } from "@/lib/format";
import type { UniversityDetailResponse } from "@/types/university";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type PageProps = {
  params: Promise<{ slug: string }>;
};

type ApiResponse<T> = {
  success: boolean;
  data: T;
  metadata?: { timestamp?: string };
};

type SourceRow = {
  source_code: string;
  rank: number | null;
  score: number | null;
  normalized_score: number | null;
  weight: number | null;
  weighted_input: number | null;
};

type ContributionRow = {
  source_code: string;
  normalized_score: number | null;
  weight: number | null;
  weighted_input: number | null;
  contribution_share: number | null;
};

type SourceComparison = {
  canonical_university_id: number;
  university_name?: string;
  ranking_year?: number;
  aggregated_rank?: number | null;
  composite_score?: number | null;
  coverage_ratio?: number | null;
  sources: SourceRow[];
  missing_sources: string[];
  rank_spread: number | null;
  confidence: "high" | "medium" | "low" | string;
  confidence_reasoning: string;
  source_disagreement_metrics: {
    available_source_count: number;
    rank_spread: number | null;
    average_pairwise_rank_difference: number | null;
    max_pairwise_rank_difference: number | null;
    qs_the_rank_difference: number | null;
  };
  aggregation_contribution: ContributionRow[];
};

type RankingExplain = {
  why_this_rank_exists: string;
  weighted_aggregation_inputs: Array<{
    source_code: string;
    rank: number | null;
    normalization: string | null;
    normalized_score: number | null;
    weight: number | null;
    included: boolean;
  }>;
  missing_source_penalties: Array<{
    source_code: string;
    penalty_type: string;
    reason: string;
  }>;
  formula_note: string;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  return { title: `${slug} source intelligence | CrawlerNest` };
}

async function fetchUniversity(slug: string) {
  return fetchJson<UniversityDetailResponse>(
    `/api/v1/universities/by-slug/${encodeURIComponent(slug)}`
  );
}

async function fetchComparison(id: number) {
  return fetchJson<ApiResponse<SourceComparison>>(
    `/api/v1/universities/${id}/source-comparison`
  );
}

async function fetchExplain(id: number) {
  return fetchJson<ApiResponse<RankingExplain>>(`/api/v1/rankings/${id}/explain`);
}

function ConfidenceBadge({ value }: { value: string }) {
  const cls =
    value === "high"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : value === "medium"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-rose-200 bg-rose-50 text-rose-800";

  return (
    <span className={`rounded border px-2 py-1 text-xs font-bold uppercase tracking-[0.12em] ${cls}`}>
      {value}
    </span>
  );
}

function fmtNumber(value: number | null | undefined, digits = 3) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return value.toFixed(digits);
}

function fmtPct(value: number | null | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return `${Math.round(value * 100)}%`;
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-black tracking-tight text-slate-950">{value}</div>
    </div>
  );
}

export default async function UniversitySourcesPage({ params }: PageProps) {
  const { slug } = await params;
  const universityResponse = await fetchUniversity(slug);
  const university = universityResponse.data;

  if (!university) {
    return (
      <main className="min-h-screen bg-slate-50 px-6 py-12">
        <div className="mx-auto max-w-3xl border border-slate-200 bg-white p-8">
          <h1 className="text-2xl font-black text-slate-950">University not found</h1>
          <Link className="mt-4 inline-block text-sm font-semibold text-blue-700" href="/rankings">
            Back to rankings
          </Link>
        </div>
      </main>
    );
  }

  const [comparisonResponse, explainResponse] = await Promise.all([
    fetchComparison(university.canonicalUniversityId),
    fetchExplain(university.canonicalUniversityId),
  ]);
  const comparison = comparisonResponse.data;
  const explain = explainResponse.data;
  const maxRank = Math.max(
    1,
    ...comparison.sources.map((source) => source.rank ?? 0)
  );

  return (
    <main className="min-h-screen bg-slate-50 pb-16">
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-5">
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            <Link href="/rankings" className="hover:text-blue-700">Rankings</Link>
            <span>/</span>
            <Link href={`/universities/${slug}`} className="hover:text-blue-700">
              {university.universityName}
            </Link>
            <span>/</span>
            <span className="text-slate-900">Sources</span>
          </div>
          <div className="mt-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="text-3xl font-black tracking-tight text-slate-950">
                {university.universityName}
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                Cross-source comparison, disagreement, and aggregation explainability.
              </p>
            </div>
            <ConfidenceBadge value={comparison.confidence} />
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 py-8">
        <section className="mb-8 grid gap-3 sm:grid-cols-4">
          <Metric
            label="Aggregated Rank"
            value={comparison.aggregated_rank ? `#${formatRank(comparison.aggregated_rank)}` : "-"}
          />
          <Metric label="Rank Spread" value={comparison.rank_spread ?? "-"} />
          <Metric label="Coverage" value={fmtPct(comparison.coverage_ratio)} />
          <Metric label="Sources" value={comparison.sources.length} />
        </section>

        <section className="mb-8 border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 bg-slate-50 px-5 py-4">
            <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-700">
              Source Comparison
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-white text-xs uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  {["Source", "Rank", "Source score", "Normalized", "Weight", "Weighted input"].map((head) => (
                    <th key={head} className="border-b border-slate-200 px-4 py-3 text-left font-bold">
                      {head}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison.sources.map((source) => (
                  <tr key={source.source_code} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3 font-bold text-slate-900">{source.source_code}</td>
                    <td className="px-4 py-3 font-mono">#{source.rank ? formatRank(source.rank) : "-"}</td>
                    <td className="px-4 py-3 font-mono">{formatRankingScore(source.score)}</td>
                    <td className="px-4 py-3 font-mono">{fmtNumber(source.normalized_score, 6)}</td>
                    <td className="px-4 py-3 font-mono">{fmtNumber(source.weight, 2)}</td>
                    <td className="px-4 py-3 font-mono">{fmtNumber(source.weighted_input, 6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {comparison.missing_sources.length > 0 && (
            <div className="border-t border-slate-100 px-5 py-4 text-sm text-slate-600">
              Missing sources:{" "}
              <span className="font-semibold text-slate-900">
                {comparison.missing_sources.join(", ")}
              </span>
            </div>
          )}
        </section>

        <section className="mb-8 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-700">
              Disagreement
            </h2>
            <div className="mt-5 space-y-4">
              {comparison.sources.map((source) => {
                const width = source.rank ? Math.max(4, (source.rank / maxRank) * 100) : 0;
                return (
                  <div key={`viz-${source.source_code}`}>
                    <div className="mb-1 flex items-center justify-between text-xs font-semibold text-slate-600">
                      <span>{source.source_code}</span>
                      <span>#{source.rank ? formatRank(source.rank) : "-"}</span>
                    </div>
                    <div className="h-3 bg-slate-100">
                      <div className="h-3 bg-blue-600" style={{ width: `${width}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
              <div className="border border-slate-100 bg-slate-50 p-3">
                <div className="text-xs font-bold uppercase text-slate-500">Avg pairwise diff</div>
                <div className="mt-1 font-mono text-slate-950">
                  {fmtNumber(comparison.source_disagreement_metrics.average_pairwise_rank_difference, 2)}
                </div>
              </div>
              <div className="border border-slate-100 bg-slate-50 p-3">
                <div className="text-xs font-bold uppercase text-slate-500">QS/THE diff</div>
                <div className="mt-1 font-mono text-slate-950">
                  {comparison.source_disagreement_metrics.qs_the_rank_difference ?? "-"}
                </div>
              </div>
            </div>
          </div>

          <div className="border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-700">
              Confidence
            </h2>
            <div className="mt-4">
              <ConfidenceBadge value={comparison.confidence} />
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">
              {comparison.confidence_reasoning}
            </p>
            <div className="mt-5 text-sm text-slate-600">
              Composite score:{" "}
              <span className="font-mono text-slate-950">
                {fmtNumber(comparison.composite_score, 6)}
              </span>
            </div>
          </div>
        </section>

        <section className="border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-700">
            Aggregation Explanation
          </h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">{explain.why_this_rank_exists}</p>
          <div className="mt-5 grid gap-3">
            {comparison.aggregation_contribution.map((row) => (
              <div
                key={`contrib-${row.source_code}`}
                className="grid gap-2 border border-slate-100 bg-slate-50 p-3 text-sm sm:grid-cols-[80px_1fr_1fr_1fr]"
              >
                <div className="font-bold text-slate-900">{row.source_code}</div>
                <div>Normalized {fmtNumber(row.normalized_score, 6)}</div>
                <div>Weight {fmtNumber(row.weight, 2)}</div>
                <div>Share {fmtPct(row.contribution_share)}</div>
              </div>
            ))}
          </div>
          {explain.missing_source_penalties.length > 0 && (
            <div className="mt-5 border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              {explain.missing_source_penalties.map((penalty) => (
                <div key={penalty.source_code}>
                  {penalty.source_code}: {penalty.reason}
                </div>
              ))}
            </div>
          )}
          <p className="mt-4 text-xs text-slate-400">{explain.formula_note}</p>
        </section>
      </div>
    </main>
  );
}
