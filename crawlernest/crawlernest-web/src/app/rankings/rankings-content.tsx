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
      tone: "bg-(--color-paper-2) text-(--color-ink) ring-1 ring-(--color-ink-2)",
    };
  }

  if (rank <= 150) {
    return {
      label: "Target",
      caption: "Balanced shortlist fit",
      tone: "bg-(--color-paper) text-(--color-ink-2) ring-1 ring-(--color-muted)",
    };
  }

  return {
    label: "Safety",
    caption: "More accessible option",
    tone: "bg-(--color-paper) text-(--color-muted) ring-1 ring-(--color-rule)",
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
    <div className="rk-state" aria-busy="true" aria-label="Loading rankings">
      <div className="skeleton-row" />
      <div className="skeleton-row" />
      <div className="skeleton-row" />
      <div className="skeleton-row" />
    </div>
  );
}

export function RankingsShell({ message }: Readonly<{ message: string }>) {
  return (
    <main className="rk">
      <div className="rk-state">
        <p>{message}</p>
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
    <section className="rk-regions" aria-labelledby="rk-regions-title">
      <div className="rk-regions__head">
        <h2 id="rk-regions-title" className="rk-regions__title">
          By region, {year}
        </h2>
        <p className="rk-regions__hint">Universities on this page</p>
      </div>
      <ul className="rk-regions__list">
        {summaries.map((summary) => (
          <li
            key={`${summary.scope}-${summary.region ?? "global"}`}
            className={`rk-regions__item${summary.totalCount === 0 ? " rk-regions__item--empty" : ""}`}
          >
            <span>{summary.label}</span>
            <span className="code">
              {formatRank(summary.totalCount)}
              <span className="visually-hidden">
                {" "}
                {pluralize(summary.totalCount, "university", "universities")} in {year}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
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
      <table className="ledger">
        <thead>
          <tr>
            <th scope="col" className="ledger__rank">Rank</th>
            <th scope="col">University</th>
            <th scope="col" className="num">Score</th>
            <th scope="col" className="num">Source coverage</th>
            <th scope="col">Selection</th>
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
                data-selected={isShortlisted ? "true" : undefined}
                onClick={(event) => onRowClick(event, item.slug)}
                onKeyDown={(event) => onRowKeyDown(event, item.slug)}
              >
                <td className="ledger__rank">
                  <span className="ledger__rank-num">#{formatRank(displayRank)}</span>
                  {isRegionScope && globalRank !== displayRank ? (
                    <span className="ledger__rank-sub">Global #{formatRank(globalRank)}</span>
                  ) : null}
                  <span className="ledger__rank-sub">{context.label}</span>
                </td>

                <td>
                  <Link href={universityHref(item.slug)} className="ledger__name">
                    {item.universityName}
                  </Link>
                  <div className="ledger__meta">{item.country}</div>
                  <div className="ledger__tags">
                    <span className="ledger__tag">{item.primarySource}</span>
                    <span className="ledger__tag">{item.rankingYear}</span>
                  </div>
                </td>

                <td className="num ledger__stat">
                  <div className="ledger__fig">{formatScore(item.compositeScore)}</div>
                  <div className="ledger__cap">
                    {isRegionScope
                      ? `${context.caption}, global #${formatRank(globalRank)}`
                      : context.caption}
                  </div>
                </td>

                <td className="num ledger__stat">
                  <div className="ledger__fig">{item.sourceCount}</div>
                  <div className="ledger__cap">
                    ranking {pluralize(item.sourceCount, "source", "sources")}
                  </div>
                </td>

                <td>
                  <div className="ledger__acts">
                    <button
                      type="button"
                      onClick={() => onToggleShortlist(item)}
                      aria-pressed={isShortlisted}
                      className={`btn ${isShortlisted ? "btn--on" : "btn--quiet"}`}
                    >
                      {isShortlisted ? "Added" : "Shortlist"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onToggleSave(item)}
                      aria-pressed={isSaved}
                      className={`btn ${isSaved ? "btn--on" : "btn--quiet"}`}
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
    );
  }

  if (loading) {
    return <LoadingSkeleton />;
  }

  if (error) {
    return (
      <div className="rk-state rk-state--error" role="alert">
        <p>Unable to load rankings.</p>
        <p>Please check backend or try again.</p>
        <button type="button" onClick={onRetry} className="btn btn--secondary">
          Retry
        </button>
      </div>
    );
  }

  if (pagedItems.length === 0) {
    return (
      <div className="rk-state">
        <p>
          {search.trim()
            ? "No rankings match your search."
            : isRegionScope
              ? `No rankings available for ${region}.`
              : "No rankings found."}
        </p>
        <p>Try adjusting filters or search.</p>
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
    <div>
      <section className="card rail-card" aria-labelledby="rk-shortlist-title">
        <div className="rail-card__head">
          <h2 id="rk-shortlist-title">Your shortlist</h2>
          <span className="rail-card__count" aria-hidden="true">
            {shortlist.length}
          </span>
        </div>
        <p className="rail-card__note">
          {shortlist.length} selected {shortlist.length === 1 ? "university" : "universities"}
        </p>

        {shortlist.length === 0 ? (
          <p className="rail-card__empty">
            Add universities from the rankings table to build a shortlist before generating recommendations.
          </p>
        ) : (
          <>
            <div className="rail-card__actions">
              <Link href={editionHref("/recommendations")} className="btn btn--primary btn--block">
                Generate recommendation
              </Link>

              {shortlist.length >= 2 ? (
                <Link href={editionHref("/compare")} className="btn btn--secondary btn--block">
                  Compare selected
                </Link>
              ) : null}
            </div>

            <ul className="rail-list">
              {shortlist.map((item) => (
                <li key={item.canonicalUniversityId}>
                  <div>
                    <Link href={editionHref(`/universities/${item.slug}`)}>
                      {item.universityName}
                    </Link>
                    <div className="rail-list__meta">
                      {item.country}, rank <span className="code">#{formatRank(item.aggregatedRank)}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => onRemove(item.canonicalUniversityId)}
                    className="btn btn--quiet"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="pager" aria-labelledby="rk-pager-title">
        <div className="pager__head">
          <h2 id="rk-pager-title">Page control</h2>
          <span className="code">Page {page}</span>
        </div>
        <p className="pager__note">
          Navigate the rankings browser from here while you review your shortlist.
        </p>
        <div className="pager__row">
          <button
            type="button"
            onClick={onPreviousPage}
            disabled={!canGoPrevious}
            className="btn btn--secondary"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={onNextPage}
            disabled={!canGoNext}
            className="btn btn--secondary"
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
    <main className="rk">
      <header>
        <div className="rk-head">
          <div>
            <h1 className="rk-head__title">{heroTitle}</h1>
            <p className="rk-head__lead">
              {isRegionScope
                ? `Use ${region.toLowerCase()} rankings, score signals, and source coverage to compare universities inside this region.`
                : "Use rankings, score signals, and source coverage to quickly evaluate university strength, shortlist promising options, and open deeper decision context for each university."}
            </p>
            <p className="rk-head__note">
              Structured university ranking data powered by CrawlerNest
              {isRegionScope ? `. Browsing universities ranked within ${region}.` : null}
            </p>
          </div>

          <div className="rk-head__act">
            {shortlist.length > 0 ? (
              <Link href={editionHref("/recommendations")} className="btn btn--primary">
                Generate Recommendation<span className="rk-tail"> based on your shortlist</span>
              </Link>
            ) : (
              <button type="button" disabled className="btn btn--primary">
                Generate Recommendation<span className="rk-tail"> based on your shortlist</span>
              </button>
            )}
            <p>
              {shortlist.length > 0
                ? "Move from browsing into a shortlist-driven recommendation flow."
                : "Add universities to your shortlist to unlock recommendation flow."}
            </p>
          </div>
        </div>

        <dl className="rk-record">
          <div className="rk-record__cell">
            <dt className="rk-record__label">total {pluralize(totalCount, "match", "matches")}</dt>
            <dd className="rk-record__value">{formatRank(totalCount)}</dd>
          </div>
          <div className="rk-record__cell">
            <dt className="rk-record__label">edition</dt>
            <dd className="rk-record__value">{year}</dd>
          </div>
          <div className="rk-record__cell">
            <dt className="rk-record__label">view</dt>
            <dd className="rk-record__value">{source}</dd>
          </div>
          <div className="rk-record__cell">
            <dt className="rk-record__label">
              on this page
              {timestamp ? `, updated ${formatUpdatedTimestamp(timestamp)}` : null}
            </dt>
            <dd className="rk-record__value">{formatRank(pagedItems.length)}</dd>
          </div>
        </dl>

        <RankingsSummary year={year} summaries={countSummaries} />
        <CaveatBanner caveats={editionCaveats(year)} className="rk-caveats" />
      </header>

      <section className="rk-tools" aria-labelledby="rk-tools-title">
        <div className="rk-table-head">
          <h2 id="rk-tools-title" className="visually-hidden">
            Explore the table
          </h2>
          <p>{browserDescription}</p>
        </div>

        <div className="rk-tools__fields">
          <label className="field">
            <span className="field__label">Scope</span>
            <select
              className="select"
              value={scope}
              onChange={(e) => handleScopeChange(e.target.value)}
            >
              <option value="global">Global</option>
              <option value="region">Region</option>
            </select>
          </label>

          {isRegionScope ? (
            <label className="field">
              <span className="field__label">Region</span>
              <select
                className="select"
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

          <label className="field">
            <span className="field__label">Source</span>
            <select className="select" value={source} disabled aria-describedby="rk-source-note">
              <option value="AGGREGATED">AGGREGATED</option>
            </select>
            <span id="rk-source-note" className="field__note">
              Locked
            </span>
          </label>

          <YearSelector variant="page" />

          <label className="field">
            <span className="field__label">Page size</span>
            <select
              className="select"
              value={pageSize}
              onChange={(e) => handlePageSizeChange(Number(e.target.value))}
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="field field--wide">
            <span className="field__label">Search</span>
            <span className="search">
              <input
                className="input"
                type="search"
                value={searchInput}
                onChange={(e) => handleSearchChange(e.target.value)}
                placeholder="Search university or country"
              />
              {searchInput ? (
                <button
                  type="button"
                  onClick={() => handleSearchChange("")}
                  className="search__clear"
                  aria-label="Clear search"
                >
                  ×
                </button>
              ) : null}
            </span>
          </label>
        </div>

        <div className="rk-tools__meta" aria-live="polite">
          <span>
            <strong>{scopeLabel}</strong>
          </span>
          {loading ? <span>Loading</span> : null}
          {!loading && pagedItems.length > 0 ? (
            <span>
              Showing rows <span className="code">{pageRowRangeLabel}</span> of{" "}
              <span className="code">{formatRank(totalCount)}</span> total matches
            </span>
          ) : null}
          {!loading && pagedItems.length === 0 ? <span>No rankings loaded</span> : null}
          {!loading && search.trim() ? (
            <span>
              Search narrowed this page to {formatRank(pagedItems.length)}{" "}
              {pluralize(pagedItems.length, "result", "results")}
            </span>
          ) : null}
          <span>{isRegionScope ? `${region} ranking universe` : "Global ranking universe"}</span>
          <span>Summary cards and table use the current page. Pagination uses the backend total result set.</span>
          <span>
            {isRegionScope
              ? `Browse ${region.toLowerCase()} rankings, shortlist strong regional options, then move into recommendation.`
              : "Browse, shortlist, compare mentally, then move into recommendation."}
          </span>
        </div>
      </section>

      <div className="rk-body">
        <section aria-labelledby="rk-table-title">
          <div className="rk-table-head">
            <h2 id="rk-table-title">{scopeLabel}</h2>
            <p>
              {isRegionScope
                ? `Scan regional rank first, then use global position and score to compare universities inside ${region}.`
                : "Scan rank, score, shortlist signal, and add strong candidates as you browse."}{" "}
              Click any row to view details.
            </p>
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

        <aside className="rk-rail">
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
        </aside>
      </div>
    </main>
  );
}

export default RankingsHomeContent;
