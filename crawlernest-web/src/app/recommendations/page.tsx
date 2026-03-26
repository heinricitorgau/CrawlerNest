"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { fetchAppJson } from "@/lib/api";
import {
  formatIelts,
  formatRank,
  formatScore,
} from "@/lib/format";

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

function formatConfidence(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }

  if (value <= 1) {
    return `${Math.round(value * 100)}%`;
  }

  return `${Math.round(value)}%`;
}

export default function RecommendationPage() {
  const [country, setCountry] = useState("United Kingdom");
  const [ielts, setIelts] = useState(6.5);
  const [targetRank, setTargetRank] = useState(100);
  const [riskProfile, setRiskProfile] = useState("balanced");

  const [data, setData] = useState<RecommendationResponse["data"] | null>(null);
  const [metadata, setMetadata] = useState<RecommendationResponse["metadata"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalCount = useMemo(() => {
    if (metadata?.candidate_count !== undefined) {
      return metadata.candidate_count;
    }

    if (!data) {
      return 0;
    }

    return data.reach.length + data.target.length + data.safety.length;
  }, [data, metadata]);

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
