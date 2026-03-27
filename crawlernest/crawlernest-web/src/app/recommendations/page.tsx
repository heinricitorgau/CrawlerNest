"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useEffect, useMemo, useState } from "react";

import { fetchAppJson } from "@/lib/api";
import {
  formatIelts,
  formatRank,
  formatScore,
} from "@/lib/format";

type ShortlistItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  slug: string;
};

type ComparisonItem = ShortlistItem & {
  ieltsMin?: number;
  matchingScore?: number;
};

type RecommendationItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  ieltsMin: number;
  matchingScore: number;
  recommendationConfidence: number;
  explanation: string;
};

type RecommendationResponse = {
  success: boolean;
  data: {
    reach: RecommendationItem[];
    target: RecommendationItem[];
    safety: RecommendationItem[];
  };
  metadata?: {
    candidate_count?: number;
    counts?: {
      reach?: number;
      target?: number;
      safety?: number;
    };
  };
};

const SHORTLIST_STORAGE_KEY = "crawlernest_shortlist";

function formatConfidence(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }

  if (value <= 1) {
    return `${Math.round(value * 100)}%`;
  }

  return `${Math.round(value)}%`;
}

function RecommendationPageContent() {
  const [country, setCountry] = useState("United Kingdom");
  const [ielts, setIelts] = useState(6.5);
  const [targetRank, setTargetRank] = useState(100);
  const [riskProfile, setRiskProfile] = useState("balanced");

  const [data, setData] = useState<RecommendationResponse["data"] | null>(null);
  const [metadata, setMetadata] = useState<RecommendationResponse["metadata"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shortlistContext, setShortlistContext] = useState<ShortlistItem[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      const storedValue = window.localStorage.getItem(SHORTLIST_STORAGE_KEY);
      if (!storedValue) {
        setShortlistContext([]);
        return;
      }

      const parsedValue = JSON.parse(storedValue);
      if (!Array.isArray(parsedValue)) {
        setShortlistContext([]);
        return;
      }

      const shortlist = parsedValue.filter((item): item is ShortlistItem => {
        return (
          typeof item?.canonicalUniversityId === "number" &&
          typeof item?.universityName === "string" &&
          typeof item?.country === "string" &&
          typeof item?.aggregatedRank === "number" &&
          typeof item?.slug === "string"
        );
      });

      setShortlistContext(shortlist);
    } catch {
      setShortlistContext([]);
    }
  }, []);

  const totalCount = useMemo(() => {
    if (metadata?.candidate_count !== undefined) {
      return metadata.candidate_count;
    }

    if (!data) {
      return 0;
    }

    return data.reach.length + data.target.length + data.safety.length;
  }, [data, metadata]);

  const recommendationLookup = useMemo(() => {
    const lookup = new Map<number, RecommendationItem>();
    if (!data) {
      return lookup;
    }

    [...data.reach, ...data.target, ...data.safety].forEach((item) => {
      if (!lookup.has(item.canonicalUniversityId)) {
        lookup.set(item.canonicalUniversityId, item);
      }
    });

    return lookup;
  }, [data]);

  const comparisonItems = useMemo<ComparisonItem[]>(() => {
    return shortlistContext.map((item) => {
      const recommendation = recommendationLookup.get(item.canonicalUniversityId);
      return {
        ...item,
        ieltsMin: recommendation?.ieltsMin,
        matchingScore: recommendation?.matchingScore,
      };
    });
  }, [recommendationLookup, shortlistContext]);

  const bestRank = useMemo(() => {
    if (comparisonItems.length === 0) {
      return null;
    }
    return Math.min(...comparisonItems.map((item) => item.aggregatedRank));
  }, [comparisonItems]);

  const bestIelts = useMemo(() => {
    const values = comparisonItems
      .map((item) => item.ieltsMin)
      .filter((value): value is number => value !== undefined);

    if (values.length === 0) {
      return null;
    }

    return Math.min(...values);
  }, [comparisonItems]);

  const bestMatchScore = useMemo(() => {
    const values = comparisonItems
      .map((item) => item.matchingScore)
      .filter((value): value is number => value !== undefined);

    if (values.length === 0) {
      return null;
    }

    return Math.max(...values);
  }, [comparisonItems]);

  const comparisonExplanations = useMemo(() => {
    if (comparisonItems.length < 2) {
      return [] as string[];
    }

    const sortedByRank = [...comparisonItems].sort(
      (a, b) => a.aggregatedRank - b.aggregatedRank
    );
    const bestRanked = sortedByRank[0];
    const secondBestRanked = sortedByRank[1];

    const explanations: string[] = [];

    if (bestRanked && secondBestRanked) {
      explanations.push(
        `${bestRanked.universityName} has the strongest global rank in your shortlist, ahead of ${secondBestRanked.universityName}.`
      );
    }

    const ieltsComparable = comparisonItems.filter(
      (item): item is ComparisonItem & { ieltsMin: number } =>
        item.ieltsMin !== undefined
    );
    if (ieltsComparable.length >= 2) {
      const sortedByIelts = [...ieltsComparable].sort(
        (a, b) => a.ieltsMin - b.ieltsMin
      );
      explanations.push(
        `${sortedByIelts[0].universityName} has the lowest IELTS requirement in this comparison, which may offer a more accessible language threshold.`
      );
    }

    const matchComparable = comparisonItems.filter(
      (item): item is ComparisonItem & { matchingScore: number } =>
        item.matchingScore !== undefined
    );
    if (matchComparable.length >= 2) {
      const sortedByMatch = [...matchComparable].sort(
        (a, b) => b.matchingScore - a.matchingScore
      );
      explanations.push(
        `${sortedByMatch[0].universityName} currently shows the strongest recommendation fit based on match score.`
      );
    }

    return explanations;
  }, [comparisonItems]);

  async function fetchRecommendations() {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        targetRank: String(targetRank),
        ieltsScore: String(ielts),
        country,
        riskProfile,
        countryPolicy: "hard_filter",
        limit: "5",
        version: "v3",
      });

      const json = await fetchAppJson<RecommendationResponse>(
        `/api/recommendations?${params.toString()}`
      );

      if (!json.success) {
        throw new Error("Recommendation request did not succeed.");
      }

      setData(json.data);
      setMetadata(json.metadata ?? null);
    } catch {
      setError("Unable to load recommendations. Please confirm the API server is running.");
      setData(null);
      setMetadata(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500">
              Decision Support
            </p>
            <h1 className="mt-2 text-4xl font-bold tracking-tight">
              Recommendation Engine
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600">
              Generate a shortlist using ranking targets, English requirements,
              and risk profile.
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:border-gray-300 hover:text-gray-900"
          >
            Back to rankings
          </Link>
        </div>

        {shortlistContext.length > 0 ? (
          <section className="mb-6 rounded-3xl border border-blue-100 bg-blue-50/70 p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900">
              Using your shortlist ({shortlistContext.length})
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              These shortlisted universities are carried into your recommendation workflow.
            </p>
            <ul className="mt-4 space-y-2">
              {shortlistContext.map((item) => (
                <li
                  key={item.canonicalUniversityId}
                  className="rounded-2xl border border-blue-200 bg-white px-4 py-3 text-sm font-medium text-blue-900"
                >
                  {item.universityName}
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <section className="mb-6 rounded-3xl border border-gray-200 bg-gray-50 p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-gray-900">
              No shortlist detected. Start from rankings.
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              Add universities to your shortlist on the rankings page, then return here to continue.
            </p>
            <Link
              href="/"
              className="mt-4 inline-flex items-center justify-center rounded-xl bg-gray-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-gray-800"
            >
              Back to rankings
            </Link>
          </section>
        )}

        {comparisonItems.length >= 2 ? (
          <section
            id="comparison"
            className="mb-6 rounded-3xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h2 className="text-xl font-semibold text-gray-900">Comparison</h2>
            <p className="mt-2 text-sm text-gray-500">
              Compare shortlisted universities side by side before generating a final recommendation.
            </p>

            <div className="mt-5 overflow-x-auto">
              <table className="w-full border-collapse">
                <thead className="bg-gray-50 text-sm text-gray-600">
                  <tr>
                    <th className="px-4 py-3 text-left">University</th>
                    <th className="px-4 py-3 text-left">Country</th>
                    <th className="px-4 py-3 text-left">Rank</th>
                    <th className="px-4 py-3 text-left">IELTS Min</th>
                    <th className="px-4 py-3 text-left">Matching Score</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonItems.map((item) => (
                    <tr
                      key={item.canonicalUniversityId}
                      className="border-t border-gray-100"
                    >
                      <td className="px-4 py-4 font-semibold text-gray-900">
                        {item.universityName}
                      </td>
                      <td className="px-4 py-4 text-gray-600">{item.country}</td>
                      <td
                        className={`px-4 py-4 ${
                          bestRank !== null && item.aggregatedRank === bestRank
                            ? "font-semibold text-emerald-700"
                            : "text-gray-700"
                        }`}
                      >
                        #{formatRank(item.aggregatedRank)}
                      </td>
                      <td
                        className={`px-4 py-4 ${
                          bestIelts !== null && item.ieltsMin === bestIelts
                            ? "font-semibold text-emerald-700"
                            : "text-gray-700"
                        }`}
                      >
                        {item.ieltsMin !== undefined
                          ? formatIelts(item.ieltsMin)
                          : "Not available"}
                      </td>
                      <td
                        className={`px-4 py-4 ${
                          bestMatchScore !== null &&
                          item.matchingScore === bestMatchScore
                            ? "font-semibold text-emerald-700"
                            : "text-gray-700"
                        }`}
                      >
                        {item.matchingScore !== undefined
                          ? formatScore(item.matchingScore)
                          : "Not available"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {comparisonExplanations.length > 0 ? (
              <div className="mt-6 rounded-2xl bg-gray-50 p-5">
                <h3 className="text-base font-semibold text-gray-900">
                  Explanation
                </h3>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-gray-700">
                  {comparisonExplanations.map((explanation) => (
                    <li key={explanation}>{explanation}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-gray-700">Country</span>
              <input
                className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="Country"
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-gray-700">IELTS Score</span>
              <input
                className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                type="number"
                step="0.5"
                value={ielts}
                onChange={(e) => setIelts(Number(e.target.value))}
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-gray-700">Target Rank</span>
              <input
                className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                type="number"
                value={targetRank}
                onChange={(e) => setTargetRank(Number(e.target.value))}
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-gray-700">Risk Profile</span>
              <select
                className="rounded-xl border border-gray-300 px-4 py-3 outline-none transition focus:border-gray-900"
                value={riskProfile}
                onChange={(e) => setRiskProfile(e.target.value)}
              >
                <option value="conservative">conservative</option>
                <option value="balanced">balanced</option>
                <option value="aggressive">aggressive</option>
              </select>
            </label>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              onClick={fetchRecommendations}
              className="inline-flex items-center justify-center rounded-xl bg-gray-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:bg-gray-400"
              disabled={loading}
            >
              {loading ? "Generating..." : "Generate Recommendations"}
            </button>
            <span className="text-sm text-gray-500">
              Results are fetched through the frontend recommendation service.
            </span>
          </div>
        </section>

        {error ? (
          <div className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
            {error}
          </div>
        ) : null}

        {data ? (
          <div className="mt-8 space-y-8">
            <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-gray-900">Summary</h2>
              <p className="mt-2 text-sm text-gray-500">
                A compact view of the assumptions and the current recommendation spread.
              </p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <SummaryItem label="Country" value={country} />
                <SummaryItem label="IELTS Score" value={formatIelts(ielts)} />
                <SummaryItem label="Target Rank" value={`#${formatRank(targetRank)}`} />
                <SummaryItem label="Risk Profile" value={riskProfile} />
                <SummaryItem label="Candidates" value={String(totalCount)} />
                <SummaryItem
                  label="Reach"
                  value={String(metadata?.counts?.reach ?? data.reach.length)}
                />
                <SummaryItem
                  label="Target"
                  value={String(metadata?.counts?.target ?? data.target.length)}
                />
                <SummaryItem
                  label="Safety"
                  value={String(metadata?.counts?.safety ?? data.safety.length)}
                />
              </div>
            </section>

            <Section
              title="Reach"
              description="Ambitious options with stronger ranking upside relative to your target."
              items={data.reach}
            />
            <Section
              title="Target"
              description="Balanced options with realistic fit and solid positioning."
              items={data.target}
            />
            <Section
              title="Safety"
              description="Lower-risk options that may be more accessible for your profile."
              items={data.safety}
            />
          </div>
        ) : null}
      </div>
    </main>
  );
}

export default function RecommendationPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-white text-gray-900">
          <div className="mx-auto max-w-5xl px-6 py-10">
            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 text-gray-600">
              Loading recommendation context...
            </div>
          </div>
        </main>
      }
    >
      <RecommendationPageContent />
    </Suspense>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-gray-50 px-4 py-3">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-1 font-medium text-gray-900">{value}</div>
    </div>
  );
}

function Section({
  title,
  description,
  items,
}: {
  title: string;
  description: string;
  items: RecommendationItem[];
}) {
  return (
    <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-2xl font-semibold text-gray-900">{title}</h2>
      <p className="mt-2 text-sm text-gray-500">{description}</p>

      {items.length === 0 ? (
        <div className="mt-5 rounded-xl bg-gray-50 p-4 text-gray-600">
          No universities available in this bucket.
        </div>
      ) : (
        <div className="mt-5 grid gap-4">
          {items.map((item) => (
            <div
              key={item.canonicalUniversityId}
              className="rounded-2xl border border-gray-200 p-5"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="text-xl font-semibold text-gray-900">
                    {item.universityName}
                  </div>
                  <div className="mt-1 text-sm text-gray-500">{item.country}</div>
                </div>
                <div className="rounded-xl bg-gray-50 px-4 py-3 text-right">
                  <div className="text-xs uppercase tracking-[0.18em] text-gray-500">
                    Match Score
                  </div>
                  <div className="mt-1 text-xl font-semibold text-gray-900">
                    {formatScore(item.matchingScore)}
                  </div>
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <SummaryItem
                  label="Aggregated Rank"
                  value={`#${formatRank(item.aggregatedRank)}`}
                />
                <SummaryItem label="IELTS Min" value={formatIelts(item.ieltsMin)} />
                <SummaryItem
                  label="Recommendation Confidence"
                  value={formatConfidence(item.recommendationConfidence)}
                />
              </div>

              <div className="mt-4 rounded-xl bg-gray-50 p-4 text-sm leading-6 text-gray-700">
                {item.explanation}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
