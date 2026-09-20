"use client";

import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";

import { CaveatBanner } from "@/components/CaveatBanner";
import SubjectRankingTable from "@/components/SubjectRankingTable";
import { YearSelector, YearSelectorFallback } from "@/components/YearSelector";
import { useSelectedYear } from "@/hooks/useSelectedYear";
import { useSubjectRankings } from "@/hooks/useSubjectRankings";
import { subjectEditionCaveats } from "@/lib/caveatMessages";
import {
  DEFAULT_RANKING_YEAR,
  SUBJECT_DATASET_YEARS,
  subjectSourcesForYear,
} from "@/lib/datasetScope";
import type {
  SubjectOption,
  SubjectOptionsApiResponse,
  SubjectRankingRow,
} from "@/types/subjectRanking";

const DEFAULT_SUBJECT = "computer-science";
const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [20, 50, 100];
const FALLBACK_SUBJECTS: SubjectOption[] = [
  { subjectKey: "computer-science", subjectName: "Computer Science" },
  {
    subjectKey: "electrical-engineering",
    subjectName: "Electrical Engineering",
  },
];

function buildSubjectInsight(items: SubjectRankingRow[]) {
  const countryCounts = new Map<string, number>();
  const scores: number[] = [];
  const ranks: number[] = [];

  items.forEach((item) => {
    const country = item.countryName || "Unknown";
    countryCounts.set(country, (countryCounts.get(country) ?? 0) + 1);

    if (typeof item.score === "number" && Number.isFinite(item.score)) {
      scores.push(item.score);
    }

    if (typeof item.rankPosition === "number" && Number.isFinite(item.rankPosition)) {
      ranks.push(item.rankPosition);
    }
  });

  const topCountries = Array.from(countryCounts.entries())
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 5)
    .map(([country, count]) => ({ country, count }));
  const averageScore =
    scores.length === 0
      ? null
      : scores.reduce((total, score) => total + score, 0) / scores.length;
  const topRankShare =
    ranks.length === 0
      ? 0
      : ranks.filter((rank) => rank <= 50).length / ranks.length;
  const difficultyLevel =
    ranks.length === 0
      ? "Unknown"
      : topRankShare >= 0.6
        ? "Highly concentrated"
        : topRankShare >= 0.3
          ? "Selective"
          : "Broad";

  return {
    topCountries,
    averageScore,
    difficultyLevel,
    rankedCount: ranks.length,
  };
}

