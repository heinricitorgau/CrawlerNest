"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { formatRank, formatScore } from "@/lib/format";
import ErrorBanner from "@/components/ErrorBanner";

// ─── Constants ───
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

// ─── Types ───
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

// ─── Inner Component (needs useSearchParams → must be inside Suspense) ───
function RankingsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // URL-synced state (read-only; mutations go through navigate())
  const scope = (searchParams.get("scope") as "global" | "region") ?? "global";
  const region = searchParams.get("region") ?? "Europe";
  const year = Number(searchParams.get("year") ?? "2026");
  const page = Number(searchParams.get("page") ?? "1");
  const searchQuery = searchParams.get("search") ?? "";

  // Local UI state
  const [searchInput, setSearchInput] = useState(searchQuery);
  const [items, setItems] = useState<RankingItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Shortlist
  const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);

  useEffect(() => {
    setSearchInput(searchQuery);
  }, [searchQuery]);

  // ─── URL navigation helper ───
  // Keep a stable ref so debounce effect can call latest navigate without
  // having navigate itself as a dependency (avoids re-trigger loop).
  const navigateRef = useRef<(updates: Record<string, string | number | null>) => void>(
    () => undefined
  );

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

  // Keep ref in sync
  useEffect(() => {
    navigateRef.current = navigate;
  }, [navigate]);

  // ─── Debounce search: auto-trigger after 400 ms of inactivity ───
  useEffect(() => {
    if (searchInput === searchQuery) return;
    const timer = setTimeout(() => {
      navigateRef.current({ search: searchInput || null, page: 1 });
    }, 400);
    return () => clearTimeout(timer);
  }, [searchInput, searchQuery]);

  // ─── Load shortlist from localStorage on mount ───
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SHORTLIST_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) setShortlist(parsed);
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  // ─── Persist shortlist to localStorage ───
  useEffect(() => {
    try {
      localStorage.setItem(SHORTLIST_STORAGE_KEY, JSON.stringify(shortlist));
    } catch {
      // ignore
    }
  }, [shortlist]);

  // ─── Polling ───
  useEffect(() => {
    const id = setInterval(() => {
      setRefreshTrigger((n) => n + 1);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  // ─── Visibility / focus / online refresh ───
  useEffect(() => {
    const bump = () => setRefreshTrigger((n) => n + 1);
    window.addEventListener("focus", bump);
    document.addEventListener("visibilitychange", bump);
    window.addEventListener("online", bump);
    return () => {
      window.removeEventListener("focus", bump);
      document.removeEventListener("visibilitychange", bump);
      window.removeEventListener("online", bump);
    };
  }, []);

  // ─── Data fetching ───
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
          signal: controller.signal,
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();

        if (isMounted) {
          setItems(payload?.data?.items ?? []);
          setTotalCount(payload?.metadata?.totalCount ?? 0);
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        if (isMounted) {
          setError("Failed to load rankings. Please retry.");
          setItems([]);
          setTotalCount(0);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    fetchRankings();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [page, year, scope, region, searchQuery, refreshTrigger]);

  // ─── Shortlist helpers ───
  const isInShortlist = (id: number) =>
    shortlist.some((s) => s.canonicalUniversityId === id);

  const toggleShortlist = (item: RankingItem) => {
    setShortlist((prev) =>
      isInShortlist(item.canonicalUniversityId)
        ? prev.filter((s) => s.canonicalUniversityId !== item.canonicalUniversityId)
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

  // ─── Pagination ───
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const canGoPrevious = page > 1;
  const canGoNext = page < totalPages;

  return (
    <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
      {/* ── Hero ── */}
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

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {countSummaries.map((summary) => (
              <div
                key={`${summary.scope}-${summary.region ?? "global"}`}
                className="rounded-2xl border border-gray-200 bg-white/80 px-4 py-3"
              >
                <div className="text-xs font-medium uppercase tracking-[0.18em] text-gray-400">
                  {summary.label}
                </div>
                <div className="mt-2 text-2xl font-bold tracking-tight text-gray-900">
                  {summary.totalCount === null ? "..." : formatRank(summary.totalCount)}
                </div>
                <div className="mt-1 text-sm text-gray-500">
                  ranking rows in {year}
                </div>
              </div>
            ))}
          </div>
        </header>

        {error ? (
          <div className="mb-6">
            <ErrorBanner message={error} onDismiss={() => setError(null)} />
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <section className="rounded-[2rem] border border-gray-200 bg-white p-6 shadow-sm">
              <div className="flex flex-col gap-5">
                <div className="flex flex-col gap-2">
                  <h2 className="text-lg font-semibold text-gray-900">
                    Explore Rankings
                  </h2>
                  <p className="text-sm text-gray-500">
                    {browserDescription}
                  </p>
                </div>

                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-gray-700">
                        Scope
                      </span>
                      <select
                        className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                        value={scope}
                        onChange={(e) => handleScopeChange(e.target.value)}
                      >
                        <option value="global">Global</option>
                        <option value="region">Region</option>
                      </select>
                    </label>

                    {isRegionScope ? (
                      <label className="flex flex-col gap-2">
                        <span className="text-sm font-medium text-gray-700">
                          Region
                        </span>
                        <select
                          className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                          value={region}
                          onChange={(e) => handleRegionChange(e.target.value)}
                        >
                          {REGION_OPTIONS.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}

                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-gray-700">
                        Source
                      </span>
                      <div className="relative">
                        <select
                          className="w-full rounded-xl border border-gray-300 bg-gray-50 px-4 py-3 text-gray-600 outline-none"
                          value={source}
                          disabled
                        >
                          <option value="AGGREGATED">AGGREGATED</option>
                        </select>
                        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-blue-100 px-2.5 py-1 text-[11px] font-semibold text-blue-700">
                          Locked
                        </span>
                      </div>
                    </label>

                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-gray-700">Year</span>
                      <input
                        className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                        type="number"
                        value={year}
                        onChange={(e) => handleYearChange(e.target.value)}
                      />
                    </label>

                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-gray-700">
                        Page Size
                      </span>
                      <select
                        className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                        value={pageSize}
                        onChange={(e) =>
                          handlePageSizeChange(Number(e.target.value))
                        }
                      >
                        {PAGE_SIZE_OPTIONS.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-gray-700">
                        Search
                      </span>
                      <div className="flex items-center gap-2 rounded-xl border border-gray-300 px-3 py-2 focus-within:border-gray-900">
                        <input
                          className="w-full border-0 bg-transparent px-1 py-1.5 outline-none"
                          value={searchInput}
                          onChange={(e) => handleSearchChange(e.target.value)}
                          placeholder="Search university or country"
                        />
                        {searchInput ? (
                          <button
                            type="button"
                            onClick={() => handleSearchChange("")}
                            className="rounded-full px-2 py-1 text-xs font-medium text-gray-500 transition hover:bg-gray-100 hover:text-gray-800"
                          >
                            ×
                          </button>
                        ) : null}
                      </div>
                    </label>
                  </div>

                    <div className="rounded-2xl bg-gray-50 px-4 py-4">
                      <div className="text-sm font-medium text-gray-900">
                        {scopeLabel}
                      </div>
                    <div className="mt-2 text-sm leading-6 text-gray-500">
                      {loading ? "Loading rankings..." : null}
                      {!loading && items.length > 0 ? (
                        <span>Rows {pageRowRangeLabel}</span>
                      ) : null}
                      {!loading && items.length === 0 ? (
                        <span>No rankings loaded</span>
                      ) : null}
                    </div>
                    {!loading && search.trim() ? (
                      <div className="mt-2 text-sm leading-6 text-gray-500">
                        Showing {items.length} matching results on this page
                      </div>
                    ) : null}
                    <div className="mt-3 text-xs uppercase tracking-[0.18em] text-gray-400">
                      {isRegionScope ? `${region} product view` : "Aggregated product view"}
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-100 pt-4">
                  <p className="text-sm text-gray-500">
                    {isRegionScope
                      ? `Browse ${region.toLowerCase()} rankings, shortlist strong regional options, then move into recommendation.`
                      : "Browse, shortlist, compare mentally, then move into recommendation."}
                  </p>
                </div>
              </div>
            </section>

            <section className="overflow-hidden rounded-[2rem] border border-gray-200 bg-white shadow-sm">
              <div className="flex flex-col gap-2 border-b border-gray-100 bg-white px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    {scopeLabel}
                  </h2>
                  <p className="mt-1 text-sm text-gray-500">
                    {isRegionScope
                      ? `Scan regional rank first, then use global position and score to compare universities inside ${region}.`
                      : "Scan rank, score, shortlist signal, and add strong candidates as you browse."}
                  </p>
                </div>
                <div className="text-sm text-gray-400">
                  Click any row to view details
                </div>
              </div>

              {error ? (
                <div className="p-6">
                  <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">
                    <div className="font-medium">Unable to load rankings.</div>
                    <div className="mt-1 text-sm text-red-600">
                      Please check backend or try again.
                    </div>
                    <button
                      type="button"
                      onClick={handleRetry}
                      className="mt-4 rounded-full border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100"
                    >
                      Retry
                    </button>
                  </div>
                </div>
              ) : loading && items.length === 0 ? (
                <LoadingSkeleton />
              ) : items.length === 0 ? (
                <div className="p-6">
                  <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 text-gray-600">
                    {search.trim()
                      ? "No rankings match your search."
                      : isRegionScope
                      ? "No rankings available for this region."
                      : "No rankings found."}
                    <div className="mt-1 text-sm text-gray-500">
                      Try adjusting filters or search.
                    </div>
                  </div>
                </div>
              ) : (
                <div className="relative">
                  {loading ? (
                    <div className="border-b border-blue-100 bg-blue-50 px-6 py-3 text-sm text-blue-700">
                      Loading rankings...
                    </div>
                  ) : null}

                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse">
                      <thead className="sticky top-0 bg-gray-50 text-sm text-gray-600">
                        <tr>
                          <th className="px-6 py-4 text-left">Rank</th>
                          <th className="px-6 py-4 text-left">University</th>
                          <th className="px-6 py-4 text-left">Score</th>
                          <th className="px-6 py-4 text-left">Source Coverage</th>
                          <th className="px-6 py-4 text-left">Selection</th>
                        </tr>
                      </thead>
                      <tbody className={loading ? "opacity-70" : ""}>
                        {items.map((item, index) => {
                          const displayRank = item.scopeRank ?? item.aggregatedRank;
                          const globalRank = item.globalRank ?? item.aggregatedRank;
                          const context = getDecisionContext(displayRank);
                          const isShortlisted = shortlistIds.has(
                            item.canonicalUniversityId
                          );
                          const rowKey = [
                            item.canonicalUniversityId,
                            item.slug,
                            displayRank,
                            globalRank,
                            index,
                          ].join("-");

                          return (
                            <tr
                              key={rowKey}
                              tabIndex={0}
                              role="link"
                              onClick={(event) => handleRowClick(event, item.slug)}
                              onKeyDown={(event) =>
                                handleRowKeyDown(event, item.slug)
                              }
                              className={`group cursor-pointer border-t border-gray-100 transition hover:bg-blue-50/60 focus-visible:bg-blue-50/60 focus-visible:outline-none ${
                                isShortlisted ? "bg-amber-50/70" : ""
                              }`}
                            >
                              <td className="px-6 py-5 align-top">
                                <div className="text-2xl font-bold tracking-tight text-gray-900">
                                  #{formatRank(displayRank)}
                                </div>
                                {isRegionScope && globalRank !== displayRank ? (
                                  <div className="mt-2 text-xs font-medium tracking-wide text-gray-400">
                                    Global #{formatRank(globalRank)}
                                  </div>
                                ) : null}
                                <div className="mt-2">
                                  <span
                                    className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ${context.tone}`}
                                  >
                                    {context.label}
                                  </span>
                                </div>
                              </td>

                              <td className="px-6 py-5 align-top">
                                <Link
                                  href={`/universities/${item.slug}`}
                                  className="block"
                                >
                                  <div className="text-base font-semibold text-gray-900 underline-offset-4 transition group-hover:text-blue-700 group-hover:underline">
                                    {item.universityName}
                                  </div>
                                  <div className="mt-1 text-sm text-gray-500">
                                    {item.country}
                                  </div>
                                  <div className="mt-3 text-xs font-medium tracking-wide text-blue-600">
                                    Click to view details
                                  </div>
                                </Link>
                              </td>

                              <td className="px-6 py-5 align-top">
                                <div className="text-base font-semibold text-gray-900">
                                  {formatScore(item.compositeScore)}
                                </div>
                                <div className="mt-2 text-sm text-gray-500">
                                  {isRegionScope
                                    ? `${context.caption} · Global #${formatRank(globalRank)}`
                                    : context.caption}
                                </div>
                              </td>

                              <td className="px-6 py-5 align-top">
                                <div className="text-base font-medium text-gray-900">
                                  {item.sourceCount}
                                </div>
                                <div className="mt-2 text-sm text-gray-500">
                                  ranking sources included
                                </div>
                              </td>

                              <td className="px-6 py-5 align-top">
                                <button
                                  type="button"
                                  onClick={() => toggleShortlist(item)}
                                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                                    isShortlisted
                                      ? "border border-amber-300 bg-amber-100 text-amber-800"
                                      : "border border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:text-gray-900"
                                  }`}
                                >
                                  {isShortlisted ? "Added" : "+ Shortlist"}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </section>
          </div>

          <div className="xl:sticky xl:top-6 xl:self-start">
            <ShortlistPanel
              shortlist={shortlist}
              onRemove={removeFromShortlist}
              page={page}
              canGoPrevious={canGoPrevious}
              canGoNext={canGoNext}
              onPreviousPage={() => handlePageChange(page - 1)}
              onNextPage={() => handlePageChange(page + 1)}
>>>>>>> claude/wizardly-johnson
            />
          </div>
          <div className="hidden text-sm text-[#6b7068] sm:block">
            {loading ? (
              <span className="animate-pulse">Loading…</span>
            ) : (
              <span>
                <span className="font-semibold text-[#1a1a1a]">{totalCount.toLocaleString()}</span>{" "}
                universities
              </span>
            )}
          </div>
        </div>
      </div>

      {/* ── Main layout ── */}
      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
        <div className="flex gap-6">
          {/* ── Filter sidebar ── */}
          <aside className="w-52 flex-shrink-0">
            <div className="rounded-2xl border border-[#e0ddd8] bg-white p-5 shadow-sm">
              <h3 className="mb-4 text-xs font-bold uppercase tracking-[0.15em] text-[#6b7068]">
                Filters
              </h3>

              {/* Year */}
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

              {/* Scope toggle */}
              <div className="mb-5">
                <label className="mb-1.5 block text-xs font-semibold text-[#1a3d2e]">
                  Scope
                </label>
                <div className="flex overflow-hidden rounded-lg border border-[#e0ddd8]">
                  {(["global", "region"] as const).map((s) => (
                    <button
                      key={s}
                      onClick={() => navigate({ scope: s, page: 1 })}
                      className={`flex-1 py-2 text-xs font-semibold capitalize transition ${
                        scope === s
                          ? "bg-[#1a3d2e] text-white"
                          : "bg-white text-[#6b7068] hover:bg-[#f5f3ee]"
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              {/* Region (visible only when scope=region) */}
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
                    {REGION_OPTIONS.map((r) => (
                      <option key={r} value={r}>
                        {r}
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

          {/* ── Table + pagination ── */}
          <div className="min-w-0 flex-1">
            {/* Sub-header */}
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-[#1a3d2e]">
                {year} Rankings ·{" "}
                {scope === "region" ? region : "Global"}
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

            {/* Error banner */}
            {error && (
              <div className="mb-4 flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <span>{error}</span>
                <button
                  onClick={() => setRefreshTrigger((n) => n + 1)}
                  className="ml-4 font-semibold underline"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Table */}
            <div className="overflow-x-auto rounded-2xl border border-[#e0ddd8] bg-white shadow-sm">
              {loading ? (
                <div className="divide-y divide-[#e0ddd8]">
                  {Array.from({ length: 10 }).map((_, i) => (
                    <div key={i} className="flex h-14 items-center gap-4 px-4">
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

            {/* Pagination */}
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

          {/* ── Shortlist panel ── */}
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
                              (s) =>
                                s.canonicalUniversityId !==
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

// ─── Page export: wraps in Suspense (required by useSearchParams) ───
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
