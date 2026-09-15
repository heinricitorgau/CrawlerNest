import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { fetchJson } from "@/lib/api";
import { CaveatBanner } from "@/components/CaveatBanner";
import { YearSelector, YearSelectorFallback } from "@/components/YearSelector";
import { YEAR_QUERY_PARAM, hrefForEdition, resolveSelectedYear } from "@/lib/datasetScope";
import { formatDegreeLevel, formatRank, formatRankingScore } from "@/lib/format";
import { AdmissionRequirementBadges } from "@/components/AdmissionRequirementBadges";
import type {
  AdmissionRequirement,
  AdmissionRequirements,
  UniversityDetail,
  UniversityDetailResponse,
} from "@/types/university";
import type {
  SubjectRankingRow,
  SubjectRankingsApiResponse,
} from "@/types/subjectRanking";
import ShortlistButton from "@/components/ShortlistButton";
import { CAVEAT_RANK_CHANGE, editionCaveats } from "@/lib/caveatMessages";
import { SourceRankChange, anyEntityChanged, anyRankChangeShown } from "@/components/SourceRankChange";

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
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

/** The edition in `?year=`, resolved by the same rule as every other year-aware page. */
async function selectedEdition(searchParams: UniversityDetailPageProps["searchParams"]) {
  const raw = (await searchParams)?.[YEAR_QUERY_PARAM];
  return resolveSelectedYear(Array.isArray(raw) ? raw[0] : raw);
}

const SOURCE_PRIORITY = ["QS", "THE", "ARWU"] as const;

// ─── Helpers ───
function formatDate(value?: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString();
}

function sourcePriority(source: string): number {
  const index = SOURCE_PRIORITY.indexOf(source as (typeof SOURCE_PRIORITY)[number]);
  return index === -1 ? SOURCE_PRIORITY.length : index;
}

function buildRankingEvidenceSummary(evidence: UniversityDetail["sourceRankings"]) {
  const ranks = evidence
    .map((row) => row.rank)
    .filter((rank): rank is number => rank != null);

  if (ranks.length === 0) {
    return {
      availableSourceCount: 0,
      bestRank: null,
      worstRank: null,
      rankSpread: null,
      agreementLevel: "limited" as const,
      note: "No ranking evidence is available for this university yet.",
    };
  }

  if (ranks.length === 1) {
    return {
      availableSourceCount: 1,
      bestRank: ranks[0],
      worstRank: ranks[0],
      rankSpread: 0,
      agreementLevel: "limited" as const,
      note: "Only one source is available for this university.",
    };
  }

  const bestRank = Math.min(...ranks);
  const worstRank = Math.max(...ranks);
  const rankSpread = worstRank - bestRank;

  if (rankSpread <= 5) {
    return {
      availableSourceCount: ranks.length,
      bestRank,
      worstRank,
      rankSpread,
      agreementLevel: "strong" as const,
      note: "Multiple ranking sources broadly agree.",
    };
  }

  if (rankSpread <= 20) {
    return {
      availableSourceCount: ranks.length,
      bestRank,
      worstRank,
      rankSpread,
      agreementLevel: "moderate" as const,
      note: "Ranking sources show moderate variation.",
    };
  }

  return {
    availableSourceCount: ranks.length,
    bestRank,
    worstRank,
    rankSpread,
    agreementLevel: "weak" as const,
    note: "Large disagreement across sources — interpret carefully.",
  };
}

function AdmissionRequirementsBlock({ admissions }: { admissions?: AdmissionRequirements }) {
  // The API always sends this block, but a cached response from before it existed
  // would not, so treat a missing block the same as an empty one.
  if (!admissions || !admissions.hasData) {
    return (
      <div className="p-4">
        <p className="text-slate-400 italic text-sm">
          No admission requirements have been collected for this university yet.
        </p>
        <AdmissionCaveatList caveats={admissions?.caveats} />
      </div>
    );
  }

  const levels = admissions.byDegreeLevel.length > 0 ? admissions.byDegreeLevel : [admissions.summary];
  const programmes = admissions.programmeRequirements ?? [];

  return (
    <div className="space-y-6">
      {admissions.byDegreeLevel.length > 0 &&
        levels.map((level, index) => (
          <AdmissionLevelRow
            key={level.degreeLevel ?? `level-${index}`}
            level={level}
            showHeading={levels.length > 1}
          />
        ))}
      {programmes.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
            Programme-specific requirements
          </h3>
          <div className="space-y-4">
            {programmes.map((programme, index) => (
              <AdmissionLevelRow
                key={`${programme.degreeLevel}-${programme.faculty}-${programme.programmeName}-${programme.intakeYear}-${index}`}
                level={programme}
                showHeading
                heading={[programme.programmeName ?? programme.faculty, formatDegreeLevel(programme.degreeLevel)]
                  .filter(Boolean)
                  .join(" · ")}
              />
            ))}
          </div>
        </div>
      )}
      <AdmissionCaveatList caveats={admissions.caveats} />
    </div>
  );
}

