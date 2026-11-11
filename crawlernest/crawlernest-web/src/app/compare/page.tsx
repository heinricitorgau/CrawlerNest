"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";

import { CaveatBanner } from "@/components/CaveatBanner";
import { CompareRankHistory } from "@/components/CompareRankHistory";
import { useHydrated } from "@/hooks/useHydrated";
import { useShortlist } from "@/lib/shortlistStore";
import { SourceRankChange, anyEntityChanged, anyRankChangeShown } from "@/components/SourceRankChange";
import { YearSelector, YearSelectorFallback } from "@/components/YearSelector";
import { useSelectedYear } from "@/hooks/useSelectedYear";
import { CAVEAT_RANK_CHANGE, editionCaveats } from "@/lib/caveatMessages";
import { DEFAULT_RANKING_YEAR, hrefForEdition } from "@/lib/datasetScope";
import { formatIelts, formatRank, formatScore } from "@/lib/format";
import type {
  CompareResponse,
  CompareUniversityPayload,
  ShortlistItem,
} from "@/types/compare";
import type { UniversityRanking } from "@/types/university";

const MAX_COMPARE_ITEMS = 4;
const COMPARE_SOURCES = ["QS", "THE", "ARWU"] as const;

/**
 * The rank as the source printed it ("=98", "601–610"). `sourceRanks` holds only a
 * band's lower bound, so it is the fallback for an API that sends no evidence.
 */
function printedSourceRank(evidence: UniversityRanking | undefined, position: number | undefined): string {
  if (evidence?.rankDisplay) return evidence.rankDisplay;
  if (evidence?.rank != null) return `#${formatRank(evidence.rank)}`;
  return position != null ? `#${formatRank(position)}` : "—";
}

