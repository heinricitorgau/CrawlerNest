"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import RankingFiltersPanel from "@/components/rankings/RankingFiltersPanel";
import RankingRow from "@/components/rankings/RankingRow";
import { useRankingFilters } from "@/hooks/useRankingFilters";
import { useRankings } from "@/hooks/useRankings";
import { rankingUniverseConfig } from "@/lib/rankingUniverseConfig";
import { buildRankingViewModel } from "@/lib/rankingViewModel";
import { formatRank } from "@/lib/format";
import type { RankingPresentationRow } from "@/types/ranking";

const SHORTLIST_STORAGE_KEY = "crawlernest_shortlist";

const REGION_OPTIONS = [
  "Africa",
  "Arab Region",
  "Asia",
  "Europe",
  "Latin America",
  "North America",
  "Oceania",
];

type ShortlistItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  slug: string;
};

function RankingsPageShell() {
  return (
    <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
      <section
        className="relative overflow-hidden py-16"
        style={{ background: "linear-gradient(135deg, #1a3d2e 0%, #0f2318 100%)" }}
      >
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(circle at 30% 50%, rgba(61,122,90,0.3), transparent 55%)",
          }}
        />
        <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
          <div className="max-w-2xl">
            <div className="h-4 w-24 animate-pulse rounded bg-white/20" />
            <div className="mt-3 h-12 w-80 animate-pulse rounded bg-white/20" />
            <div className="mt-4 h-5 w-96 animate-pulse rounded bg-white/10" />
          </div>
        </div>
      </section>

      <div className="sticky top-0 z-40 border-b border-[#e0ddd8] bg-white/95 shadow-sm backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-6 lg:px-8">
          <div className="h-10 max-w-lg flex-1 animate-pulse rounded-lg bg-[#e0ddd8]" />
          <div className="hidden h-4 w-28 animate-pulse rounded bg-[#e0ddd8] sm:block" />
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
        <div className="flex gap-6">
          <aside className="w-52 flex-shrink-0">
            <div className="rounded-2xl border border-[#e0ddd8] bg-white p-5 shadow-sm">
              <div className="h-3 w-16 animate-pulse rounded bg-[#e0ddd8]" />
              <div className="mt-5 space-y-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index}>
                    <div className="mb-2 h-3 w-12 animate-pulse rounded bg-[#e0ddd8]" />
                    <div className="h-10 animate-pulse rounded-lg bg-[#f5f3ee]" />
                  </div>
                ))}
              </div>
            </div>
          </aside>

          <div className="min-w-0 flex-1">
            <div className="mb-4">
              <div className="h-4 w-48 animate-pulse rounded bg-[#e0ddd8]" />
              <div className="mt-2 h-3 w-96 animate-pulse rounded bg-[#e0ddd8]" />
              <div className="mt-2 h-3 w-80 animate-pulse rounded bg-[#e0ddd8]" />
            </div>

            <div className="overflow-x-auto rounded-2xl border border-[#e0ddd8] bg-white shadow-sm">
              <div className="divide-y divide-[#e0ddd8]">
                {Array.from({ length: 10 }).map((_, index) => (
                  <div key={index} className="flex h-14 items-center gap-4 px-4">
                    <div className="h-4 w-8 animate-pulse rounded bg-[#e0ddd8]" />
                    <div className="h-4 flex-1 animate-pulse rounded bg-[#e0ddd8]" />
                    <div className="h-4 w-24 animate-pulse rounded bg-[#e0ddd8]" />
                    <div className="h-4 w-16 animate-pulse rounded bg-[#e0ddd8]" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function RankingsPageContent() {
  const router = useRouter();
  const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);
  const {
    isClientReady,
    searchInput,
    setSearchInput,
    scope,
    region,
    year,
    page,
    pageSize,
    searchQuery,
    country,
    normalizedSelectedCountry,
    countryOptions,
    navigate,
  } = useRankingFilters([], {});
  const { items, metadata, totalCount, loading, error, totalPages } = useRankings({
    isClientReady,
    page,
    pageSize,
    year,
    scope,
    region,
    searchQuery,
    country,
  });
  const filters = useRankingFilters(items, metadata);
  const activeFilters = filters.isClientReady ? filters : {
    isClientReady,
    searchInput,
    setSearchInput,
    scope,
    region,
    year,
    page,
    pageSize,
    searchQuery,
    country,
    normalizedSelectedCountry,
    countryOptions,
    navigate,
  };
  const universe = activeFilters.scope === "region" ? "region" : "global";
  const universeConfig = rankingUniverseConfig[universe];

  useEffect(() => {
    if (!isClientReady) {
      return;
    }

    try {
      const stored = localStorage.getItem(SHORTLIST_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setShortlist(parsed);
        }
      }
    } catch {
      // ignore localStorage parse errors
    }
  }, [isClientReady]);

  useEffect(() => {
    if (!isClientReady) {
      return;
    }

    try {
      localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(shortlist));
    } catch {
      // ignore localStorage write errors
    }
  }, [isClientReady, shortlist]);

  const isInShortlist = (id: number) =>
    shortlist.some((item) => item.canonicalUniversityId === id);

  const presentationItems: RankingPresentationRow[] = items.map((item) =>
    buildRankingViewModel(item, { scope: activeFilters.scope, region: activeFilters.region })
  );

  const toggleShortlist = (item: RankingPresentationRow) => {
    setShortlist((prev) =>
      isInShortlist(item.canonicalUniversityId)
        ? prev.filter(
            (entry) => entry.canonicalUniversityId !== item.canonicalUniversityId
          )
        : [
            ...prev,
            {
              canonicalUniversityId: item.canonicalUniversityId,
              universityName: item.title,
              country: item.country,
              aggregatedRank: item.shortlistRank,
              slug: item.slug,
            },
          ]
    );
  };

  const goToRecommendations = () => {
    localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(shortlist));
    router.push("/recommendations");
  };

  const canGoPrevious = activeFilters.page > 1 && !loading;
  const canGoNext = !loading && items.length === activeFilters.pageSize;
  const emptyStateMessage = useMemo(() => {
    if (activeFilters.country) {
      if (activeFilters.scope === "region") {
        return `No universities found for ${activeFilters.normalizedSelectedCountry} in ${activeFilters.region}.`;
      }
      return `No universities found for ${activeFilters.normalizedSelectedCountry}.`;
    }

    if (activeFilters.scope === "region") {
      return `No universities found in ${activeFilters.region}.`;
    }

    return "No universities found for the current filters.";
  }, [activeFilters.country, activeFilters.normalizedSelectedCountry, activeFilters.region, activeFilters.scope]);

  if (!isClientReady) {
    return <RankingsPageShell />;
  }

  return (
    <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
      <section
        className="relative overflow-hidden py-16"
        style={{ background: "linear-gradient(135deg, #1a3d2e 0%, #0f2318 100%)" }}
      >
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(circle at 30% 50%, rgba(61,122,90,0.3), transparent 55%)",
          }}
        />
        <div className="relative mx-auto max-w-7xl px-6 lg:px-8">
          <div className="max-w-2xl">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-[#7dbf9a]">
              CrawlerNest
            </p>
            <h1 className="mt-3 text-4xl font-bold tracking-tight text-white sm:text-5xl">
              World University Rankings
            </h1>
            <p className="mt-4 text-lg leading-7 text-[#a8c5b5]">
              Comparing universities across ranking universes with aggregated multi-source signals.
            </p>
          </div>
        </div>
      </section>

      <div className="sticky top-0 z-40 border-b border-[#e0ddd8] bg-white/95 shadow-sm backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-6 lg:px-8">
          <div className="relative max-w-lg flex-1">
            <input
              type="text"
              placeholder="Search universities… (press Enter)"
              value={activeFilters.searchInput}
              onChange={(e) => activeFilters.setSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  activeFilters.navigate({ search: activeFilters.searchInput || null, page: 1 });
                }
              }}
              className="w-full rounded-lg border border-[#e0ddd8] bg-[#f5f3ee] px-4 py-2 pr-8 text-sm outline-none transition focus:border-[#1a3d2e] focus:bg-white"
            />
            {activeFilters.searchInput && (
              <button
                onClick={() => {
                  activeFilters.setSearchInput("");
                  activeFilters.navigate({ search: null, page: 1 });
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#6b7068] transition hover:text-[#1a1a1a]"
                aria-label="Clear search"
              >
                ×
              </button>
            )}
          </div>
          <div className="hidden text-sm text-[#6b7068] sm:block">
            {loading ? (
              <span className="animate-pulse">Loading…</span>
            ) : (
              <span>
                <span className="font-semibold text-[#1a1a1a]">
                  {totalCount.toLocaleString()}
                </span>{" "}
                universities
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
        <div className="flex gap-6">
          <aside className="w-52 flex-shrink-0">
            <RankingFiltersPanel
              year={activeFilters.year}
              scope={activeFilters.scope}
              region={activeFilters.region}
              country={activeFilters.country}
              pageSize={activeFilters.pageSize}
              countryOptions={activeFilters.countryOptions}
              regionOptions={REGION_OPTIONS}
              onUpdate={activeFilters.navigate}
            />
          </aside>

          <div className="min-w-0 flex-1">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-[#1a3d2e]">
                  {activeFilters.year} Rankings · {activeFilters.scope === "region" ? activeFilters.region : "Global"}
                </h2>
                <p className="mt-1 text-xs text-[#6b7068]">
                  This ranking is computed by combining multiple sources (QS, THE, ARWU) using a weighted rank model.
                </p>
                <p className="mt-1 text-xs text-[#6b7068]">
                  Trust score reflects data completeness and consistency across ranking sources.
                </p>
                <p className="mt-1 text-xs text-[#6b7068]">
                  Rankings are aggregated from multiple sources (QS, THE, ARWU). Differences between sources are shown for transparency.
                </p>
              </div>
              {shortlist.length > 0 && (
                <button
                  onClick={goToRecommendations}
                  className="rounded-full bg-[#1a3d2e] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
                >
                  Generate Recommendation ({shortlist.length})
                </button>
              )}
            </div>

            {error && (
              <div className="mb-4 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <span>{error}</span>
                <button
                  onClick={() => router.refresh()}
                  className="ml-4 font-semibold underline"
                >
                  Retry
                </button>
              </div>
            )}

            <div className="overflow-x-auto rounded-2xl border border-[#e0ddd8] bg-white shadow-sm">
              {loading ? (
                <div className="divide-y divide-[#e0ddd8]">
                  {Array.from({ length: 10 }).map((_, index) => (
                    <div key={index} className="flex h-14 items-center gap-4 px-4">
                      <div className="h-4 w-8 animate-pulse rounded bg-[#e0ddd8]" />
                      <div className="h-4 flex-1 animate-pulse rounded bg-[#e0ddd8]" />
                      <div className="h-4 w-24 animate-pulse rounded bg-[#e0ddd8]" />
                      <div className="h-4 w-16 animate-pulse rounded bg-[#e0ddd8]" />
                    </div>
                  ))}
                </div>
              ) : (
                <table className="min-w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-[#e0ddd8] bg-[#f5f3ee]">
                      <th className="w-16 px-4 py-3 text-center text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        {universeConfig.rankHeading}
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        University
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        Location
                      </th>
                      <th className="w-28 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        {universeConfig.scoreHeading}
                      </th>
                      <th className="w-24 px-4 py-3 text-center text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        Sources
                      </th>
                      <th className="w-16 px-4 py-3 text-center text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        Save
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {!error && presentationItems.length === 0 ? (
                      <tr>
                        <td
                          colSpan={6}
                          className="py-20 text-center italic text-[#6b7068]"
                        >
                          {emptyStateMessage}
                          <span className="mt-2 block text-xs not-italic text-[#8a8f87]">
                            Try another country or broaden your filters.
                          </span>
                        </td>
                      </tr>
                    ) : !error ? (
                      presentationItems.map((item) => (
                        <RankingRow
                          key={`${item.canonicalUniversityId}-${item.slug}-${item.shortlistRank}`}
                          item={item}
                          inShortlist={isInShortlist(item.canonicalUniversityId)}
                          onToggleShortlist={toggleShortlist}
                        />
                      ))
                    ) : (
                      <tr>
                        <td
                          colSpan={6}
                          className="py-20 text-center italic text-[#6b7068]"
                        >
                          Rankings could not be loaded for the current filters.
                          <span className="mt-2 block text-xs not-italic text-[#8a8f87]">
                            Please retry or adjust your filters.
                          </span>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              )}
            </div>

            <div className="mt-6 flex items-center justify-between">
              <span className="text-sm text-[#6b7068]">
                Page {activeFilters.page} of {totalPages}
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={!canGoPrevious}
                  onClick={() => activeFilters.navigate({ page: activeFilters.page - 1 })}
                  className="rounded-lg border border-[#e0ddd8] bg-white px-4 py-2 text-sm font-medium text-[#1a1a1a] transition hover:border-[#1a3d2e] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Previous
                </button>
                <span className="rounded-lg bg-[#1a3d2e] px-4 py-2 text-sm font-semibold text-white">
                  {activeFilters.page}
                </span>
                <button
                  disabled={!canGoNext}
                  onClick={() => activeFilters.navigate({ page: activeFilters.page + 1 })}
                  className="rounded-lg border border-[#e0ddd8] bg-white px-4 py-2 text-sm font-medium text-[#1a1a1a] transition hover:border-[#1a3d2e] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </div>

          {shortlist.length > 0 && (
            <aside className="w-60 flex-shrink-0">
              <div className="sticky top-20 rounded-2xl border border-[#e0ddd8] bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-sm font-bold text-[#1a3d2e]">
                    Shortlist ({shortlist.length})
                  </h3>
                  <button
                    onClick={() => setShortlist([])}
                    className="text-xs text-[#6b7068] transition hover:text-red-600"
                  >
                    Clear all
                  </button>
                </div>

                <ul className="space-y-2">
                  {shortlist.map((item) => (
                    <li
                      key={`${item.canonicalUniversityId}-${item.slug}`}
                      className="flex items-start justify-between gap-2 rounded-xl border border-[#e8f2ec] bg-[#f5f3ee] px-3 py-2.5"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-xs font-semibold text-[#1a1a1a]">
                          {item.universityName}
                        </div>
                        <div className="mt-0.5 text-xs text-[#6b7068]">
                          #{formatRank(item.aggregatedRank)} · {item.country}
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setShortlist((prev) =>
                            prev.filter(
                              (entry) =>
                                entry.canonicalUniversityId !==
                                item.canonicalUniversityId
                            )
                          )
                        }
                        className="mt-0.5 flex-shrink-0 text-[#6b7068] transition hover:text-red-600"
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>

                {shortlist.length >= 2 && (
                  <Link
                    href="/compare"
                    className="mt-3 block w-full rounded-full border border-[#1a3d2e] py-2 text-center text-sm font-semibold text-[#1a3d2e] transition hover:bg-[#e8f2ec]"
                  >
                    Compare Selected
                  </Link>
                )}

                <button
                  onClick={goToRecommendations}
                  className="mt-3 w-full rounded-full bg-[#1a3d2e] py-2.5 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
                >
                  Generate Recommendation
                </button>
              </div>
            </aside>
          )}
        </div>
      </div>
    </main>
  );
}

export default function RankingsHomePage() {
  return (
    <Suspense fallback={<RankingsPageShell />}>
      <RankingsPageContent />
    </Suspense>
  );
}