/** The API renders these (with the fetch date); shown verbatim, never reworded here. */
function AdmissionCaveatList({ caveats }: { caveats?: string[] }) {
  if (!caveats || caveats.length === 0) {
    return null;
  }
  return (
    <ul className="mt-2 space-y-1" aria-label="Admission data caveats">
      {caveats.map((caveat) => (
        <li key={caveat} className="text-xs text-slate-500">
          · {caveat}
        </li>
      ))}
    </ul>
  );
}

function AdmissionLevelRow({
  level,
  showHeading,
  heading,
}: {
  level: AdmissionRequirement;
  showHeading: boolean;
  heading?: string;
}) {
  return (
    <div>
      {showHeading && (
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
          {heading ?? formatDegreeLevel(level.degreeLevel)}
        </h3>
      )}
      <AdmissionRequirementBadges
        requirements={level}
        emptyMessage="The source for this level did not publish any entry requirements."
      />
      {level.requirementScope === "unspecified" && (
        <p className="mt-2 text-xs text-slate-500">
          The source gives one figure without saying whether it applies to every programme.
        </p>
      )}
      {level.valuesDiffer && (
        <p className="mt-2 text-xs text-slate-500">
          Sources for this level disagree; the lowest published figure is shown.
        </p>
      )}
      {level.intakeYear != null && (
        <p className="mt-2 text-xs text-slate-500">
          For the {level.intakeYear} intake
          {level.intakeYearBasis === "deadline_inferred" ? " (inferred from the application deadline)" : ""}.
        </p>
      )}
      {level.sourceUrl && (
        <a
          href={level.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block mt-3 text-xs text-slate-500 underline hover:text-slate-700"
        >
          Source
        </a>
      )}
    </div>
  );
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

async function fetchUniversityDetail(slug: string, year?: number): Promise<UniversityDetailResponse> {
  const query = year != null ? `?year=${year}` : "";
  return fetchJson<UniversityDetailResponse>(`/api/v1/universities/by-slug/${encodeURIComponent(slug)}${query}`);
}

async function fetchUniversitySubjectRankings(canonicalUniversityId: number, year: number): Promise<SubjectRankingRow[]> {
  try {
    // Scoped to the edition: without a year this endpoint returns every year it
    // holds, which on a 2025 page would show 2026 subject ranks.
    const response = await fetchJson<SubjectRankingsApiResponse>(
      `/api/v1/universities/${canonicalUniversityId}/subject-rankings?year=${year}`
    );

    if (!response.success || !Array.isArray(response.data?.items)) {
      return [];
    }

    return response.data.items;
  } catch (error) {
    console.error("Subject ranking fetch failed", error);
    return [];
  }
}

function formatSubjectScore(score?: number | null) {
  if (typeof score !== "number" || !Number.isFinite(score)) {
    return "—";
  }

  return score.toFixed(1);
}

function SubjectRankingsBlock({ items, year }: { items: SubjectRankingRow[]; year: number }) {
  const strongSubjects = items.filter((item) => item.rankPosition != null && item.rankPosition <= 10);
  const midSubjects = items.filter(
    (item) => item.rankPosition != null && item.rankPosition > 10 && item.rankPosition <= 50
  );
  const weakSubjects = items.filter((item) => item.rankPosition == null || item.rankPosition > 50);

  if (items.length === 0) {
    // "Held" on purpose: subject tables are ingested for fewer editions than world
    // rankings, so an empty list is our coverage, not a statement about the university.
    return (
      <div className="rounded border border-slate-100 bg-slate-50 p-6 text-sm text-slate-500">
        No {year} subject rankings are held for this university.
      </div>
    );
  }

  const groups = [
    {
      title: "Strong subjects",
      description: "Top 10 subject positions.",
      items: strongSubjects,
      tone: "border-emerald-200 bg-emerald-50 text-emerald-900",
    },
    {
      title: "Mid subjects",
      description: "Ranks 11-50. Strong enough to support a subject-led shortlist.",
      items: midSubjects,
      tone: "border-amber-200 bg-amber-50 text-amber-900",
    },
    {
      title: "Weak / missing",
      description: "Ranks below 50 or records with no rank position.",
      items: weakSubjects,
      tone: "border-slate-200 bg-slate-50 text-slate-700",
    },
  ];

  return (
    <div className="grid gap-4">
      {groups.map((group) => (
        <div key={group.title} className={`rounded border p-4 ${group.tone}`}>
          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="text-sm font-bold">{group.title}</div>
              <div className="mt-1 text-xs opacity-80">{group.description}</div>
            </div>
            <div className="text-xs font-bold uppercase tracking-[0.12em]">
              {group.items.length} subject{group.items.length === 1 ? "" : "s"}
            </div>
          </div>

          {group.items.length > 0 ? (
            <div className="mt-3 grid gap-2">
              {group.items.map((item) => (
                <div
                  key={`${group.title}-${item.subjectKey}-${item.rankingYear}-${item.sourceCode}`}
                  className="grid gap-2 rounded bg-white/80 p-3 text-sm text-slate-800 sm:grid-cols-[1fr_auto_auto_auto]"
                >
                  <div>
                    <div className="font-semibold">{item.subjectName}</div>
                    <div className="mt-1 text-xs text-slate-500">{item.rankingYear}</div>
                  </div>
                  <div className="font-mono">
                    {item.rankDisplay || formatRank(item.rankPosition)}
                  </div>
                  <div className="font-mono">{formatSubjectScore(item.score)}</div>
                  <div className="font-semibold">{item.sourceCode}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 rounded bg-white/70 p-3 text-sm opacity-80">
              No subjects in this band.
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default async function UniversityDetailPage({ params, searchParams }: UniversityDetailPageProps) {
  const { slug } = await params;
  const { year } = await selectedEdition(searchParams);
  const editionHref = (href: string) => hrefForEdition(href, year);
  let detail: UniversityDetail | null = null;
  let timestamp: string | undefined;

  try {
    const response = await fetchUniversityDetail(slug, year);
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
          <Link href={editionHref("/")} className="inline-block px-6 py-2 bg-blue-600 text-white font-bold rounded hover:bg-blue-700 transition-colors">
            Back to Rankings
          </Link>
        </div>
      </div>
    );
  }

  const primaryRank = detail.aggregatedRanking?.displayRank;
  const rankingEvidence = (detail.rankingEvidence ?? detail.sourceRankings ?? []).slice().sort((left, right) => {
    return sourcePriority(left.source) - sourcePriority(right.source);
  });
  const evidenceSummary = buildRankingEvidenceSummary(rankingEvidence);
  const agreementTone =
    evidenceSummary.agreementLevel === "strong"
      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
      : evidenceSummary.agreementLevel === "moderate"
        ? "bg-amber-50 text-amber-800 border-amber-200"
        : "bg-rose-50 text-rose-800 border-rose-200";
  const subjectRankings = await fetchUniversitySubjectRankings(detail.canonicalUniversityId, year);
  // The edition the API read; the requested one if an older API does not say.
  const edition = detail.rankingYear ?? year;
  const rankedInEdition = detail.aggregatedRanking != null;

  return (
    <main className="min-h-screen bg-slate-50 pb-20">
      {/* ── 1. Breadcrumb/Actions ── */}
      <div className="bg-white border-b border-slate-200">
        <div className="mx-auto max-w-7xl px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-widest">
            <Link href={editionHref("/")} className="hover:text-blue-600">Rankings</Link>
            <span>/</span>
            <span className="text-slate-900">{detail.universityName}</span>
          </div>
          <Suspense fallback={<YearSelectorFallback variant="nav" />}>
            <YearSelector variant="nav" />
          </Suspense>
          <ShortlistButton
            item={{
              canonicalUniversityId: detail.canonicalUniversityId,
              universityName: detail.universityName,
              country: detail.country,
              aggregatedRank: detail.aggregatedRanking?.displayRank ?? 9999,
              slug: detail.slug,
            }}
          />
          <Link
            href={`/universities/${slug}/sources`}
            className="rounded border border-slate-200 px-3 py-2 text-xs font-bold uppercase tracking-[0.12em] text-slate-700 hover:border-blue-300 hover:text-blue-700"
          >
            Sources
          </Link>
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
              <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-700">{edition} edition</span>
            </div>
          </div>

          <div className="flex-shrink-0 bg-slate-900 text-white rounded-lg p-6 shadow-xl relative overflow-hidden min-w-[200px]">
            <div className="absolute top-0 right-0 w-24 h-24 bg-blue-600/10 -mr-8 -mt-8 rounded-full blur-2xl" />
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400 mb-2">Aggregated Rank · {edition}</p>
            {rankedInEdition ? (
              <p className="text-5xl font-black tabular-nums">
                #{primaryRank ? formatRank(primaryRank) : "N/A"}
              </p>
            ) : (
              <p className="max-w-[16rem] text-sm font-semibold leading-snug text-slate-200">
                Not in the {edition} edition held here.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ── 3. Profile Content ── */}
      <div className="mx-auto max-w-7xl px-6 lg:px-8 mt-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          
          {/* Main Column */}
          <div className="lg:col-span-2">
            <Section title="Ranking Evidence (QS / THE / ARWU)">
              <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">
                      Ranking Evidence Summary
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-2 text-sm text-slate-700 sm:grid-cols-5">
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Sources available
                        </div>
                        <div className="mt-1 font-semibold text-slate-900">
                          {evidenceSummary.availableSourceCount}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Best rank
                        </div>
                        <div className="mt-1 font-semibold text-slate-900">
                          {evidenceSummary.bestRank != null ? `#${formatRank(evidenceSummary.bestRank)}` : "—"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Worst rank
                        </div>
                        <div className="mt-1 font-semibold text-slate-900">
                          {evidenceSummary.worstRank != null ? `#${formatRank(evidenceSummary.worstRank)}` : "—"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Rank spread
                        </div>
                        <div className="mt-1 font-semibold text-slate-900">
                          {evidenceSummary.rankSpread != null ? formatRank(evidenceSummary.rankSpread) : "—"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Agreement
                        </div>
                        <div className="mt-1 font-semibold capitalize text-slate-900">
                          {evidenceSummary.agreementLevel}
                          {evidenceSummary.agreementLevel === "limited" ? " evidence" : ""}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div
                    className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-[0.14em] ${agreementTone}`}
                  >
                    {evidenceSummary.agreementLevel}
                  </div>
                </div>
                <p className="mt-3 text-sm text-slate-600">{evidenceSummary.note}</p>
              </div>

              <div className="overflow-hidden rounded border border-slate-100">
                <table className="ranking-table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th className="text-center">Rank</th>
                      <th className="text-center">Overall Score</th>
                      <th className="text-center">Year</th>
                      <th className="text-center">Change in this source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rankingEvidence.length > 0 ? rankingEvidence.map((r) => (
                      <tr key={`${r.source}-${r.year ?? "unknown"}`}>
                        <td className="font-bold text-slate-900">{r.source}</td>
                        <td className="text-center font-mono">{r.rankDisplay || formatRank(r.rank)}</td>
                        <td className="text-center font-mono">{formatRankingScore(r.score)}</td>
                        <td className="text-center text-slate-500">{r.year ?? "—"}</td>
                        <td className="text-center">
                          <SourceRankChange ranking={r} />
                        </td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan={5} className="text-center py-10 text-slate-400 italic">
                          {rankedInEdition
                            ? "No source evidence found."
                            : `No ${edition} ranking row is held for this university.`}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <CaveatBanner
                className="mt-3"
                caveats={[
                  ...editionCaveats(edition),
                  anyRankChangeShown(rankingEvidence) || anyEntityChanged(rankingEvidence) ? CAVEAT_RANK_CHANGE : null,
                ]}
              />
            </Section>

            <Section title="Subject Rankings">
              <SubjectRankingsBlock items={subjectRankings} year={edition} />
            </Section>

            <Section title="Admission Requirements">
              <AdmissionRequirementsBlock admissions={detail.admissionRequirements} />
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
                 href={editionHref("/recommendations")}
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
