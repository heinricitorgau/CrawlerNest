"use client";

import Link from "next/link";
import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { fetchAppJson } from "@/lib/api";
import { formatRank, formatScore } from "@/lib/format";

type RankingItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  compositeScore: number;
  rankingYear: number;
  primarySource: string;
  sourceCount: number;
  slug: string;
};

type RankingsResponse = {
  success: boolean;
  data: {
    items: RankingItem[];
  };
  metadata?: {
    timestamp?: string;
  };
};

const DEFAULT_SOURCE = "AGGREGATED";
const DEFAULT_YEAR = 2026;
const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

function getDecisionContext(rank: number) {
  if (rank <= 50) {
    return {
      label: "Top-tier",
      tone: "bg-blue-50 text-blue-700 ring-1 ring-blue-100",
    };
  }

  if (rank <= 150) {
    return {
      label: "Target",
      tone: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
    };
  }

  return {
    label: "Safety",
    tone: "bg-gray-100 text-gray-600 ring-1 ring-gray-200",
  };
}

function parsePositiveInt(value: string | null, fallback: number) {
  if (!value) {
    return fallback;
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return fallback;
  }

  return Math.floor(parsed);
}

function buildQueryString(params: URLSearchParams) {
  const next = new URLSearchParams(params);
  return next.toString();
}

function RankingsHomeContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = parsePositiveInt(searchParams.get("page"), DEFAULT_PAGE);
  const pageSize = parsePositiveInt(
    searchParams.get("pageSize"),
    DEFAULT_PAGE_SIZE
  );
  const year = parsePositiveInt(searchParams.get("year"), DEFAULT_YEAR);
  const source = searchParams.get("source") ?? DEFAULT_SOURCE;

  const [items, setItems] = useState<RankingItem[]>([]);
  const [timestamp, setTimestamp] = useState<string | undefined>();
  const [searchTerm, setSearchTerm] = useState(searchParams.get("search") ?? "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSearchTerm(searchParams.get("search") ?? "");
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;

    async function loadRankings() {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          page: String(page),
          pageSize: String(pageSize),
          source,
          year: String(year),
        });

        const result = await fetchAppJson<RankingsResponse>(
          `/api/rankings?${params.toString()}`
        );

        if (!cancelled) {
          setItems(result.data.items ?? []);
          setTimestamp(result.metadata?.timestamp);
        }
      } catch {
        if (!cancelled) {
          setError(
            "Unable to load rankings. Please confirm the API server is running."
          );
          setItems([]);
          setTimestamp(undefined);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadRankings();

    return () => {
      cancelled = true;
    };
  }, [page, pageSize, source, year]);

  const filteredItems = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();

    if (!query) {
      return items;
    }

    return items.filter((item) => {
      return (
        item.universityName.toLowerCase().includes(query) ||
        item.country.toLowerCase().includes(query)
      );
    });
  }, [items, searchTerm]);

  const canGoPrevious = page > 1 && !loading;
  const canGoNext = items.length === pageSize && !loading;

  function updateRoute(nextValues: Record<string, string | number | null>) {
    const nextParams = new URLSearchParams(searchParams.toString());

    Object.entries(nextValues).forEach(([key, value]) => {
      if (value === null || value === "") {
        nextParams.delete(key);
      } else {
        nextParams.set(key, String(value));
      }
    });

    const query = buildQueryString(nextParams);
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  function handlePageChange(nextPage: number) {
    updateRoute({ page: nextPage });
  }

  function handlePageSizeChange(nextPageSize: number) {
    updateRoute({ pageSize: nextPageSize, page: 1 });
  }

  function handleSourceChange(nextSource: string) {
    updateRoute({ source: nextSource, page: 1 });
  }

  function handleYearChange(nextYear: string) {
    const normalizedYear = nextYear.trim();
    if (!normalizedYear) {
      return;
    }

    updateRoute({ year: normalizedYear, page: 1 });
  }

  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-4xl font-bold tracking-tight">
              Global University Rankings
            </h1>
            <p className="mt-2 text-gray-600">
              Structured university ranking data powered by CrawlerNest
            </p>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-500">
              Use rankings, score signals, and source coverage to quickly
              evaluate university strength.
            </p>
            {timestamp ? (
              <p className="mt-2 text-sm text-gray-400">
                Updated: {new Date(timestamp).toLocaleString()}
              </p>
            ) : null}
          </div>

          <Link
            href="/recommendations"
            className="inline-flex items-center rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:border-gray-300 hover:text-gray-900"
          >
            Open Recommendation Engine
          </Link>
        </header>

        <section className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <label className="flex flex-col gap-2">
                  <span className="text-sm font-medium text-gray-700">Source</span>
                  <select
                    className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                    value={source}
                    onChange={(e) => handleSourceChange(e.target.value)}
                  >
                    <option value="AGGREGATED">AGGREGATED</option>
                  </select>
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
                  <span className="text-sm font-medium text-gray-700">Search</span>
                  <input
                    className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Filter this page by university or country"
                  />
                </label>
              </div>

              <div className="rounded-2xl bg-gray-50 px-4 py-3 text-sm text-gray-600">
                <div className="font-medium text-gray-900">Page {page}</div>
                <div className="mt-1">
                  {loading
                    ? "Loading rankings..."
                    : `Showing ${filteredItems.length} of ${items.length} rows on this page`}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-100 pt-4">
              <p className="text-sm text-gray-500">
                Browse global rankings and open detail profiles.
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handlePageChange(page - 1)}
                  disabled={!canGoPrevious}
                  className="rounded-full border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-300 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-500">Page {page}</span>
                <button
                  type="button"
                  onClick={() => handlePageChange(page + 1)}
                  disabled={!canGoNext}
                  className="rounded-full border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-300 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </section>

        <div className="mt-6 overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-100 bg-white px-5 py-4 text-sm text-gray-500">
            Rankings browser
          </div>

          {error ? (
            <div className="p-6">
              <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
                {error}
              </div>
            </div>
          ) : loading && items.length === 0 ? (
            <div className="p-6">
              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 text-gray-600">
                Loading rankings...
              </div>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="p-6">
              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 text-gray-600">
                {searchTerm.trim()
                  ? "No universities on this page match the current search."
                  : "No ranking data available for this page. Try another page or page size."}
              </div>
            </div>
          ) : (
            <div className="relative">
              {loading ? (
                <div className="border-b border-blue-100 bg-blue-50 px-5 py-3 text-sm text-blue-700">
                  Updating rankings...
                </div>
              ) : null}

              <table className="w-full border-collapse">
                <thead className="sticky top-0 bg-gray-50 text-sm text-gray-600">
                  <tr>
                    <th className="px-5 py-4 text-left">Rank</th>
                    <th className="px-5 py-4 text-left">University</th>
                    <th className="px-5 py-4 text-left">Country</th>
                    <th className="px-5 py-4 text-left">Score</th>
                    <th className="px-5 py-4 text-left">Sources</th>
                  </tr>
                </thead>
                <tbody className={loading ? "opacity-70" : ""}>
                  {filteredItems.map((item) => {
                    const context = getDecisionContext(item.aggregatedRank);

                    return (
                      <tr
                        key={item.canonicalUniversityId}
                        className="group cursor-pointer border-t border-gray-100 transition hover:bg-blue-50/60"
                      >
                        <td className="px-5 py-5 align-top font-semibold">
                          <Link
                            href={`/universities/${item.slug}`}
                            className="block"
                            aria-label={`View details for ${item.universityName}`}
                          >
                            #{formatRank(item.aggregatedRank)}
                          </Link>
                        </td>

                        <td className="px-5 py-5 align-top">
                          <Link
                            href={`/universities/${item.slug}`}
                            className="block"
                          >
                            <div className="font-medium text-gray-900 underline-offset-4 transition group-hover:text-blue-700 group-hover:underline">
                              {item.universityName}
                            </div>
                            <div className="mt-1 text-sm text-gray-400">
                              /universities/{item.slug}
                            </div>
                            <div className="mt-2 text-xs font-medium tracking-wide text-blue-600">
                              Click to view details
                            </div>
                          </Link>
                        </td>

                        <td className="px-5 py-5 align-top text-gray-700">
                          <Link
                            href={`/universities/${item.slug}`}
                            className="block"
                            aria-hidden="true"
                            tabIndex={-1}
                          >
                            {item.country}
                          </Link>
                        </td>

                        <td className="px-5 py-5 align-top text-gray-700">
                          <Link
                            href={`/universities/${item.slug}`}
                            className="block"
                            aria-hidden="true"
                            tabIndex={-1}
                          >
                            <div className="font-medium">
                              {formatScore(item.compositeScore)}
                            </div>
                            <span
                              className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-[11px] font-medium ${context.tone}`}
                            >
                              {context.label}
                            </span>
                          </Link>
                        </td>

                        <td className="px-5 py-5 align-top text-gray-500">
                          <Link
                            href={`/universities/${item.slug}`}
                            className="block"
                            aria-hidden="true"
                            tabIndex={-1}
                          >
                            {item.sourceCount}
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-white text-gray-900">
          <div className="mx-auto max-w-6xl px-6 py-10">
            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 text-gray-600">
              Loading rankings browser...
            </div>
          </div>
        </main>
      }
    >
      <RankingsHomeContent />
    </Suspense>
  );
}
