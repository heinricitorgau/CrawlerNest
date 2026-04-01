"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { formatRank, formatScore } from "@/lib/format";

const REFRESH_INTERVAL_MS = 5000;
const SHORTLIST_STORAGE_KEY = "crawlernest_shortlist";
const PAGE_SIZE = 20;

const REGION_OPTIONS = [
  "Africa",
  "Arab Region",
  "Asia",
  "Europe",
  "Latin America",
  "North America",
  "Oceania",
];

type RankingItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  globalRank?: number;
  scopeRank?: number;
  compositeScore: number;
  rankingYear?: number;
  primarySource?: string;
  sourceCount: number;
  slug: string;
};

type ShortlistItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  slug: string;
};

function RankingsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const scope = (searchParams.get("scope") as "global" | "region") ?? "global";
  const region = searchParams.get("region") ?? "Europe";
  const year = Number(searchParams.get("year") ?? "2026");
  const page = Number(searchParams.get("page") ?? "1");
  const searchQuery = searchParams.get("search") ?? "";

  const [searchInput, setSearchInput] = useState(searchQuery);
  const [items, setItems] = useState<RankingItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);

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
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(shortlist));
    } catch {
      // ignore localStorage write errors
    }
  }, [shortlist]);

  useEffect(() => {
    const id = setInterval(() => {
      setRefreshTrigger((value) => value + 1);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const bump = () => setRefreshTrigger((value) => value + 1);
    window.addEventListener("focus", bump);
    document.addEventListener("visibilitychange", bump);
    window.addEventListener("online", bump);
    return () => {
      window.removeEventListener("focus", bump);
      document.removeEventListener("visibilitychange", bump);
      window.removeEventListener("online", bump);
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function fetchRankings() {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          page: String(page),
          pageSize: String(PAGE_SIZE),
          year: String(year),
          scope,
          ...(scope === "region" ? { region } : {}),
          ...(searchQuery ? { search: searchQuery } : {}),
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
  }, [page, year, scope, region, searchQuery, refreshTrigger]);

  const isInShortlist = (id: number) =>
    shortlist.some((item) => item.canonicalUniversityId === id);

  const toggleShortlist = (item: RankingItem) => {
    setShortlist((prev) =>
      isInShortlist(item.canonicalUniversityId)
        ? prev.filter(
            (entry) => entry.canonicalUniversityId !== item.canonicalUniversityId
          )
        : [
            ...prev,
            {
              canonicalUniversityId: item.canonicalUniversityId,
              universityName: item.universityName,
              country: item.country,
              aggregatedRank: item.aggregatedRank,
              slug: item.slug,
            },
          ]
    );
  };

  const goToRecommendations = () => {
    localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(shortlist));
    router.push("/recommendations");
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const canGoPrevious = page > 1;
  const canGoNext = page < totalPages;

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
              Comparing 1,500+ global institutions. Aggregate data from QS, THE, and more.
            </p>
          </div>
        </div>
      </section>

      <div className="sticky top-0 z-40 border-b border-[#e0ddd8] bg-white/95 shadow-sm backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-6 lg:px-8">
          <div className="max-w-lg flex-1">
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
              className="w-full rounded-lg border border-[#e0ddd8] bg-[#f5f3ee] px-4 py-2 text-sm outline-none transition focus:border-[#1a3d2e] focus:bg-white"
            />
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
              <h2 className="text-sm font-semibold text-[#1a3d2e]">
                {year} Rankings · {scope === "region" ? region : "Global"}
              </h2>
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
                        Rank
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        University
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        Location
                      </th>
                      <th className="w-28 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                        Agg. Score
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
                    {items.length === 0 ? (
                      <tr>
                        <td
                          colSpan={6}
                          className="py-20 text-center italic text-[#6b7068]"
                        >
                          No universities found.
                        </td>
                      </tr>
                    ) : (
                      items.map((item) => {
                        const inList = isInShortlist(item.canonicalUniversityId);
                        return (
                          <tr
                            key={`${item.canonicalUniversityId}-${item.slug}-${item.aggregatedRank}`}
                            className="border-t border-[#e0ddd8] transition hover:bg-[#f5f3ee]"
                          >
                            <td className="px-4 py-3.5 text-center font-bold text-[#1a3d2e]">
                              {formatRank(item.aggregatedRank)}
                            </td>
                            <td className="px-4 py-3.5">
                              <Link
                                href={`/universities/${item.slug}`}
                                className="font-medium text-[#1a1a1a] underline decoration-[#c0bdb8] underline-offset-2 transition hover:text-[#1a3d2e] hover:decoration-[#1a3d2e]"
                              >
                                {item.universityName}
                              </Link>
                            </td>
                            <td className="px-4 py-3.5 text-[#6b7068]">
                              {item.country}
                            </td>
                            <td className="px-4 py-3.5 text-right font-mono font-semibold text-[#1a1a1a]">
                              {formatScore(item.compositeScore)}
                            </td>
                            <td className="px-4 py-3.5 text-center">
                              <span className="inline-flex items-center rounded-full bg-[#e8f2ec] px-2.5 py-0.5 text-xs font-medium text-[#1a3d2e]">
                                {item.sourceCount}
                              </span>
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
                      key={item.canonicalUniversityId}
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

                <button
                  onClick={goToRecommendations}
                  className="mt-4 w-full rounded-full bg-[#1a3d2e] py-2.5 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
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
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#f5f3ee]">
          <div
            className="py-16"
            style={{
              background: "linear-gradient(135deg, #1a3d2e 0%, #0f2318 100%)",
            }}
          >
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
              <div className="h-6 w-24 animate-pulse rounded bg-white/20" />
              <div className="mt-3 h-10 w-80 animate-pulse rounded bg-white/20" />
              <div className="mt-3 h-5 w-96 animate-pulse rounded bg-white/10" />
            </div>
          </div>
        </main>
      }
    >
      <RankingsPageContent />
    </Suspense>
  );
}