function ComparePageShell() {
  return (
    <main className="min-h-screen bg-(--color-paper) px-6 py-10 text-(--color-ink) lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="h-5 w-40 animate-pulse rounded bg-(--color-paper-2)" />
        <div className="mt-4 h-10 w-80 animate-pulse rounded bg-(--color-paper-3)" />
        <div className="mt-4 h-4 w-[32rem] animate-pulse rounded bg-(--color-paper-2)" />
        <div className="mt-8 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="rounded-3xl border border-(--color-rule) bg-white p-6 shadow-sm">
              <div className="h-5 w-36 animate-pulse rounded bg-(--color-paper-2)" />
              <div className="mt-4 h-4 w-24 animate-pulse rounded bg-(--color-paper-2)" />
              <div className="mt-6 space-y-3">
                {Array.from({ length: 6 }).map((__, rowIndex) => (
                  <div key={rowIndex} className="h-4 animate-pulse rounded bg-(--color-paper-2)" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

function trustTone(level: CompareUniversityPayload["trustLevel"]) {
  if (level === "high") return "bg-(--color-paper-2) text-(--color-ink)";
  if (level === "medium") return "bg-(--color-paper-2) text-(--color-warn)";
  return "bg-(--color-paper-2) text-(--color-error)";
}

function agreementTone(level: CompareUniversityPayload["evidenceSummary"]["agreementLevel"]) {
  if (level === "strong") return "bg-(--color-paper-2) text-(--color-ink)";
  if (level === "moderate") return "bg-(--color-paper-2) text-(--color-warn)";
  return "bg-(--color-paper-2) text-(--color-error)";
}

/**
 * Reads the edition from the URL. The page body takes it as a prop, so it can be
 * rendered (and tested) without a router.
 */
export default function ComparePage() {
  return (
    <Suspense fallback={<ComparePageShell />}>
      <ComparePageWithSelectedYear />
    </Suspense>
  );
}

function ComparePageWithSelectedYear() {
  const { year } = useSelectedYear();
  return <ComparePageContent rankingYear={year} yearSelector={<YearSelector variant="page" />} />;
}

type ComparePageContentProps = {
  /** A held edition; the wrapper resolves it from `?year=`. */
  rankingYear?: number;
  yearSelector?: ReactNode;
};

export function ComparePageContent({
  rankingYear = DEFAULT_RANKING_YEAR,
  yearSelector = <YearSelectorFallback variant="page" />,
}: ComparePageContentProps) {
  // Shortlist and selection come from localStorage, so nothing reads them until hydration is over.
  const isClientReady = useHydrated();
  const [shortlist] = useShortlist();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [comparison, setComparison] = useState<CompareResponse["data"] | null>(null);
  // The edition the displayed comparison came from. While a refetch for another
  // edition is in flight the old cards stay up, and their caveats must describe them.
  const [comparisonYear, setComparisonYear] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isClientReady) {
      return;
    }

    setSelectedIds((previous) => {
      const availableIds = new Set(shortlist.map((item) => item.canonicalUniversityId));
      const pruned = previous.filter((id) => availableIds.has(id)).slice(0, MAX_COMPARE_ITEMS);

      if (pruned.length >= 2) {
        return pruned;
      }

      const fallback = shortlist
        .slice(0, Math.min(MAX_COMPARE_ITEMS, shortlist.length))
        .map((item) => item.canonicalUniversityId);

      return fallback;
    });
  }, [isClientReady, shortlist]);

  useEffect(() => {
    if (!isClientReady || selectedIds.length < 2) {
      setComparison(null);
      setComparisonYear(null);
      return;
    }

    let cancelled = false;

    async function fetchComparison() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch("/api/compare", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            universityIds: selectedIds,
            rankingYear,
          }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = (await response.json()) as CompareResponse;
        if (!cancelled) {
          setComparison(payload.data ?? null);
          setComparisonYear(payload.data ? rankingYear : null);
        }
      } catch {
        if (!cancelled) {
          setComparison(null);
          setComparisonYear(null);
          setError(`Unable to load the ${rankingYear} comparison right now. Please try again.`);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchComparison();

    return () => {
      cancelled = true;
    };
  }, [isClientReady, selectedIds, rankingYear]);

  const selectedCount = selectedIds.length;
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  // In selection order, so each university keeps one colour and shape in every rank-history chart.
  const selectedUniversities = useMemo(
    () =>
      selectedIds.flatMap((id) => {
        const item = shortlist.find((entry) => entry.canonicalUniversityId === id);
        return item ? [{ canonicalUniversityId: id, universityName: item.universityName }] : [];
      }),
    [selectedIds, shortlist]
  );

  const comparedUniversities = useMemo(() => {
    if (!comparison?.comparison?.universities) {
      return [];
    }

    const universities = comparison.comparison.universities;
    const orderedNames =
      comparison.order?.length && comparison.order.length > 0
        ? comparison.order
        : Object.keys(universities);

    return orderedNames
      .map((name) => universities[name])
      .filter(Boolean)
      .map((university) => {
        const shortlistItem = shortlist.find(
          (item) => item.canonicalUniversityId === university.canonicalUniversityId
        );
        return {
          ...university,
          slug: shortlistItem?.slug ?? "",
        };
      });
  }, [comparison, shortlist]);

  const bestAggregatedRank = useMemo(() => {
    const available = comparedUniversities
      .map((university) => university.aggregatedRank)
      .filter((rank): rank is number => rank != null);
    return available.length > 0 ? Math.min(...available) : null;
  }, [comparedUniversities]);

  const highestTrustScore = useMemo(() => {
    const available = comparedUniversities
      .map((university) => university.trustScore)
      .filter((score): score is number => score != null);
    return available.length > 0 ? Math.max(...available) : null;
  }, [comparedUniversities]);

  const toggleComparedUniversity = (item: ShortlistItem) => {
    setSelectedIds((previous) => {
      if (previous.includes(item.canonicalUniversityId)) {
        return previous.filter((id) => id !== item.canonicalUniversityId);
      }
      if (previous.length >= MAX_COMPARE_ITEMS) {
        return previous;
      }
      return [...previous, item.canonicalUniversityId];
    });
  };

  if (!isClientReady) {
    return <ComparePageShell />;
  }

  return (
    <main className="min-h-screen bg-(--color-paper) pb-20 text-(--color-ink)">
      <section
        className="band-ink relative overflow-hidden py-14"
      >
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <p className="band-ink__note text-sm font-medium">
            CrawlerNest
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            Compare Universities
          </h1>
          <p className="band-ink__note mt-4 max-w-3xl text-lg leading-7">
            Compare shortlisted universities side by side using aggregated position,
            source evidence, trust signals, and admissions context. This is an
            evidence-based comparison, not an official ranking.
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
        {shortlist.length === 0 ? (
          <section className="rounded-3xl border border-(--color-rule) bg-white p-8 shadow-sm">
            <h2 className="text-2xl font-semibold text-(--color-ink)">No shortlist yet</h2>
            <p className="mt-3 text-sm leading-6 text-(--color-muted)">
              Add universities to your shortlist first, then come back here to compare
              them side by side.
            </p>
            <Link
              href="/"
              className="mt-6 inline-flex bg-(--color-ink) px-5 py-3 text-sm font-semibold text-white transition hover:bg-(--color-ink-2)"
            >
              Browse rankings
            </Link>
          </section>
        ) : (
          <>
            <section className="rounded-3xl border border-(--color-rule) bg-white p-6 shadow-sm">
              <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-(--color-ink)">
                    Selected universities
                  </h2>
                  <p className="mt-2 text-sm text-(--color-muted)">
                    Choose 2 to 4 shortlisted universities to compare. Remove any item
                    here without affecting your shortlist.
                  </p>
                </div>
                <div className="flex flex-col gap-3 md:items-end">
                  {yearSelector}
                  <div className="text-sm text-(--color-muted)">
                    {selectedCount} selected / {MAX_COMPARE_ITEMS} max
                  </div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                {shortlist.map((item) => {
                  const selected = selectedSet.has(item.canonicalUniversityId);
                  const disabled = !selected && selectedCount >= MAX_COMPARE_ITEMS;
                  return (
                    <button
                      key={`${item.canonicalUniversityId}-${item.slug}`}
                      type="button"
                      disabled={disabled}
                      onClick={() => toggleComparedUniversity(item)}
                      className={` border px-4 py-2 text-sm font-medium transition ${
                        selected
                          ? "border-(--color-ink) bg-(--color-paper-2) text-(--color-ink)"
                          : disabled
                            ? "cursor-not-allowed border-(--color-rule) bg-(--color-paper) text-(--color-muted)"
                            : "border-(--color-rule) bg-white text-(--color-ink) hover:border-(--color-ink)"
                      }`}
                    >
                      {selected ? "✓ " : ""}{item.universityName}
                    </button>
                  );
                })}
              </div>

              {selectedCount < 2 ? (
                <div className="mt-6 rounded-2xl border border-(--color-warn-soft) bg-(--color-paper-2) px-4 py-3 text-sm text-(--color-warn)">
                  Select at least 2 universities to compare.
                </div>
              ) : null}
            </section>

            {selectedCount >= 2 ? (
              <>
                {error ? (
                  <div className="mt-6 rounded-2xl border border-(--color-error-soft) bg-(--color-paper) px-4 py-3 text-sm text-(--color-error)">
                    {error}
                  </div>
                ) : null}

                {comparison ? (
                  <>
                    <section className="mt-6 rounded-3xl border border-(--color-rule) bg-white p-6 shadow-sm">
                      <h2 className="text-xl font-semibold text-(--color-ink)">
                        Comparison Summary
                        {comparisonYear != null ? (
                          <span className="ml-2 align-middle text-sm font-medium text-(--color-muted)">
                            {comparisonYear} edition
                          </span>
                        ) : null}
                      </h2>
                      <p className="mt-3 text-sm leading-6 text-(--color-muted)">
                        {comparison.summary}
                      </p>
                      {comparison.comparison?.decisionFactors?.length ? (
                        <div className="mt-5 rounded-2xl bg-(--color-paper) p-5">
                          <h3 className="text-sm font-semibold text-(--color-muted)">
                            Decision Factors
                          </h3>
                          <ul className="mt-3 space-y-2 text-sm text-(--color-ink-2)">
                            {comparison.comparison.decisionFactors.map((factor) => (
                              <li key={factor}>{factor}</li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </section>

                    <section className="mt-6 grid gap-6 md:grid-cols-2 2xl:grid-cols-4">
                      {comparedUniversities.map((university) => {
                        const strongestRank =
                          bestAggregatedRank != null &&
                          university.aggregatedRank != null &&
                          university.aggregatedRank === bestAggregatedRank;
                        const highestTrust =
                          highestTrustScore != null &&
                          university.trustScore === highestTrustScore;

                        return (
                          <article
                            key={university.canonicalUniversityId}
                            className="rounded-3xl border border-(--color-rule) bg-white p-6 shadow-sm"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <h3 className="text-lg font-semibold text-(--color-ink)">
                                  {university.slug ? (
                                    <Link
                                      href={hrefForEdition(`/universities/${university.slug}`, comparisonYear ?? rankingYear)}
                                      className="underline decoration-(--color-rule) underline-offset-2 hover:text-(--color-ink) hover:decoration-(--color-ink)"
                                    >
                                      {university.universityName}
                                    </Link>
                                  ) : (
                                    university.universityName
                                  )}
                                </h3>
                                <p className="mt-1 text-sm text-(--color-muted)">{university.country}</p>
                              </div>
                              <span className={`rounded-full px-2.5 py-1 text-xs font-bold uppercase ${trustTone(university.trustLevel)}`}>
                                {university.trustLevel}
                              </span>
                            </div>

                            <div className="mt-5 space-y-6">
                              <section>
                                <div className="mb-2 text-xs font-bold text-(--color-muted)">
                                  Overview
                                </div>
                                <div className="space-y-2 text-sm">
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">Aggregated rank</span>
                                    <span className={`font-semibold ${strongestRank ? "text-(--color-ink)" : "text-(--color-ink)"}`}>
                                      #{formatRank(university.aggregatedRank)}
                                    </span>
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">Score</span>
                                    <span className="font-semibold text-(--color-ink)">
                                      {formatScore(university.aggregatedScore)}
                                    </span>
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">Evidence sources</span>
                                    <span className="font-semibold text-(--color-ink)">
                                      {university.evidenceSummary.availableSourceCount}
                                    </span>
                                  </div>
                                </div>
                                {strongestRank ? (
                                  <div className="mt-3 rounded-xl bg-(--color-paper-2) px-3 py-2 text-xs font-medium text-(--color-ink)">
                                    Stronger aggregated position in this comparison
                                  </div>
                                ) : null}
                              </section>

                              <section>
                                <div className="mb-2 text-xs font-bold text-(--color-muted)">
                                  Ranking Evidence
                                </div>
                                <div className="space-y-2 text-sm">
                                  {COMPARE_SOURCES.map((source) => {
                                    const evidence = university.sourceRankings?.find((row) => row.source === source);
                                    return (
                                      <div key={source} className="flex items-start justify-between gap-3">
                                        <span className="text-(--color-muted)">{source}</span>
                                        <span className="flex flex-col items-end gap-0.5">
                                          <span className="font-semibold text-(--color-ink)">
                                            {printedSourceRank(evidence, university.sourceRanks[source])}
                                          </span>
                                          {evidence ? <SourceRankChange ranking={evidence} /> : null}
                                        </span>
                                      </div>
                                    );
                                  })}
                                </div>
                              </section>

                              <section>
                                <div className="mb-2 text-xs font-bold text-(--color-muted)">
                                  Trust & Agreement
                                </div>
                                <div className="space-y-2 text-sm">
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">Trust score</span>
                                    <span className={`font-semibold ${highestTrust ? "text-(--color-ink)" : "text-(--color-ink)"}`}>
                                      {Math.round(university.trustScore)}
                                    </span>
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">Best rank</span>
                                    <span className="font-semibold text-(--color-ink)">
                                      {university.evidenceSummary.bestRank != null
                                        ? `#${formatRank(university.evidenceSummary.bestRank)}`
                                        : "—"}
                                    </span>
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">Worst rank</span>
                                    <span className="font-semibold text-(--color-ink)">
                                      {university.evidenceSummary.worstRank != null
                                        ? `#${formatRank(university.evidenceSummary.worstRank)}`
                                        : "—"}
                                    </span>
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">Spread</span>
                                    <span className="font-semibold text-(--color-ink)">
                                      {university.evidenceSummary.spread != null
                                        ? formatRank(university.evidenceSummary.spread)
                                        : "—"}
                                    </span>
                                  </div>
                                </div>
                                <div className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-xs font-bold uppercase ${agreementTone(university.evidenceSummary.agreementLevel)}`}>
                                  {university.evidenceSummary.agreementLevel}
                                </div>
                                <p className="mt-3 text-sm leading-6 text-(--color-muted)">
                                  {university.evidenceSummary.note}
                                </p>
                                {highestTrust ? (
                                  <div className="mt-3 rounded-xl bg-(--color-paper-2) px-3 py-2 text-xs font-medium text-(--color-ink)">
                                    Highest trust signal among selected universities
                                  </div>
                                ) : null}
                              </section>

                              <section>
                                <div className="mb-2 text-xs font-bold text-(--color-muted)">
                                  Admissions / Fit
                                </div>
                                <div className="space-y-2 text-sm">
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">IELTS minimum</span>
                                    <span className="font-semibold text-(--color-ink)">
                                      {formatIelts(university.ieltsMin)}
                                    </span>
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <span className="text-(--color-muted)">Recommendation fit</span>
                                    <span className="font-semibold text-(--color-ink)">—</span>
                                  </div>
                                </div>
                              </section>

                              <section>
                                <div className="mb-2 text-xs font-bold text-(--color-muted)">
                                  Notes / Warnings
                                </div>
                                {university.warnings.length > 0 || university.trustExplain.notes.length > 0 ? (
                                  <ul className="space-y-2 text-sm text-(--color-muted)">
                                    {university.trustExplain.notes.map((note) => (
                                      <li key={note}>{note}</li>
                                    ))}
                                    {university.warnings.map((warning) => (
                                      <li key={warning} className="text-(--color-error)">
                                        {warning}
                                      </li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="text-sm text-(--color-muted)">No major warnings.</p>
                                )}
                              </section>
                            </div>
                          </article>
                        );
                      })}
                    </section>
                    <CaveatBanner
                      className="mt-6"
                      caveats={[
                        ...editionCaveats(comparisonYear ?? rankingYear),
                        comparedUniversities.some((university) => {
                          const rows = university.sourceRankings ?? [];
                          return anyRankChangeShown(rows) || anyEntityChanged(rows);
                        })
                          ? CAVEAT_RANK_CHANGE
                          : null,
                      ]}
                    />
                    {/* Every held edition, so outside the edition selector's scope; it carries its own caveats. */}
                    <section className="mt-6 rounded-3xl border border-(--color-rule) bg-white p-6 shadow-sm">
                      <h2 className="text-xl font-semibold text-(--color-ink)">Rank history by source</h2>
                      <p className="mt-1 mb-4 text-sm text-(--color-muted)">
                        Each source&apos;s own printed rank in every edition held, one chart per source. Ranks from
                        different sources are not combined.
                      </p>
                      <CompareRankHistory universities={selectedUniversities} />
                    </section>
                  </>
                ) : loading ? (
                  <section className="mt-6 grid gap-6 md:grid-cols-2 2xl:grid-cols-4">
                    {Array.from({ length: Math.min(selectedCount, MAX_COMPARE_ITEMS) }).map((_, index) => (
                      <div
                        key={index}
                        className="rounded-3xl border border-(--color-rule) bg-white p-6 shadow-sm"
                      >
                        <div className="h-5 w-32 animate-pulse rounded bg-(--color-paper-2)" />
                        <div className="mt-4 h-4 w-20 animate-pulse rounded bg-(--color-paper-2)" />
                        <div className="mt-6 space-y-3">
                          {Array.from({ length: 8 }).map((__, rowIndex) => (
                            <div key={rowIndex} className="h-4 animate-pulse rounded bg-(--color-paper-2)" />
                          ))}
                        </div>
                      </div>
                    ))}
                  </section>
                ) : null}
              </>
            ) : null}

            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/"
                className="border border-(--color-ink) px-4 py-3 text-sm font-semibold text-(--color-ink) transition hover:bg-(--color-paper-2)"
              >
                Back to rankings
              </Link>
              <Link
                href="/recommendations"
                className="bg-(--color-ink) px-4 py-3 text-sm font-semibold text-white transition hover:bg-(--color-ink-2)"
              >
                Continue to recommendations
              </Link>
            </div>
          </>
        )}
      </div>
    </main>
  );
}
