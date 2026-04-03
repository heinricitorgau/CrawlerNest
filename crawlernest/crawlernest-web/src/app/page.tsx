"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { rankingUniverseConfig } from "@/lib/rankingUniverseConfig";
import { buildRankingViewModel } from "@/lib/rankingViewModel";
import { formatRank } from "@/lib/format";
import type {
  RankingApiRow,
  RankingPresentationRow,
  RankingScope,
} from "@/types/ranking";

const REFRESH_INTERVAL_MS = 5000;
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
  const searchParams = useSearchParams();
  const [isClientReady, setIsClientReady] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [items, setItems] = useState<RankingApiRow[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);

  useEffect(() => {
    setIsClientReady(true);
  }, []);

  const scope = isClientReady
    ? ((searchParams.get("scope") as RankingScope) ?? "global")
    : "global";
  const region = isClientReady ? (searchParams.get("region") ?? "Europe") : "Europe";
  const year = isClientReady ? Number(searchParams.get("year") ?? "2026") : 2026;
  const page = isClientReady ? Number(searchParams.get("page") ?? "1") : 1;
  const pageSize = isClientReady ? Number(searchParams.get("pageSize") ?? "20") : 20;
  const searchQuery = isClientReady ? (searchParams.get("search") ?? "") : "";
  const universe = scope === "region" ? "region" : "global";
  const universeConfig = rankingUniverseConfig[universe];

  useEffect(() => {
    setSearchInput(searchQuery);
  }, [searchQuery]);

  const navigate = useCallback(
    (updates: Record<string, string | number | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === "") {
          params.delete(key);
        } else {
          params.set(key, String(value));
        }
      }
      router.replace(`/?${params.toString()}`);
    },
    [router, searchParams]
  );

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

  useEffect(() => {
    if (!isClientReady) {
      return;
    }

    const id = setInterval(() => {
      setRefreshTrigger((value) => value + 1);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isClientReady]);

  useEffect(() => {
    if (!isClientReady) {
      return;
    }

    const bump = () => setRefreshTrigger((value) => value + 1);
    window.addEventListener("focus", bump);
    document.addEventListener("visibilitychange", bump);
    window.addEventListener("online", bump);
    return () => {
      window.removeEventListener("focus", bump);
      document.removeEventListener("visibilitychange", bump);
      window.removeEventListener("online", bump);
    };
  }, [isClientReady]);

  useEffect(() => {
    if (!isClientReady) {
      return;
    }

    let isMounted = true;
    const controller = new AbortController();

    async function fetchRankings() {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          page: String(page),
          pageSize: String(pageSize),
          year: String(year),
          scope,
          ...(scope === "region" ? { region } : {}),
          ...(searchQuery ? { search: searchQuery } : {}),
          _ts: Date.now().toString(),
        });

        const res = await fetch(`/api/rankings?${params.toString()}`, {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const payload = await res.json();

        if (isMounted) {
          setItems(Array.isArray(payload?.data?.items) ? payload.data.items : []);
          setTotalCount(payload?.metadata?.totalCount ?? 0);
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }

        if (isMounted) {
          setError("Failed to load rankings. Please retry.");
          setItems([]);
          setTotalCount(0);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchRankings();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [isClientReady, page, pageSize, year, scope, region, searchQuery, refreshTrigger]);

  const isInShortlist = (id: number) =>
    shortlist.some((item) => item.canonicalUniversityId === id);

  const presentationItems: RankingPresentationRow[] = items.map((item) =>
    buildRankingViewModel(item, { scope, region })
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

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const canGoPrevious = page > 1 && !loading;
  const canGoNext = !loading && items.length === pageSize;
  const trustSources = (item: RankingPresentationRow) =>
    (["QS", "THE", "ARWU"] as const)
      .filter((source) => item.trustExplain?.sources[source] != null)
      .join(", ");
  const evidenceRows = (item: RankingPresentationRow) => {
    const sources = item.aggregationExplain?.sources;
    const availableRanks = (["QS", "THE", "ARWU"] as const)
      .map((source) => sources?.[source] ?? null)
      .filter((value): value is number => value != null);
    const bestRank = availableRanks.length > 0 ? Math.min(...availableRanks) : null;

    return (["QS", "THE", "ARWU"] as const).map((source) => {
      const rank = sources?.[source] ?? null;
      return {
        source,
        rank,
        hasLargeDifference:
          rank != null && bestRank != null && Math.abs(rank - bestRank) > 20,
      };
    });
  };
  const evidenceHint = (item: RankingPresentationRow) => {
    const available = evidenceRows(item).filter((row) => row.rank != null);
    if (available.length <= 1) {
      return "Only one source available";
    }
    const ranks = available.map((row) => row.rank as number);
    const spread = Math.max(...ranks) - Math.min(...ranks);
    if (spread <= 5) {
      return "Strong agreement across ranking sources";
    }
    if (spread <= 20) {
      return "Moderate variation across sources";
    }
    return "High disagreement — interpret carefully";
  };

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
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  navigate({ search: searchInput || null, page: 1 });
                }
              }}
              className="w-full rounded-lg border border-[#e0ddd8] bg-[#f5f3ee] px-4 py-2 pr-8 text-sm outline-none transition focus:border-[#1a3d2e] focus:bg-white"
            />
            {searchInput && (
              <button
                onClick={() => {
                  setSearchInput("");
                  navigate({ search: null, page: 1 });
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
            <div className="rounded-2xl border border-[#e0ddd8] bg-white p-5 shadow-sm">
              <h3 className="mb-4 text-xs font-bold uppercase tracking-[0.15em] text-[#6b7068]">
                Filters
              </h3>

              <div className="mb-5">
                <label className="mb-1.5 block text-xs font-semibold text-[#1a3d2e]">
                  Year
                </label>
                <select
                  value={year}
                  onChange={(e) => navigate({ year: e.target.value, page: 1 })}
                  className="w-full rounded-lg border border-[#e0ddd8] bg-[#f5f3ee] px-3 py-2 text-sm outline-none transition focus:border-[#1a3d2e]"
                >
                  <option value="2026">2026</option>
                  <option value="2025">2025</option>
                  <option value="2024">2024</option>
                </select>
              </div>

              <div className="mb-5">
                <label className="mb-1.5 block text-xs font-semibold text-[#1a3d2e]">
                  Scope
                </label>
                <div className="flex overflow-hidden rounded-lg border border-[#e0ddd8]">
                  {(["global", "region"] as const).map((nextScope) => (
                    <button
                      key={nextScope}
                      onClick={() => navigate({ scope: nextScope, page: 1 })}
                      className={`flex-1 py-2 text-xs font-semibold capitalize transition ${
                        scope === nextScope
                          ? "bg-[#1a3d2e] text-white"
                          : "bg-white text-[#6b7068] hover:bg-[#f5f3ee]"
                      }`}
                    >
                      {nextScope}
                    </button>
                  ))}
                </div>
              </div>

              {scope === "region" && (
                <div className="mb-5">
                  <label className="mb-1.5 block text-xs font-semibold text-[#1a3d2e]">
                    Region
                  </label>
                  <select
                    value={region}
                    onChange={(e) => navigate({ region: e.target.value, page: 1 })}
                    className="w-full rounded-lg border border-[#e0ddd8] bg-[#f5f3ee] px-3 py-2 text-sm outline-none transition focus:border-[#1a3d2e]"
                  >
                    {REGION_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="mb-5">
                <label className="mb-1.5 block text-xs font-semibold text-[#1a3d2e]">
                  Per Page
                </label>
                <select
                  value={pageSize}
                  onChange={(e) => navigate({ pageSize: e.target.value, page: 1 })}
                  className="w-full rounded-lg border border-[#e0ddd8] bg-[#f5f3ee] px-3 py-2 text-sm outline-none transition focus:border-[#1a3d2e]"
                >
                  <option value="20">20</option>
                  <option value="50">50</option>
                  <option value="100">100</option>
                </select>
              </div>

              <button
                onClick={() =>
                  navigate({
                    scope: "global",
                    region: null,
                    year: 2026,
                    search: null,
                    page: 1,
                  })
                }
                className="w-full rounded-lg border border-[#e0ddd8] py-2 text-xs font-semibold text-[#6b7068] transition hover:border-[#1a3d2e] hover:text-[#1a3d2e]"
              >
                Reset Filters
              </button>
            </div>
          </aside>

          <div className="min-w-0 flex-1">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-[#1a3d2e]">
                  {year} Rankings · {scope === "region" ? region : "Global"}
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
                  onClick={() => setRefreshTrigger((value) => value + 1)}
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
                    {presentationItems.length === 0 ? (
                      <tr>
                        <td
                          colSpan={6}
                          className="py-20 text-center italic text-[#6b7068]"
                        >
                          No universities found.
                        </td>
                      </tr>
                    ) : (
                      presentationItems.map((item) => {
                        const inList = isInShortlist(item.canonicalUniversityId);
                        return (
                          <tr
                            key={`${item.canonicalUniversityId}-${item.slug}-${item.shortlistRank}`}
                            className="border-t border-[#e0ddd8] transition hover:bg-[#f5f3ee]"
                          >
                            <td className="px-4 py-3.5 text-center font-bold text-[#1a3d2e]">
                              <div>{item.primaryRankLabel}</div>
                              {item.secondaryRankLabel && (
                                <div className="mt-0.5 text-[11px] font-medium text-[#6b7068]">
                                  {item.secondaryRankLabel}
                                </div>
                              )}
                            </td>
                            <td className="px-4 py-3.5">
                              <Link
                                href={`/universities/${item.slug}`}
                                className="font-medium text-[#1a1a1a] underline decoration-[#c0bdb8] underline-offset-2 transition hover:text-[#1a3d2e] hover:decoration-[#1a3d2e]"
                              >
                                {item.title}
                              </Link>
                              <div className="mt-1 flex items-center gap-2 text-xs text-[#6b7068]">
                                <span>{item.subtitle}</span>
                                <span
                                  className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${
                                    item.badgeTone === "accent"
                                      ? "bg-[#e8f2ec] text-[#1a3d2e]"
                                      : "bg-[#f0ede7] text-[#6b7068]"
                                  }`}
                                >
                                  {item.badgeLabel}
                                </span>
                                {item.trustLevel && (
                                  <span
                                    className={`inline-flex items-center rounded-full px-2 py-0.5 font-semibold uppercase tracking-[0.08em] ${
                                      item.trustLevel === "high"
                                        ? "bg-[#e8f2ec] text-[#1a3d2e]"
                                        : item.trustLevel === "medium"
                                          ? "bg-[#f3ecd6] text-[#8a6116]"
                                          : "bg-[#f3e7e4] text-[#8b3a2b]"
                                    }`}
                                  >
                                    {item.trustLevel} {item.trustScore != null ? Math.round(item.trustScore) : ""}
                                  </span>
                                )}
                                {item.trustLevel === "low" && (
                                  <span className="text-[11px] font-medium text-[#8b3a2b]">
                                    Limited data — interpret with caution.
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3.5 text-[#6b7068]">
                              {item.country}
                            </td>
                            <td className="px-4 py-3.5 text-right font-mono font-semibold text-[#1a1a1a]">
                              <div>{item.scoreLabel}</div>
                              <div className="mt-0.5 text-[11px] font-sans font-medium text-[#6b7068]">
                                {item.scoreCaption}
                              </div>
                            </td>
                            <td className="px-4 py-3.5 text-center">
                              <span className="inline-flex items-center rounded-full bg-[#e8f2ec] px-2.5 py-0.5 text-xs font-medium text-[#1a3d2e]">
                                {item.sourceCoverageLabel}
                              </span>
                              <div className="mt-1 text-[11px] text-[#6b7068]">
                                {item.rankingUniverseLabel}
                              </div>
                              {item.aggregationExplain && item.aggregationExplain.availableSourceCount > 0 && (
                                <details className="mt-2 text-left">
                                  <summary className="cursor-pointer text-[11px] font-medium text-[#1a3d2e]">
                                    Ranking Evidence
                                  </summary>
                                  <div className="mt-2 rounded-xl border border-[#e0ddd8] bg-[#f5f3ee] p-3 text-[11px] text-[#4f544d] shadow-sm">
                                    <div className="font-semibold text-[#1a1a1a]">
                                      Ranking Evidence
                                    </div>
                                    <div className="mt-2 space-y-1.5">
                                      {evidenceRows(item).map((row) => (
                                        <div key={row.source} className="flex items-center justify-between">
                                          <span className="font-medium text-[#4f544d]">
                                            {row.source}
                                          </span>
                                          <span
                                            className={`font-semibold ${
                                              row.hasLargeDifference
                                                ? "text-[#8b3a2b]"
                                                : "text-[#1a1a1a]"
                                            }`}
                                          >
                                            {row.rank != null ? `#${formatRank(row.rank)}` : "—"}
                                            {row.hasLargeDifference ? "  Large difference" : ""}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                    <div className="mt-2 border-t border-[#ddd7cf] pt-2">
                                      <div className="flex items-center justify-between">
                                        <span>Aggregated Rank (weighted)</span>
                                        <span className="font-semibold text-[#1a1a1a]">
                                          {item.aggregationExplain.aggregatedRankValue.toFixed(2)}
                                        </span>
                                      </div>
                                      <div className="mt-2 font-semibold text-[#1a1a1a]">
                                        Weights
                                      </div>
                                      <div className="mt-1 space-y-1">
                                        {(["QS", "THE", "ARWU"] as const).map((source) => (
                                          <div key={source} className="flex items-center justify-between">
                                            <span>{source}</span>
                                            <span>{Math.round((item.aggregationExplain?.weights[source] ?? 0) * 100)}%</span>
                                          </div>
                                        ))}
                                      </div>
                                      <div className="mt-2 rounded-lg bg-white/70 px-2.5 py-2 text-[#6b7068]">
                                        {evidenceHint(item)}
                                      </div>
                                      {item.trustLevel && item.trustExplain && item.trustScore != null && (
                                        <div className="mt-2 border-t border-[#ddd7cf] pt-2">
                                          <div className="flex items-center justify-between">
                                            <span>Trust</span>
                                            <span className="font-semibold uppercase text-[#1a1a1a]">
                                              {item.trustLevel} ({Math.round(item.trustScore)})
                                            </span>
                                          </div>
                                          <div className="mt-1">
                                            Sources: {trustSources(item).split(", ").filter(Boolean).length}
                                            {" "}
                                            ({trustSources(item)})
                                          </div>
                                          <div className="mt-1">
                                            Consistency: {item.trustExplain.consistencyScore >= 100 ? "strong" : item.trustExplain.consistencyScore >= 70 ? "moderate" : "weak"}
                                            {" "}(std = {item.trustExplain.stdDeviation.toFixed(1)})
                                          </div>
                                          <div className="mt-1">
                                            Coverage: {item.trustExplain.coverageScore >= 100 ? "full" : item.trustExplain.coverageScore >= 65 ? "partial" : "limited"}
                                          </div>
                                          <div className="mt-2">
                                            <div className="font-semibold text-[#1a1a1a]">
                                              Trust Analysis
                                            </div>
                                            <div className="mt-1 space-y-1">
                                              {item.trustExplain.notes.map((note) => (
                                                <div key={note}>
                                                  {note.toLowerCase().includes("strong agreement") ? "✓" : "⚠"} {note}
                                                </div>
                                              ))}
                                            </div>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </details>
                              )}
                            </td>
                            <td className="px-4 py-3.5 text-center">
                              <button
                                onClick={() => toggleShortlist(item)}
                                title={
                                  inList
                                    ? "Remove from shortlist"
                                    : "Add to shortlist"
                                }
                                className={`h-7 w-7 rounded-full text-sm font-bold transition ${
                                  inList
                                    ? "bg-[#1a3d2e] text-white"
                                    : "bg-[#f5f3ee] text-[#6b7068] hover:bg-[#e8f2ec] hover:text-[#1a3d2e]"
                                }`}
                              >
                                {inList ? "✓" : "+"}
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              )}
            </div>

            <div className="mt-6 flex items-center justify-between">
              <span className="text-sm text-[#6b7068]">
                Page {page} of {totalPages}
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={!canGoPrevious}
                  onClick={() => navigate({ page: page - 1 })}
                  className="rounded-lg border border-[#e0ddd8] bg-white px-4 py-2 text-sm font-medium text-[#1a1a1a] transition hover:border-[#1a3d2e] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Previous
                </button>
                <span className="rounded-lg bg-[#1a3d2e] px-4 py-2 text-sm font-semibold text-white">
                  {page}
                </span>
                <button
                  disabled={!canGoNext}
                  onClick={() => navigate({ page: page + 1 })}
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
                    href="/recommendations#comparison"
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
