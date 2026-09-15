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
  useEffect,
  useMemo,
  useState,
} from "react";

import { CaveatBanner } from "@/components/CaveatBanner";
import { YearSelector } from "@/components/YearSelector";
import { editionCaveats } from "@/lib/caveatMessages";
import { YEAR_QUERY_PARAM, hrefForEdition, resolveSelectedYear } from "@/lib/datasetScope";
import { formatRank, formatScore } from "@/lib/format";
import { countryBelongsToRegion, normalizeCountryName } from "@/lib/regionMap";
import { useAuth } from "@/hooks/useAuthPlaceholder";
import { useSavedUniversities } from "@/hooks/useSavedUniversities";
import { AUTH_MESSAGES } from "@/lib/authMessages";

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
    metadata?: {
      timestamp?: string;
      totalCount?: number;
      page?: number;
      pageSize?: number;
    };
  };
};

type RankingsState = {
  items: RankingItem[];
  totalCount: number;
  loading: boolean;
  error: string | null;
  timestamp?: string;
};

type RankingCountSummary = {
  label: string;
  scope: "global" | "region";
  region?: string;
  totalCount: number;
};

function normalizeRankingsResponse(payload: unknown): RankingsResponse["data"] {
  const result = payload as Partial<RankingsResponse>;

  if (!result?.success || !result.data) {
    throw new Error("Rankings API request failed.");
  }

  return {
    items: Array.isArray(result.data.items) ? result.data.items : [],
    metadata:
      result.data.metadata && typeof result.data.metadata === "object"
        ? result.data.metadata
        : {},
  };
}

function isAbortLikeError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === "AbortError") {
    return true;
  }

  if (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    (error as { name?: string }).name === "AbortError"
  ) {
    return true;
  }

  return false;
}

const DEFAULT_SOURCE = "AGGREGATED";
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
const COUNT_SUMMARY_GROUPS: Array<{
  label: string;
  scope: "global" | "region";
  region?: string;
}> = [
  { label: "Global", scope: "global" },
  { label: "Europe", scope: "region", region: "Europe" },
  { label: "Asia", scope: "region", region: "Asia" },
  { label: "North America", scope: "region", region: "North America" },
  { label: "Latin America", scope: "region", region: "Latin America" },
  { label: "Oceania", scope: "region", region: "Oceania" },
  { label: "Africa", scope: "region", region: "Africa" },
];

function pluralize(value: number, singular: string, plural: string) {
  return value === 1 ? singular : plural;
}

function formatUpdatedTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-CA", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Taipei",
  }).format(new Date(value));
}

function getDecisionContext(rank: number) {
  if (rank <= 50) {
    return {
      label: "Top-tier",
      caption: "Strong global position",
      tone: "bg-[#e8f2ec] text-[#1a3d2e] ring-1 ring-[#3d7a5a]",
    };
  }

  if (rank <= 150) {
    return {
      label: "Target",
      caption: "Balanced shortlist fit",
      tone: "bg-[#f0f7f3] text-[#2a5a42] ring-1 ring-[#6aaa88]",
    };
  }

  return {
    label: "Safety",
    caption: "More accessible option",
    tone: "bg-[#f5f3ee] text-[#6b7068] ring-1 ring-[#c0bdb8]",
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
        <div className="h-12 rounded-2xl bg-[#e0ddd8]" />
        <div className="h-20 rounded-2xl bg-[#f5f3ee]" />
        <div className="h-20 rounded-2xl bg-[#f5f3ee]" />
        <div className="h-20 rounded-2xl bg-[#f5f3ee]" />
      </div>
    </div>
  );
}

export function RankingsShell({ message }: Readonly<{ message: string }>) {
  return (
    <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="rounded-2xl border border-[#e0ddd8] bg-white p-6 text-[#6b7068]">
          {message}
        </div>
      </div>
    </main>
  );
}

