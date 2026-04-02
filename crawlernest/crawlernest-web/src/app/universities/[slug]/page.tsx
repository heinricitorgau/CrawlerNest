import type { Metadata } from "next";
import Link from "next/link";
import { fetchJson } from "@/lib/api";
import { formatRank, formatRankingScore } from "@/lib/format";
import type {
  UniversityDetail,
  UniversityDetailResponse,
} from "@/types/university";
import ShortlistButton from "@/components/ShortlistButton";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function generateMetadata({ params }: UniversityDetailPageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const response = await fetchUniversityDetail(slug);
    if (response.success && response.data) {
      return { title: `${response.data.universityName} | CrawlerNest` };
    }
  } catch {
    // fall through to default
  }
  return { title: "University | CrawlerNest" };
}

type UniversityDetailPageProps = {
  params: Promise<{
    slug: string;
  }>;
};

// ─── Helpers ───
function formatDate(value?: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm mb-8">
      <div className="px-6 py-4 border-b border-slate-100 bg-slate-50">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-600">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </section>
  );
}

async function fetchUniversityDetail(slug: string): Promise<UniversityDetailResponse> {
  // Real implement would use fetchJson from lib/api
  return fetchJson<UniversityDetailResponse>(`/api/v1/universities/by-slug/${encodeURIComponent(slug)}`);
}

