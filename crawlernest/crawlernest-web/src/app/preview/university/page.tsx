"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

export default function UniversityPreviewPage() {
  const searchParams = useSearchParams();
  const canonicalUniversityId = searchParams.get("canonicalUniversityId");
  const universityName = searchParams.get("universityName");

  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!canonicalUniversityId && !universityName) {
      setError("Invalid query");
      setLoading(false);
      return;
    }

    let url = "/api/university-preview?";

    if (canonicalUniversityId) {
      url += `canonicalUniversityId=${canonicalUniversityId}`;
    } else {
      url += `universityName=${encodeURIComponent(universityName!)}`;
    }

    fetch(url)
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 404) throw new Error("University not found");
          if (res.status === 400) throw new Error("Invalid query");
          throw new Error("Failed to fetch");
        }
        return res.json();
      })
      .then((json) => {
        setData(json.data);
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [canonicalUniversityId, universityName]);

  const showAliasBadges = Array.isArray(data?.aliases) ? data.aliases : [];
  const rankingYears = Array.isArray(data?.rankingSummary?.rankingYears)
    ? data.rankingSummary.rankingYears
    : [];
  const rankingSources = Array.isArray(data?.rankingSummary?.sources)
    ? data.rankingSummary.sources
    : [];
  const admissionCountries = Array.isArray(data?.admissionSummary?.countries)
    ? data.admissionSummary.countries
    : [];
  const missingSections = [
    data?.hasRankingData ? null : "Ranking",
    data?.hasAdmissionData ? null : "Admission",
  ]
    .filter(Boolean)
    .join(", ");

  const renderBadge = (value: string) => (
    <span
      key={value}
      className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700"
    >
      {value}
    </span>
  );

  const renderValue = (value: unknown): string => {
    if (value === null || value === undefined || value === "") {
      return "N/A";
    }
    return String(value);
  };

  const renderBoolean = (value?: boolean) => (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${
        value ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"
      }`}
    >
      {value ? "Yes" : "No"}
    </span>
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-10">
        <div className="rounded-3xl border border-slate-200 bg-white px-8 py-12 text-center shadow-sm">
          <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Loading university preview</p>
          <p className="mt-4 text-2xl font-semibold text-slate-900">Please wait...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-10">
        <div className="rounded-3xl border border-rose-200 bg-rose-50 px-8 py-8 shadow-sm">
          <p className="text-lg font-semibold text-rose-800">Error loading preview</p>
          <p className="mt-3 text-sm text-rose-700">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <div className="rounded-[32px] border border-slate-200 bg-white px-6 py-8 shadow-sm sm:px-10">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Preview Mode</p>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
                {renderValue(data?.universityDisplayName)}
              </h1>
              <p className="mt-2 text-sm text-slate-600">
                Normalized Name: {renderValue(data?.normalizedUniversityName)}
              </p>
            </div>
            <div className="rounded-3xl bg-slate-100 px-4 py-3 text-sm text-slate-700">
              <div className="font-semibold text-slate-900">Query</div>
              <div className="mt-1 text-slate-600">
                {canonicalUniversityId
                  ? `canonicalUniversityId=${canonicalUniversityId}`
                  : `universityName=${universityName}`}
              </div>
              <div className="mt-3 text-slate-500">ID: {renderValue(data?.canonicalUniversityId)}</div>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {showAliasBadges.length > 0 ? (
              showAliasBadges.map((alias: string) => renderBadge(alias))
            ) : (
              <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-500">
                No aliases
              </span>
            )}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <section className="rounded-[32px] border border-slate-200 bg-white px-6 py-8 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">Identity</p>
                <h2 className="mt-2 text-xl font-semibold text-slate-900">Canonical identity</h2>
              </div>
            </div>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Canonical slug</p>
                <p className="mt-2 text-base font-medium text-slate-900">{renderValue(data?.canonicalSlug)}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Status</p>
                <p className="mt-2 text-base font-medium text-slate-900">{renderValue(data?.status)}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Alias count</p>
                <p className="mt-2 text-base font-medium text-slate-900">{showAliasBadges.length}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Matched by</p>
                <p className="mt-2 text-base font-medium text-slate-900">{renderValue(data?.matchedBy)}</p>
                <p className="mt-1 text-sm text-slate-500">{renderValue(data?.matchedValue)}</p>
              </div>
            </div>
          </section>

          <section className="rounded-[32px] border border-slate-200 bg-white px-6 py-8 shadow-sm">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">Availability</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-900">Data overview</h2>
            <div className="mt-6 space-y-4">
              <div className="flex items-center justify-between rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
                <span className="text-sm text-slate-600">Ranking</span>
                {renderBoolean(data?.hasRankingData)}
              </div>
              <div className="flex items-center justify-between rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
                <span className="text-sm text-slate-600">Admission</span>
                {renderBoolean(data?.hasAdmissionData)}
              </div>
              <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
                <p className="text-sm text-slate-600">Missing sections</p>
                <p className="mt-2 text-base font-medium text-slate-900">{missingSections || "None"}</p>
              </div>
            </div>
          </section>
        </div>

        <section className="rounded-[32px] border border-slate-200 bg-white px-6 py-8 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">Ranking</p>
              <h2 className="mt-2 text-xl font-semibold text-slate-900">Summary</h2>
            </div>
            {!data?.rankingSummary && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-600">No ranking data</span>
            )}
          </div>

          {data?.rankingSummary ? (
            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Best Rank</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{renderValue(data.rankingSummary.bestRank)}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Best Source</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{renderValue(data.rankingSummary.bestSource)}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Best Ranking Year</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{renderValue(data.rankingSummary.bestRankingYear)}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Source Count</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{renderValue(data.rankingSummary.sourceCount)}</p>
              </div>
            </div>
          ) : null}

          {data?.rankingSummary ? (
            <div className="mt-6 space-y-4">
              <div>
                <p className="text-sm font-semibold text-slate-500">Years</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {rankingYears.length > 0
                    ? rankingYears.map((year: string | number) => renderBadge(String(year)))
                    : renderBadge("N/A")}
                </div>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-500">Sources</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {rankingSources.length > 0
                    ? rankingSources.map((source: string) => renderBadge(source))
                    : renderBadge("N/A")}
                </div>
              </div>
            </div>
          ) : null}
        </section>

        <section className="rounded-[32px] border border-slate-200 bg-white px-6 py-8 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">Admission</p>
              <h2 className="mt-2 text-xl font-semibold text-slate-900">Summary</h2>
            </div>
            {!data?.admissionSummary && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-600">No admission data</span>
            )}
          </div>

          {data?.admissionSummary ? (
            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Best IELTS</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{renderValue(data.admissionSummary.bestIeltsRequirement)}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Best TOEFL</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{renderValue(data.admissionSummary.bestToeflRequirement)}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Source URL Count</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{renderValue(data.admissionSummary.sourceUrlCount)}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-sm text-slate-500">Latest Extracted At</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{renderValue(data.admissionSummary.latestExtractedAt)}</p>
              </div>
            </div>
          ) : null}

          {data?.admissionSummary ? (
            <div className="mt-6">
              <p className="text-sm font-semibold text-slate-500">Countries</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {admissionCountries.length > 0
                  ? admissionCountries.map((country: string) => renderBadge(country))
                  : renderBadge("N/A")}
              </div>
            </div>
          ) : null}

          {/* Rendered by the API with the fetch date; shown verbatim. */}
          {Array.isArray(data?.admissionCaveats) && data.admissionCaveats.length > 0 ? (
            <ul className="mt-6 space-y-1" aria-label="Admission data caveats">
              {data.admissionCaveats.map((caveat: string) => (
                <li key={caveat} className="text-xs text-slate-500">
                  · {caveat}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      </div>
    </main>
  );
}