function RankingsSummary({
  year,
  summaries,
}: Readonly<{
  year: number;
  summaries: RankingCountSummary[];
}>) {
  return (
    <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {summaries.map((summary) => (
        <div
          key={`${summary.scope}-${summary.region ?? "global"}`}
          className="rounded-[1.5rem] border border-[#e0ddd8] bg-gradient-to-br from-white to-[#f8f6f1] px-5 py-4 shadow-sm"
        >
          <div className="text-xs font-medium uppercase tracking-[0.18em] text-[#6b7068]">
            {summary.label}
          </div>
          <div className="mt-3 text-3xl font-bold tracking-tight text-[#16382a]">
            {formatRank(summary.totalCount)}
          </div>
          <div className="mt-1 text-sm text-[#6b7068]">
            {pluralize(summary.totalCount, "university", "universities")} in {year}
          </div>
        </div>
      ))}
    </div>
  );
}

function RankingsTable({
  error,
  loading,
  pagedItems,
  shortlistIds,
  savedIds,
  isRegionScope,
  search,
  region,
  onRetry,
  onRowClick,
  onRowKeyDown,
  onToggleShortlist,
  onToggleSave,
  universityHref,
}: Readonly<{
  error: string | null;
  loading: boolean;
  pagedItems: RankingItem[];
  shortlistIds: Set<number>;
  savedIds: Set<number>;
  isRegionScope: boolean;
  search: string;
  region: string;
  onRetry: () => void;
  onRowClick: (event: ReactMouseEvent<HTMLTableRowElement>, slug: string) => void;
  onRowKeyDown: (event: ReactKeyboardEvent<HTMLTableRowElement>, slug: string) => void;
  onToggleShortlist: (item: RankingItem) => void;
  onToggleSave: (item: RankingItem) => void;
  /** The university page for the edition this table shows. */
  universityHref: (slug: string) => string;
}>) {
  if (pagedItems.length > 0) {
    return (
      <div className="relative">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead className="sticky top-0 bg-[#f5f3ee] text-sm text-[#6b7068]">
              <tr>
                <th className="px-6 py-4 text-left">Rank</th>
                <th className="px-6 py-4 text-left">University</th>
                <th className="px-6 py-4 text-left">Score</th>
                <th className="px-6 py-4 text-left">Source Coverage</th>
                <th className="px-6 py-4 text-left">Selection</th>
              </tr>
            </thead>
            <tbody>
              {pagedItems.map((item, index) => {
                const displayRank = item.scopeRank ?? item.aggregatedRank;
                const globalRank = item.globalRank ?? item.aggregatedRank;
                const context = getDecisionContext(displayRank);
                const isShortlisted = shortlistIds.has(item.canonicalUniversityId);
                const isSaved = savedIds.has(item.canonicalUniversityId);
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
                    onClick={(event) => onRowClick(event, item.slug)}
                    onKeyDown={(event) => onRowKeyDown(event, item.slug)}
                    className={`group cursor-pointer border-t border-[#e0ddd8] transition hover:bg-[#f0f5f1] focus-visible:bg-[#f0f5f1] focus-visible:outline-none ${
                      isShortlisted ? "bg-[#e8f2ec]" : ""
                    }`}
                  >
                    <td className="px-6 py-5 align-top">
                      <div className="text-3xl font-bold tracking-tight text-[#16382a]">
                        #{formatRank(displayRank)}
                      </div>
                      {isRegionScope && globalRank !== displayRank ? (
                        <div className="mt-2 text-xs font-medium tracking-wide text-[#6b7068]">
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
                      <Link href={universityHref(item.slug)} className="block">
                        <div className="text-lg font-semibold text-[#1a1a1a] underline-offset-4 transition group-hover:text-[#1a3d2e] group-hover:underline">
                          {item.universityName}
                        </div>
                        <div className="mt-1 text-sm text-[#6b7068]">
                          {item.country}
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-medium tracking-wide text-[#3d7a5a]">
                          <span className="rounded-full bg-[#e8f2ec] px-2.5 py-1">
                            {item.primarySource}
                          </span>
                          <span className="rounded-full bg-[#f5f3ee] px-2.5 py-1 text-[#6b7068]">
                            {item.rankingYear}
                          </span>
                        </div>
                      </Link>
                    </td>

                    <td className="px-6 py-5 align-top">
                      <div className="text-base font-semibold text-[#1a1a1a]">
                        {formatScore(item.compositeScore)}
                      </div>
                      <div className="mt-2 text-sm text-[#6b7068]">
                        {isRegionScope
                          ? `${context.caption} · Global #${formatRank(globalRank)}`
                          : context.caption}
                      </div>
                    </td>

                    <td className="px-6 py-5 align-top">
                      <div className="text-base font-medium text-[#1a1a1a]">
                        {item.sourceCount}
                      </div>
                      <div className="mt-2 text-sm text-[#6b7068]">
                        ranking {pluralize(item.sourceCount, "source", "sources")}
                      </div>
                    </td>

                    <td className="px-6 py-5 align-top">
                      <div className="flex flex-col gap-2">
                        <button
                          type="button"
                          onClick={() => onToggleShortlist(item)}
                          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                            isShortlisted
                              ? "border border-[#3d7a5a] bg-[#e8f2ec] text-[#1a3d2e]"
                              : "border border-[#e0ddd8] bg-white text-[#1a3d2e] hover:border-[#3d7a5a] hover:bg-[#e8f2ec]"
                          }`}
                        >
                          {isShortlisted ? "Added" : "+ Shortlist"}
                        </button>
                        <button
                          type="button"
                          onClick={() => onToggleSave(item)}
                          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                            isSaved
                              ? "border border-[#3d7a5a] bg-[#e8f2ec] text-[#1a3d2e]"
                              : "border border-[#e0ddd8] bg-white text-[#6b7068] hover:border-[#3d7a5a] hover:bg-[#e8f2ec] hover:text-[#1a3d2e]"
                          }`}
                        >
                          {isSaved ? AUTH_MESSAGES.saved : AUTH_MESSAGES.save}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700">
          <div className="font-medium">Unable to load rankings.</div>
          <div className="mt-1 text-sm text-red-600">
            Please check backend or try again.
          </div>
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 rounded-full border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-700 transition hover:bg-red-100"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (pagedItems.length === 0) {
    return (
      <div className="p-6">
        <div className="rounded-2xl border border-[#e0ddd8] bg-white p-6 text-[#6b7068]">
          {search.trim()
            ? "No rankings match your search."
            : isRegionScope
              ? `No rankings available for ${region}.`
              : "No rankings found."}
          <div className="mt-1 text-sm text-[#6b7068]">
            Try adjusting filters or search.
          </div>
        </div>
      </div>
    );
  }
}

function ShortlistPanel({
  shortlist,
  onRemove,
  page,
  canGoPrevious,
  canGoNext,
  onPreviousPage,
  onNextPage,
  editionHref,
}: Readonly<{
  shortlist: ShortlistItem[];
  onRemove: (id: number) => void;
  page: number;
  canGoPrevious: boolean;
  canGoNext: boolean;
  onPreviousPage: () => void;
  onNextPage: () => void;
  /** A link into another year-aware page, keeping the edition this page shows. */
  editionHref: (href: string) => string;
}>) {
  return (
    <div className="space-y-4">
      <section className="rounded-[1.75rem] border border-[#e0ddd8] bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-[#1a3d2e]">Your Shortlist</h2>
            <p className="mt-1 text-sm text-[#6b7068]">
              {shortlist.length} selected {shortlist.length === 1 ? "university" : "universities"}
            </p>
          </div>
          <div className="rounded-full bg-[#e8f2ec] px-3 py-1 text-sm font-semibold text-[#1a3d2e]">
            {shortlist.length}
          </div>
        </div>

        {shortlist.length === 0 ? (
          <div className="mt-4 rounded-2xl bg-[#f5f3ee] p-4 text-sm text-[#6b7068]">
            Add universities from the rankings table to build a shortlist before generating recommendations.
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <Link
              href={editionHref("/recommendations")}
              className="inline-flex w-full items-center justify-center rounded-full bg-[#1a3d2e] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
            >
              Generate Recommendation
            </Link>

            {shortlist.length >= 2 ? (
              <Link
                href={editionHref("/compare")}
                className="inline-flex w-full items-center justify-center rounded-full border border-[#3d7a5a] bg-white px-4 py-3 text-sm font-semibold text-[#1a3d2e] transition hover:bg-[#e8f2ec]"
              >
                Compare Selected
              </Link>
            ) : null}

            <div className="space-y-3">
              {shortlist.map((item) => (
                <div
                  key={item.canonicalUniversityId}
                  className="rounded-2xl border border-[#e0ddd8] bg-[#f5f3ee] px-4 py-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        href={editionHref(`/universities/${item.slug}`)}
                        className="block text-sm font-semibold text-[#1a1a1a] underline-offset-4 transition hover:text-[#1a3d2e] hover:underline"
                      >
                        {item.universityName}
                      </Link>
                      <div className="mt-1 text-sm text-[#6b7068]">
                        {item.country}
                      </div>
                      <div className="mt-2 text-xs font-medium tracking-wide text-[#6b7068]">
                        Rank #{formatRank(item.aggregatedRank)}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onRemove(item.canonicalUniversityId)}
                      className="shrink-0 rounded-full border border-[#e0ddd8] bg-white px-3 py-1.5 text-xs font-medium text-[#1a3d2e] transition hover:border-[#3d7a5a] hover:bg-[#e8f2ec]"
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

      <section className="rounded-[1.75rem] border border-[#e0ddd8] bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-[#1a3d2e]">Page Control</h2>
            <p className="mt-1 text-sm text-[#6b7068]">
              Navigate the rankings browser from here while you review your shortlist.
            </p>
          </div>
          <div className="rounded-full bg-[#e8f2ec] px-3 py-1 text-sm font-semibold text-[#1a3d2e]">
            Page {page}
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            onClick={onPreviousPage}
            disabled={!canGoPrevious}
            className="flex-1 rounded-full border border-[#e0ddd8] bg-white px-4 py-2 text-sm font-medium text-[#1a3d2e] transition hover:border-[#3d7a5a] hover:bg-[#e8f2ec] disabled:cursor-not-allowed disabled:bg-[#f5f3ee] disabled:text-[#6b7068]"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={onNextPage}
            disabled={!canGoNext}
            className="flex-1 rounded-full border border-[#e0ddd8] bg-white px-4 py-2 text-sm font-medium text-[#1a3d2e] transition hover:border-[#3d7a5a] hover:bg-[#e8f2ec] disabled:cursor-not-allowed disabled:bg-[#f5f3ee] disabled:text-[#6b7068]"
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
  // Only a held edition is ever queried: an unheld ?year= reads the default and the
  // selector says so, instead of showing an empty table that looks like no data.
  const { year } = resolveSelectedYear(searchParams.get(YEAR_QUERY_PARAM));
  const source = searchParams.get("source") ?? DEFAULT_SOURCE;
  const search = searchParams.get("search") ?? "";
  const scope = parseScope(searchParams.get("scope"));
  const region = parseRegion(searchParams.get("region"));
  const country = searchParams.get("country") ?? "";

  const [searchInput, setSearchInput] = useState(search);
  const [state, setState] = useState<RankingsState>({
    items: [],
    totalCount: 0,
    loading: true,
    error: null,
    timestamp: undefined,
  });
  const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);

  const { authenticated, refresh: refreshAuth } = useAuth();
  const { savedIds, toggleSave } = useSavedUniversities(
    authenticated,
    () => void refreshAuth()
  );

  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const REFRESH_INTERVAL_MS = 5000;
  const { items, totalCount, loading, error, timestamp } = state;

  useEffect(() => {
    if (loading) {
      return;
    }

    const interval = setInterval(() => {
      setRefreshTrigger((prev) => prev + 1);
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [loading]);

  useEffect(() => {
    function triggerRefresh() {
      setRefreshTrigger((prev) => prev + 1);
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "visible") {
        triggerRefresh();
      }
    }

    window.addEventListener("focus", triggerRefresh);
    window.addEventListener("online", triggerRefresh);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("focus", triggerRefresh);
      window.removeEventListener("online", triggerRefresh);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    setSearchInput(search);
  }, [search]);

  useEffect(() => {
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
  }, []);

  useEffect(() => {
    window.localStorage.setItem(
      SHORTLIST_STORAGE_KEY,
      JSON.stringify(shortlist)
    );
  }, [shortlist]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function fetchRankings() {
      setState((currentState) => ({
        ...currentState,
        loading: true,
        error: null,
      }));

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

        if (country.trim()) {
          params.set("country", country.trim());
        }

        params.set("_ts", Date.now().toString());

        const res = await fetch(`/api/rankings?${params.toString()}`, {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error("Rankings API request failed.");
        }

        const normalized = normalizeRankingsResponse(await res.json());
        const rawItems = normalized.items;
        const nextTotalCount =
          typeof normalized.metadata?.totalCount === "number"
            ? normalized.metadata.totalCount
            : 0;
        const nextTimestamp =
          typeof normalized.metadata?.timestamp === "string"
            ? normalized.metadata.timestamp
            : undefined;

        if (!cancelled) {
          setState({
            items: rawItems,
            totalCount: nextTotalCount,
            loading: false,
            error: null,
            timestamp: nextTimestamp,
          });
        }
      } catch (caughtError) {
        if (isAbortLikeError(caughtError) || controller.signal.aborted) {
          return;
        }
        if (!cancelled) {
          setState({
            items: [],
            totalCount: 0,
            loading: false,
            error: "Unable to load rankings. Please check backend or try again.",
            timestamp: undefined,
          });
        }
      } finally {
        // `loading` is finalized via the state writes above to keep a single source of truth.
      }
    }

    fetchRankings();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [page, pageSize, source, year, scope, region, search, country, refreshTrigger]);

  const filteredItems = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return items.filter((item) => {
      if (scope === "region" && !countryBelongsToRegion(item.country, region)) {
        return false;
      }

      if (country.trim()) {
        const normalizedCountry = normalizeCountryName(country);
        if (normalizeCountryName(item.country) !== normalizedCountry) {
          return false;
        }
      }

      if (!normalizedSearch) {
        return true;
      }

      const haystack = [
        item.universityName,
        item.country,
        item.primarySource,
        item.slug,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedSearch);
    });
  }, [country, items, region, scope, search]);

  const pagedItems = useMemo(() => filteredItems, [filteredItems]);

  const countSummaries = useMemo<RankingCountSummary[]>(
    () =>
      COUNT_SUMMARY_GROUPS.map((group) => {
        if (group.scope === "global") {
          return {
            ...group,
            totalCount: pagedItems.length,
          };
        }

        return {
          ...group,
          totalCount: pagedItems.filter((item) =>
            group.region ? countryBelongsToRegion(item.country, group.region) : false
          ).length,
        };
      }),
    [pagedItems]
  );

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
  const canGoNext = !loading && page * pageSize < totalCount;
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

    router.push(universityHref(slug));
  }

  function handleRowKeyDown(
    event: ReactKeyboardEvent<HTMLTableRowElement>,
    slug: string
  ) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      router.push(universityHref(slug));
    }
  }

  function editionHref(href: string) {
    return hrefForEdition(href, year);
  }

  function universityHref(slug: string) {
    return editionHref(`/universities/${slug}`);
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

  function handleToggleSave(item: RankingItem) {
    if (!authenticated) {
      router.push("/signin");
      return;
    }
    toggleSave(item);
  }

  return (
    <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8 rounded-[2rem] border border-[#e0ddd8] bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-sm font-medium uppercase tracking-[0.18em] text-[#6b7068]">
                Rankings Browser
              </p>
              <h1 className="mt-3 text-4xl font-bold tracking-tight text-[#16382a] sm:text-5xl">
                {heroTitle}
              </h1>
              <p className="mt-3 text-[#6b7068]">
                Structured university ranking data powered by CrawlerNest
              </p>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[#6b7068]">
                {isRegionScope
                  ? `Use ${region.toLowerCase()} rankings, score signals, and source coverage to compare universities inside this region.`
                  : "Use rankings, score signals, and source coverage to quickly evaluate university strength, shortlist promising options, and open deeper decision context for each university."}
              </p>
              {isRegionScope ? (
                <p className="mt-2 text-sm text-[#6b7068]">
                  Browsing universities ranked within {region}.
                </p>
              ) : null}
              {timestamp ? (
                <p className="mt-4 text-sm text-[#6b7068]">
                  Updated: {formatUpdatedTimestamp(timestamp)}
                </p>
              ) : null}
              <div className="mt-6 flex flex-wrap gap-3">
                <div className="rounded-full border border-[#d8d3cb] bg-[#f5f3ee] px-4 py-2 text-sm text-[#1a3d2e]">
                  <span className="font-semibold">{formatRank(totalCount)}</span>{" "}
                  total {pluralize(totalCount, "match", "matches")}
                </div>
                <div className="rounded-full border border-[#d8d3cb] bg-[#f5f3ee] px-4 py-2 text-sm text-[#1a3d2e]">
                  <span className="font-semibold">{year}</span> edition
                </div>
                <div className="rounded-full border border-[#d8d3cb] bg-[#f5f3ee] px-4 py-2 text-sm text-[#1a3d2e]">
                  <span className="font-semibold">{source}</span> view
                </div>
                <div className="rounded-full border border-[#d8d3cb] bg-[#f5f3ee] px-4 py-2 text-sm text-[#1a3d2e]">
                  <span className="font-semibold">{formatRank(pagedItems.length)}</span> on this page
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3 lg:items-end">
              {shortlist.length > 0 ? (
                <Link
                  href={editionHref("/recommendations")}
                  className="inline-flex items-center justify-center rounded-full bg-[#1a3d2e] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
                >
                  Generate Recommendation based on your shortlist
                </Link>
              ) : (
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center justify-center rounded-full bg-[#c0bdb8] px-5 py-3 text-sm font-semibold text-white"
                >
                  Generate Recommendation based on your shortlist
                </button>
              )}
              <p className="text-sm text-[#6b7068]">
                {shortlist.length > 0
                  ? "Move from browsing into a shortlist-driven recommendation flow."
                  : "Add universities to your shortlist to unlock recommendation flow."}
              </p>
            </div>
          </div>

          <RankingsSummary year={year} summaries={countSummaries} />
          <CaveatBanner caveats={editionCaveats(year)} className="mt-6" />
        </header>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <section className="rounded-[2rem] border border-[#e0ddd8] bg-white p-6 shadow-sm">
              <div className="flex flex-col gap-5">
                <div className="flex flex-col gap-2">
                  <h2 className="text-lg font-semibold text-[#1a3d2e]">
                    Explore the Table
                  </h2>
                  <p className="text-sm text-[#6b7068]">
                    {browserDescription}
                  </p>
                  <p className="text-xs uppercase tracking-[0.16em] text-[#6b7068]">
                    Summary cards and table use the current page. Pagination uses the backend total result set.
                  </p>
                </div>

                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-[#1a3d2e]">
                        Scope
                      </span>
                      <select
                        className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                        value={scope}
                        onChange={(e) => handleScopeChange(e.target.value)}
                      >
                        <option value="global">Global</option>
                        <option value="region">Region</option>
                      </select>
                    </label>

                    {isRegionScope ? (
                      <label className="flex flex-col gap-2">
                        <span className="text-sm font-medium text-[#1a3d2e]">
                          Region
                        </span>
                        <select
                          className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
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
                      <span className="text-sm font-medium text-[#1a3d2e]">
                        Source
                      </span>
                      <div className="relative">
                        <select
                          className="w-full rounded-xl border border-[#e0ddd8] bg-[#f5f3ee] px-4 py-3 text-[#6b7068] outline-none"
                          value={source}
                          disabled
                        >
                          <option value="AGGREGATED">AGGREGATED</option>
                        </select>
                        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-[#e8f2ec] px-2.5 py-1 text-[11px] font-semibold text-[#3d7a5a]">
                          Locked
                        </span>
                      </div>
                    </label>

                    <YearSelector variant="page" />

                    <label className="flex flex-col gap-2">
                      <span className="text-sm font-medium text-[#1a3d2e]">
                        Page Size
                      </span>
                      <select
                        className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
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
                      <span className="text-sm font-medium text-[#1a3d2e]">
                        Search
                      </span>
                      <div className="flex items-center gap-2 rounded-xl border border-[#e0ddd8] px-3 py-2 focus-within:border-[#1a3d2e]">
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
                            className="rounded-full px-2 py-1 text-xs font-medium text-[#6b7068] transition hover:bg-[#e8f2ec] hover:text-[#1a3d2e]"
                          >
                            ×
                          </button>
                        ) : null}
                      </div>
                    </label>
                  </div>

                  <div className="rounded-2xl bg-[#f5f3ee] px-4 py-4">
                      <div className="text-sm font-medium uppercase tracking-[0.16em] text-[#6b7068]">
                        {scopeLabel}
                      </div>
                      <div className="mt-3 text-3xl font-bold tracking-tight text-[#16382a]">
                        {loading ? "..." : formatRank(pagedItems.length)}
                      </div>
                      <div className="mt-1 text-sm leading-6 text-[#6b7068]">
                        {!loading && pagedItems.length > 0 ? (
                          <span>
                            Showing rows {pageRowRangeLabel} of {formatRank(totalCount)} total matches
                          </span>
                        ) : null}
                        {!loading && pagedItems.length === 0 ? (
                          <span>No rankings loaded</span>
                        ) : null}
                      </div>
                      {!loading && search.trim() ? (
                        <div className="mt-2 text-sm leading-6 text-[#6b7068]">
                          Search narrowed this page to {formatRank(pagedItems.length)}{" "}
                          {pluralize(pagedItems.length, "result", "results")}
                        </div>
                      ) : null}
                      <div className="mt-3 text-xs uppercase tracking-[0.18em] text-[#6b7068]">
                        {isRegionScope ? `${region} ranking universe` : "Global ranking universe"}
                      </div>
                    </div>
                  </div>

                <div className="border-t border-[#e0ddd8] pt-4">
                  <p className="text-sm text-[#6b7068]">
                    {isRegionScope
                      ? `Browse ${region.toLowerCase()} rankings, shortlist strong regional options, then move into recommendation.`
                      : "Browse, shortlist, compare mentally, then move into recommendation."}
                  </p>
                </div>
              </div>
            </section>

            <section className="overflow-hidden rounded-[2rem] border border-[#e0ddd8] bg-white shadow-sm">
              <div className="flex flex-col gap-2 border-b border-[#e0ddd8] bg-white px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-[#1a3d2e]">
                    {scopeLabel}
                  </h2>
                  <p className="mt-1 text-sm text-[#6b7068]">
                    {isRegionScope
                      ? `Scan regional rank first, then use global position and score to compare universities inside ${region}.`
                      : "Scan rank, score, shortlist signal, and add strong candidates as you browse."}
                  </p>
                </div>
                <div className="text-sm text-[#6b7068]">
                  Click any row to view details
                </div>
              </div>

              <RankingsTable
                error={error}
                loading={loading}
                pagedItems={pagedItems}
                shortlistIds={shortlistIds}
                savedIds={savedIds}
                isRegionScope={isRegionScope}
                search={search}
                region={region}
                onRetry={handleRetry}
                onRowClick={handleRowClick}
                onRowKeyDown={handleRowKeyDown}
                onToggleShortlist={toggleShortlist}
                onToggleSave={handleToggleSave}
                universityHref={universityHref}
              />
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
              editionHref={editionHref}
            />
          </div>
        </div>
      </div>
    </main>
  );
}

export default RankingsHomeContent;