export default async function UniversityDetailPage({ params }: UniversityDetailPageProps) {
  const { slug } = await params;
  let detail: UniversityDetail | null = null;
  let timestamp: string | undefined;

  try {
    const response = await fetchUniversityDetail(slug);
    if (response.success) {
      detail = response.data;
      timestamp = response.metadata?.timestamp;
    }
  } catch (err) {
    console.error("Detail fetch failed", err);
  }

  if (!detail) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center max-w-md p-8 bg-white border border-slate-200 rounded-lg shadow-lg">
          <h1 className="text-2xl font-bold text-slate-900 mb-4">University Not Found</h1>
          <p className="text-slate-600 mb-6">The university with slug "{slug}" could not be located in our database.</p>
          <Link href="/" className="inline-block px-6 py-2 bg-blue-600 text-white font-bold rounded hover:bg-blue-700 transition-colors">
            Back to Rankings
          </Link>
        </div>
      </div>
    );
  }

  const primaryRank = detail.aggregatedRanking?.displayRank;

  return (
    <main className="min-h-screen bg-slate-50 pb-20">
      {/* ── 1. Breadcrumb/Actions ── */}
      <div className="bg-white border-b border-slate-200">
        <div className="mx-auto max-w-7xl px-6 lg:px-8 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-widest">
            <Link href="/" className="hover:text-blue-600">Rankings</Link>
            <span>/</span>
            <span className="text-slate-900">{detail.universityName}</span>
          </div>
          <ShortlistButton
            item={{
              canonicalUniversityId: detail.canonicalUniversityId,
              universityName: detail.universityName,
              country: detail.country,
              aggregatedRank: detail.aggregatedRanking?.displayRank ?? 9999,
              slug: detail.slug,
            }}
          />
        </div>
      </div>

      {/* ── 2. Profile Header ── */}
      <div className="bg-white border-b border-slate-200 py-12">
        <div className="mx-auto max-w-7xl px-6 lg:px-8 flex flex-col md:flex-row md:items-end justify-between gap-8">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-2 py-1 bg-slate-100 rounded text-xs font-bold text-slate-600 mb-4">
              <span>📍 {detail.country}</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-black tracking-tight text-slate-900 antialiased">
              {detail.universityName}
            </h1>
            <div className="mt-6 flex items-center gap-6 text-sm text-slate-500 font-medium">
              <span className="flex items-center gap-1.5">
                <span className="text-green-500">✓</span> Data Verified
              </span>
              <span>Updated: {formatDate(timestamp) || "Recently"}</span>
            </div>
          </div>

          <div className="flex-shrink-0 bg-slate-900 text-white rounded-lg p-6 shadow-xl relative overflow-hidden min-w-[200px]">
            <div className="absolute top-0 right-0 w-24 h-24 bg-blue-600/10 -mr-8 -mt-8 rounded-full blur-2xl" />
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400 mb-2">Aggregated Rank</p>
            <p className="text-5xl font-black tabular-nums">
              #{primaryRank ? formatRank(primaryRank) : "N/A"}
            </p>
          </div>
        </div>
      </div>

      {/* ── 3. Profile Content ── */}
      <div className="mx-auto max-w-7xl px-6 lg:px-8 mt-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          
          {/* Main Column */}
          <div className="lg:col-span-2">
            <Section title="Ranking Evidence (QS vs THE)">
              <div className="overflow-hidden rounded border border-slate-100">
                <table className="ranking-table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th className="text-center">Rank</th>
                      <th className="text-center">Overall Score</th>
                      <th className="text-center">Year</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.sourceRankings ?? []).length > 0 ? (detail.sourceRankings ?? []).map((r, i) => (
                      <tr key={i}>
                        <td className="font-bold text-slate-900">{r.source}</td>
                        <td className="text-center font-mono">{formatRank(r.rank)}</td>
                        <td className="text-center font-mono">{formatRankingScore(r.score)}</td>
                        <td className="text-center text-slate-500">{r.year}</td>
                      </tr>
                    )) : (
                      <tr><td colSpan={4} className="text-center py-10 text-slate-400 italic">No source evidence found.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Section>

            <Section title="Admission Requirements">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {Object.entries(detail.admissionRequirements || {}).map(([key, val]) => (
                  <div key={key} className="p-4 bg-slate-50 rounded border border-slate-100">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">{key}</p>
                    <p className="text-sm font-semibold text-slate-800">{String(val) || "N/A"}</p>
                  </div>
                ))}
                {Object.keys(detail.admissionRequirements || {}).length === 0 && (
                  <p className="p-4 text-slate-400 italic text-sm">No structured requirements found.</p>
                )}
              </div>
            </Section>
          </div>

          {/* Sidebar Column */}
          <div className="space-y-8">
            <Section title="Decision Score">
              <div className="text-center py-6">
                <div className="relative inline-flex items-center justify-center">
                  <svg className="w-32 h-32 transform -rotate-90">
                    <circle className="text-slate-100" strokeWidth="8" stroke="currentColor" fill="transparent" r="58" cx="64" cy="64" />
                    <circle className="text-blue-600" strokeWidth="8" strokeDasharray={364} strokeDashoffset={364 - (364 * (detail.aggregatedRanking?.compositeScore || 0)) / 100} strokeLinecap="round" stroke="currentColor" fill="transparent" r="58" cx="64" cy="64" />
                  </svg>
                  <span className="absolute text-3xl font-black text-slate-900">
                    {detail.aggregatedRanking?.compositeScore ? Math.round(detail.aggregatedRanking.compositeScore) : "—"}
                  </span>
                </div>
                <p className="mt-4 text-xs font-bold text-slate-500 uppercase tracking-widest leading-loose">
                  Composite Intelligence Score<br/>
                  <span className="text-[10px] font-normal text-slate-400 font-sans">v{detail.aggregatedRanking?.aggregationMethodVersion || "1.0"} Normalized</span>
                </p>
              </div>
            </Section>

            <Section title="Data Completeness">
               <div className="space-y-4">
                 <div>
                    <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase mb-1">
                      <span>Recommendation Confidence</span>
                      <span>{Math.round((detail.dataQuality?.recommendationConfidence || 0) * 100)}%</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                      <div className="bg-green-500 h-full rounded-full transition-all duration-1000" style={{ width: `${(detail.dataQuality?.recommendationConfidence || 0) * 100}%` }} />
                    </div>
                 </div>
                 <div className="p-3 bg-slate-50 rounded border border-slate-100">
                    <p className="text-[10px] font-bold text-slate-500 uppercase mb-1">Status</p>
                    <p className="text-xs font-semibold text-slate-700">{detail.dataQuality?.confidenceLabel || "Unknown"}</p>
                    <p className="mt-2 text-[10px] text-slate-400 leading-relaxed italic">{detail.dataQuality?.confidenceReason || "No specific quality notes."}</p>
                 </div>
               </div>
            </Section>

            <div className="p-6 bg-blue-600 rounded-lg text-white shadow-lg">
               <h3 className="text-lg font-bold mb-2">Ready to apply?</h3>
               <p className="text-sm text-blue-100 mb-6 leading-relaxed">Our recommendation engine can check your profile against this university's criteria.</p>
               <Link
                 href="/recommendations"
                 className="block w-full py-3 bg-white text-blue-600 font-bold text-sm rounded shadow-sm hover:bg-blue-50 transition-colors text-center"
               >
                 Check Admission Odds
               </Link>
            </div>

          </div>
        </div>
      </div>
    </main>
  );
}