function SubjectInsight({ items, loading }: { items: SubjectRankingRow[]; loading: boolean }) {
  const insight = buildSubjectInsight(items);
  const maxCountryCount = Math.max(1, ...insight.topCountries.map((item) => item.count));
  const topCountry = insight.topCountries[0];
  const narrative = loading
    ? "Subject narrative is loading with the current result set."
    : insight.rankedCount === 0
      ? "There is not enough subject ranking data yet to describe this field."
      : `${topCountry?.country ?? "The leading country"} has the largest visible presence in this subject result set. The average visible QS score is ${
          insight.averageScore == null ? "not available" : insight.averageScore.toFixed(1)
        }, and the rank distribution looks ${insight.difficultyLevel.toLowerCase()}.`;

  return (
    <section className="mt-6 border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-600">
            Subject Insight
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Lightweight summary for the current subject selection.
          </p>
        </div>
        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
          {loading ? "Loading" : `${insight.rankedCount} ranked rows`}
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="border border-slate-100 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
            Top Countries
          </div>
          <div className="mt-4 space-y-3">
            {loading ? (
              <div className="h-20 animate-pulse bg-slate-100" />
            ) : insight.topCountries.length > 0 ? (
              insight.topCountries.map((item) => (
                <div key={item.country}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="font-medium text-slate-700">{item.country}</span>
                    <span className="font-mono text-slate-500">{item.count}</span>
                  </div>
                  <div className="h-2 bg-white">
                    <div
                      className="h-2 bg-blue-600"
                      style={{ width: `${(item.count / maxCountryCount) * 100}%` }}
                    />
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No country distribution yet.</p>
            )}
          </div>
        </div>

        <div className="border border-slate-100 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
            Average Score
          </div>
          <div className="mt-4 text-4xl font-black tracking-tight text-slate-950">
            {loading
              ? "..."
              : insight.averageScore == null
                ? "—"
                : insight.averageScore.toFixed(1)}
          </div>
          <p className="mt-2 text-sm text-slate-500">QS score average in the current result set.</p>
        </div>

        <div className="border border-slate-100 bg-slate-50 p-4">
          <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
            Difficulty Level
          </div>
          <div className="mt-4 text-2xl font-black tracking-tight text-slate-950">
            {loading ? "..." : insight.difficultyLevel}
          </div>
          <p className="mt-2 text-sm text-slate-500">
            Estimated from how much of the visible set sits inside the top 50 ranks.
          </p>
        </div>
      </div>

      <div className="mt-4 border border-slate-100 bg-slate-50 p-4">
        <div className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">
          Narrative
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-700">{narrative}</p>
      </div>
    </section>
  );
}

/** Reads the edition from the URL; the body takes it as a prop, router-free. */
export default function SubjectRankingsPage() {
  return (
    // A placeholder, not the page itself: rendering the body here would fetch the
    // default edition and then fetch again once the URL is readable.
    <Suspense fallback={<main className="min-h-screen bg-slate-50" />}>
      <SubjectRankingsPageWithSelectedYear />
    </Suspense>
  );
}

function SubjectRankingsPageWithSelectedYear() {
  const { year } = useSelectedYear();
  return (
    <SubjectRankingsPageContent
      rankingYear={year}
      yearSelector={<YearSelector variant="page" years={SUBJECT_DATASET_YEARS} />}
    />
  );
}

type SubjectRankingsPageContentProps = {
  /** A held edition; the wrapper resolves it from `?year=`. */
  rankingYear?: number;
  yearSelector?: ReactNode;
};

export function SubjectRankingsPageContent({
  rankingYear = DEFAULT_RANKING_YEAR,
  yearSelector = <YearSelectorFallback variant="page" />,
}: SubjectRankingsPageContentProps = {}) {
  const [subjects, setSubjects] = useState<SubjectOption[]>(FALLBACK_SUBJECTS);
  const [subject, setSubject] = useState(DEFAULT_SUBJECT);
  const [countryInput, setCountryInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [country, setCountry] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [subjectListError, setSubjectListError] = useState<string | null>(null);
  const [hasMounted, setHasMounted] = useState(false);

  useEffect(() => {
    setHasMounted(true);
  }, []);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    async function fetchSubjects() {
      try {
        const response = await fetch("/api/subject-rankings/subjects", {
          cache: "no-store",
          signal: controller.signal,
        });
        const payload = (await response.json()) as SubjectOptionsApiResponse;

        if (!response.ok || payload.success === false) {
          throw new Error(payload?.data?.error || payload?.error || "HTTP error");
        }

        const resolvedSubjects = Array.isArray(payload.data?.items)
          ? payload.data.items
          : [];

        if (isMounted && resolvedSubjects.length > 0) {
          setSubjects(resolvedSubjects);
          setSubject((current) =>
            resolvedSubjects.some((item) => item.subjectKey === current)
              ? current
              : resolvedSubjects[0].subjectKey
          );
        }
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }

        if (isMounted) {
          setSubjectListError("Subject list is using the local MVP defaults.");
        }
      }
    }

    fetchSubjects();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setCountry(countryInput);
      setSearch(searchInput);
      setPage(1);
    }, 350);

    return () => window.clearTimeout(timeout);
  }, [countryInput, searchInput]);

  const {
    items,
    metadata,
    totalCount,
    loading,
    error,
    totalPages,
  } = useSubjectRankings({
    subject,
    year: rankingYear,
    page,
    pageSize,
    country,
    search,
  });

  // Page 7 of the 2026 table is not page 7 of another edition. Adjusted during
  // render rather than in an effect, which would render the old page number
  // against the new edition first and re-render to fix it.
  const [pagedEdition, setPagedEdition] = useState(rankingYear);
  if (pagedEdition !== rankingYear) {
    setPagedEdition(rankingYear);
    setPage(1);
  }

  // The edition the page is showing. metadata.year comes back only when the
  // query found rows, so for an edition with none it is the requested year that
  // has to be named -- saying nothing would leave the empty table unexplained.
  const editionShown = metadata.year ?? rankingYear;

  const selectedSubjectName = useMemo(() => {
    return (
      subjects.find((item) => item.subjectKey === subject)?.subjectName ??
      "Subject Ranking"
    );
  }, [subject, subjects]);

  const startRow = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endRow = Math.min(page * pageSize, totalCount);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.14em] text-blue-700">
                QS Subject Rankings
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
                {selectedSubjectName}
              </h1>
            </div>
            <div className="text-sm text-slate-500">
              {/* The source is named only for an edition that has one. "2018
                  edition · QS" attributed QS to an edition with no QS subject
                  row in it. */}
              {editionShown} edition
              {subjectSourcesForYear(editionShown).length > 0
                ? ` · ${metadata.source ?? subjectSourcesForYear(editionShown).join(", ")}`
                : " · no subject data held"}
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-6 lg:px-8">
        <div className="border border-slate-200 bg-white p-4 shadow-sm">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700 xl:col-span-2">
              Subject
              <select
                value={subject}
                onChange={(event) => {
                  setSubject(event.target.value);
                  setPage(1);
                }}
                className="h-11 border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
              >
                {subjects.map((item) => (
                  <option key={item.subjectKey} value={item.subjectKey}>
                    {item.subjectName}
                  </option>
                ))}
              </select>
            </label>

            {yearSelector}

            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700">
              Country
              <input
                value={countryInput}
                onChange={(event) => setCountryInput(event.target.value)}
                placeholder="United States"
                className="h-11 border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
              />
            </label>

            <label className="flex flex-col gap-2 text-sm font-medium text-slate-700 xl:col-span-2">
              Search
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="University name"
                className="h-11 border border-slate-300 bg-white px-3 text-sm text-slate-950 outline-none placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
              />
            </label>
          </div>

          {subjectListError ? (
            <div className="mt-4 border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {subjectListError}
            </div>
          ) : null}
        </div>

        {error ? (
          <div className="mt-6 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}

        {hasMounted ? <SubjectInsight items={items} loading={loading} /> : null}

        <div className="mt-6">
          <SubjectRankingTable items={items} loading={loading} rankingYear={rankingYear} />
        </div>

        <CaveatBanner className="mt-4" caveats={subjectEditionCaveats(editionShown)} />

        <div className="mt-4 flex flex-col gap-3 border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm md:flex-row md:items-center md:justify-between">
          <div>
            {loading
              ? "Loading..."
              : `${startRow}-${endRow} of ${totalCount} subject ranking rows`}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2">
              Page size
              <select
                value={pageSize}
                onChange={(event) => {
                  setPageSize(Number(event.target.value));
                  setPage(1);
                }}
                className="h-9 border border-slate-300 bg-white px-2 text-sm text-slate-950 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
              >
                {PAGE_SIZE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page <= 1 || loading}
              className="h-9 border border-slate-300 px-3 font-medium text-slate-700 transition-colors hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Previous
            </button>
            <span className="min-w-20 text-center">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() =>
                setPage((current) => Math.min(totalPages, current + 1))
              }
              disabled={page >= totalPages || loading}
              className="h-9 border border-slate-300 px-3 font-medium text-slate-700 transition-colors hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
