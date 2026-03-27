"use client";

import Link from "next/link";
import {
  usePathname,
  useRouter,
  useSearchParams,
} from "next/navigation";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  Suspense,
  useEffect,
  useMemo,
  useState,
} from "react";

import { fetchAppJson } from "@/lib/api";
import { formatRank, formatScore } from "@/lib/format";

type RankingItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  globalRank?: number | null;
  scopeRank?: number | null;
  compositeScore: number;
  rankingYear: number;
  primarySource: string;
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
const DEFAULT_SCOPE = "global";
const DEFAULT_REGION = "Europe";
const PAGE_SIZE_OPTIONS = [20, 50, 100];
const REGION_OPTIONS = [
  "Europe",
  "Asia",
  "North America",
  "Latin America",
  "Oceania",
  "Africa",
];
const SHORTLIST_STORAGE_KEY = "crawlernest_shortlist";

function getDecisionContext(rank: number) {
  if (rank <= 50) {
    return {
      label: "Top-tier",
      caption: "Strong global position",
      tone: "bg-blue-100 text-blue-800 ring-1 ring-blue-200",
    };
  }

  if (rank <= 150) {
    return {
      label: "Target",
      caption: "Balanced shortlist fit",
      tone: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
    };
  }

  return {
    label: "Safety",
    caption: "More accessible option",
    tone: "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
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

function parseScope(value: string | null) {
  return value === "region" ? "region" : DEFAULT_SCOPE;
}

function parseRegion(value: string | null) {
  if (!value) {
    return DEFAULT_REGION;
  }

  return REGION_OPTIONS.includes(value) ? value : DEFAULT_REGION;
}

function buildQueryString(params: URLSearchParams) {
  const next = new URLSearchParams(params);
  return next.toString();
}

function toShortlistItem(item: RankingItem): ShortlistItem {
  return {
    canonicalUniversityId: item.canonicalUniversityId,
    universityName: item.universityName,
    country: item.country,
    aggregatedRank: item.aggregatedRank,
    slug: item.slug,
  };
}

function LoadingSkeleton() {
  return (
    <div className="p-6">
      <div className="animate-pulse space-y-4">
        <div className="h-12 rounded-2xl bg-gray-100" />
        <div className="h-20 rounded-2xl bg-gray-50" />
        <div className="h-20 rounded-2xl bg-gray-50" />
        <div className="h-20 rounded-2xl bg-gray-50" />
      </div>
    </div>
  );
}

function RankingsShell({ message }: Readonly<{ message: string }>) {
  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 text-gray-600">
          {message}
        </div>
      </div>
    </main>
  );
}

function ShortlistPanel({
  shortlist,
  onRemove,
  page,
  canGoPrevious,
  canGoNext,
  onPreviousPage,
  onNextPage,
}: Readonly<{
  shortlist: ShortlistItem[];
  onRemove: (id: number) => void;
  page: number;
  canGoPrevious: boolean;
  canGoNext: boolean;
  onPreviousPage: () => void;
  onNextPage: () => void;
}>) {
  return (
    <div className="space-y-4">
      <section className="rounded-[1.75rem] border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Your Shortlist</h2>
            <p className="mt-1 text-sm text-gray-500">
              {shortlist.length} selected {shortlist.length === 1 ? "university" : "universities"}
            </p>
          </div>
          <div className="rounded-full bg-gray-100 px-3 py-1 text-sm font-semibold text-gray-700">
            {shortlist.length}
          </div>
        </div>

        {shortlist.length === 0 ? (
          <div className="mt-4 rounded-2xl bg-gray-50 p-4 text-sm text-gray-600">
            Add universities from the rankings table to build a shortlist before generating recommendations.
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <Link
              href="/recommendations"
              className="inline-flex w-full items-center justify-center rounded-xl bg-gray-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-gray-800"
            >
              Generate Recommendation
            </Link>

            {shortlist.length >= 2 ? (
              <Link
                href="/recommendations#comparison"
                className="inline-flex w-full items-center justify-center rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm font-semibold text-gray-700 transition hover:border-gray-300 hover:text-gray-900"
              >
                Compare Selected
              </Link>
            ) : null}

            <div className="space-y-3">
              {shortlist.map((item) => (
                <div
                  key={item.canonicalUniversityId}
                  className="rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={`/universities/${item.slug}`}
                        className="block text-sm font-semibold text-gray-900 underline-offset-4 transition hover:text-blue-700 hover:underline"
                      >
                        {item.universityName}
                      </Link>
                      <div className="mt-1 text-sm text-gray-500">
                        {item.country}
                      </div>
                      <div className="mt-2 text-xs font-medium tracking-wide text-gray-400">
                        Rank #{formatRank(item.aggregatedRank)}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemove(item.canonicalUniversityId)}
                      className="shrink-0 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:border-gray-300 hover:text-gray-900"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="rounded-[1.75rem] border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Page Control</h2>
            <p className="mt-1 text-sm text-gray-500">
              Navigate the rankings browser from here while you review your shortlist.
            </p>
          </div>
          <div className="rounded-full bg-gray-100 px-3 py-1 text-sm font-semibold text-gray-700">
            Page {page}
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            onClick={onPreviousPage}
            disabled={!canGoPrevious}
            className="flex-1 rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-300 hover:text-gray-900 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={onNextPage}
            disabled={!canGoNext}
            className="flex-1 rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-300 hover:text-gray-900 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
          >
            Next
          </button>
        </div>
      </section>
    </div>
  );
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
  const search = searchParams.get("search") ?? "";
  const scope = parseScope(searchParams.get("scope"));
  const region = parseRegion(searchParams.get("region"));

  const [items, setItems] = useState<RankingItem[]>([]);
  const [timestamp, setTimestamp] = useState<string | undefined>();
  const [searchInput, setSearchInput] = useState(search);
  const [isMounted, setIsMounted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    setSearchInput(search);
  }, [search]);

  useEffect(() => {
    if (!isMounted) {
      return;
    }

    try {
      const storedValue = window.localStorage.getItem(SHORTLIST_STORAGE_KEY);
      if (!storedValue) {
        setShortlist([]);
        return;
      }

      const parsedValue = JSON.parse(storedValue);
      if (!Array.isArray(parsedValue)) {
        setShortlist([]);
        return;
      }

      setShortlist(
        parsedValue.filter((item): item is ShortlistItem => {
          return (
            typeof item?.canonicalUniversityId === "number" &&
            typeof item?.universityName === "string" &&
            typeof item?.country === "string" &&
            typeof item?.aggregatedRank === "number" &&
            typeof item?.slug === "string"
          );
        })
      );
    } catch {
      setShortlist([]);
    }
  }, [isMounted]);

  useEffect(() => {
    if (!isMounted) {
      return;
    }

    window.localStorage.setItem(
      SHORTLIST_STORAGE_KEY,
      JSON.stringify(shortlist)
    );
  }, [isMounted, shortlist]);

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
          scope,
        });

        if (scope === "region") {
          params.set("region", region);
        }

        if (search.trim()) {
          params.set("search", search.trim());
        }

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
            "Unable to load rankings. Please check backend or try again."
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
  }, [page, pageSize, source, year, scope, region, search]);

  const shortlistIds = useMemo(
    () => new Set(shortlist.map((item) => item.canonicalUniversityId)),
    [shortlist]
  );

  const pageRowRangeLabel = useMemo(() => {
    const startRow = (page - 1) * pageSize + 1;
    const endRow = page * pageSize;

    return `${formatRank(startRow)}-${formatRank(endRow)}`;
  }, [page, pageSize]);

  const canGoPrevious = page > 1 && !loading;
  const canGoNext = !loading && items.length === pageSize;
  const isRegionScope = scope === "region";
  const scopeLabel = isRegionScope ? `${region} Rankings` : "Global Rankings";
  const heroTitle = isRegionScope
    ? `${region} University Rankings`
    : "Global University Rankings";
  const browserDescription = isRegionScope
    ? `Browse the ${region} ranking universe, search within this region, and open detailed profiles.`
    : "Browse the aggregated ranking view, search across the active ranking universe, and refine results without leaving the browser.";

  function updateRoute(
    nextValues: Record<string, string | number | null>,
    mode: "push" | "replace" = "replace"
  ) {
    const nextParams = new URLSearchParams(searchParams.toString());

    Object.entries(nextValues).forEach(([key, value]) => {
      if (value === null || value === "") {
        nextParams.delete(key);
      } else {
        nextParams.set(key, String(value));
      }
    });

    const query = buildQueryString(nextParams);
    const nextUrl = query ? `${pathname}?${query}` : pathname;

    if (mode === "push") {
      router.push(nextUrl, { scroll: false });
      return;
    }

    router.replace(nextUrl, { scroll: false });
  }

  function handlePageChange(nextPage: number) {
    updateRoute({ page: nextPage }, "push");
  }

  function handlePageSizeChange(nextPageSize: number) {
    updateRoute({ pageSize: nextPageSize, page: 1 }, "push");
  }

  function handleScopeChange(nextScope: string) {
    updateRoute(
      {
        scope: nextScope,
        region: nextScope === "region" ? region || DEFAULT_REGION : null,
        page: 1,
      },
      "push"
    );
  }

  function handleRegionChange(nextRegion: string) {
    updateRoute({ region: nextRegion, page: 1 }, "push");
  }

  function handleYearChange(nextYear: string) {
    const normalizedYear = nextYear.trim();
    if (!normalizedYear) {
      return;
    }

    updateRoute({ year: normalizedYear, page: 1 }, "push");
  }

  function handleSearchChange(value: string) {
    setSearchInput(value);
    updateRoute({ search: value || null, page: 1 });
  }

  function handleRetry() {
    router.refresh();
  }

  function handleRowClick(
    event: ReactMouseEvent<HTMLTableRowElement>,
    slug: string
  ) {
    const target = event.target as HTMLElement;
    if (target.closest("a, button, input, select")) {
      return;
    }

    router.push(`/universities/${slug}`);
  }

  function handleRowKeyDown(
    event: ReactKeyboardEvent<HTMLTableRowElement>,
    slug: string
  ) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      router.push(`/universities/${slug}`);
    }
  }

  function toggleShortlist(item: RankingItem) {
    setShortlist((currentShortlist) => {
      const exists = currentShortlist.some(
        (shortlisted) =>
          shortlisted.canonicalUniversityId === item.canonicalUniversityId
      );

      if (exists) {
        return currentShortlist.filter(
          (shortlisted) =>
            shortlisted.canonicalUniversityId !== item.canonicalUniversityId
        );
      }

      return [...currentShortlist, toShortlistItem(item)];
    });
  }

  function removeFromShortlist(id: number) {
    setShortlist((currentShortlist) =>
      currentShortlist.filter(
        (shortlisted) => shortlisted.canonicalUniversityId !== id
      )
    );
  }

  if (!isMounted) {
    return <RankingsShell message="Loading rankings browser..." />;
  }

  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8 rounded-[2rem] border border-gray-200 bg-gray-50/70 p-8 shadow-sm">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500">
                Rankings Browser
              </p>
              <h1 className="mt-3 text-4xl font-bold tracking-tight">
                {heroTitle}
              </h1>
              <p className="mt-3 text-gray-600">
                Structured university ranking data powered by CrawlerNest
              </p>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-500">
                {isRegionScope
                  ? `Use ${region.toLowerCase()} rankings, score signals, and source coverage to compare universities inside this region.`
                  : "Use rankings, score signals, and source coverage to quickly evaluate university strength, shortlist promising options, and open deeper decision context for each university."}
              </p>
              {isRegionScope ? (
                <p className="mt-2 text-sm text-gray-400">
                  Browsing universities ranked within {region}.
                </p>
              ) : null}
              {timestamp ? (
                <p className="mt-4 text-sm text-gray-400">
                  Updated: {new Date(timestamp).toLocaleString()}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-3 lg:items-end">
              {shortlist.length > 0 ? (
                <Link
                  href="/recommendations"
                  className="inline-flex items-center justify-center rounded-full bg-gray-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-gray-800"
                >
                  Generate Recommendation based on your shortlist
                </Link>
              ) : (
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center justify-center rounded-full bg-gray-300 px-5 py-3 text-sm font-semibold text-white"
                >
                  Generate Recommendation based on your shortlist
                </button>
              )}
              <p className="text-sm text-gray-500">
                {shortlist.length > 0
                  ? "Move from browsing into a shortlist-driven recommendation flow."
                  : "Add universities to your shortlist to unlock recommendation flow."}
              </p>
            </div>
          </div>
        </header>

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
            />
          </div>
        </div>
      </div>
    </main>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<RankingsShell message="Loading rankings browser..." />}>
      <RankingsHomeContent />
    </Suspense>
  );
}
