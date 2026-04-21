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
  gpaRequirement?: number;
  ieltsMin: number;
  toeflRequirement?: number;
  duolingoRequirement?: number;
  matchingScore: number;
  recommendationConfidence: number;
  explanation: string;
  admissionComposite?: {
    admissionReadiness: "strong" | "moderate" | "weak" | "unknown";
    admissionRisk: "low" | "medium" | "high" | "unknown";
    topConcerns: string[];
    topConcernLabels?: string[];
    reason?: string;
  };
  decisionOutput?: {
    decisionAction:
      | "apply_early"
      | "apply"
      | "apply_with_caution"
      | "improve_profile_first"
      | "monitor"
      | "insufficient_data";
    decisionStrength: "strong" | "moderate" | "weak" | "unknown";
    decisionReason: string;
    recommendedNextSteps: string[];
  };
  decisionStrategy?: {
    primaryStrategy: string;
    supportingActions: string[];
    riskMitigation: string[];
    timelineHint: string;
    reason: string;
  };
  surfaceSignals?: Array<{
    type: "ielts" | "toefl" | "gpa" | "duolingo" | "deadline";
    message?: string;
    urgency?: "high" | "medium" | "low" | "unknown";
    priorityLevel?: number;
    priorityScore?: number;
    emphasized?: boolean;
  }>;
  toeflFitHighlight?: {
    requiredScore: number;
    userScore: number;
    margin: number;
    fitBand: "comfortably_above" | "meets_requirement" | "slightly_below" | "well_below" | "unknown";
    fitUrgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  gpaFitHighlight?: {
    requiredScore: number;
    userScore: number;
    margin: number;
    fitBand: "comfortably_above" | "meets_requirement" | "slightly_below" | "well_below" | "unknown";
    fitUrgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  duolingoFitHighlight?: {
    requiredScore: number;
    userScore: number;
    margin: number;
    fitBand: "comfortably_above" | "meets_requirement" | "slightly_below" | "well_below" | "unknown";
    fitUrgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  ieltsFitHighlight?: {
    requiredScore: number;
    userScore: number;
    margin: number;
    fitBand: "comfortably_above" | "meets_requirement" | "slightly_below" | "well_below" | "unknown";
    fitUrgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  deadlineHighlight?: {
    date: string;
    type: string;
    urgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  recommendationExplain?: {
    fitScore: number;
    dimensions: {
      rankingFit: number;
      riskFit: number;
      languageFit: number;
      dataConfidence: number;
    };
    reasons: string[];
    warnings: string[];
  };
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
  const [toefl, setToefl] = useState<number | "">( "");
  const [gpa, setGpa] = useState<number | "">( "");
  const [duolingo, setDuolingo] = useState<number | "">( "");
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
      if (toefl !== "") {
        params.set("toeflScore", String(toefl));
      }
      if (gpa !== "") {
        params.set("gpaScore", String(gpa));
      }
      if (duolingo !== "") {
        params.set("duolingoScore", String(duolingo));
      }

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
    <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-[#6b7068]">
              Decision Support
            </p>
            <h1 className="mt-2 text-4xl font-bold tracking-tight text-[#1a3d2e]">
              Recommendation Engine
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#6b7068]">
              Generate a shortlist using ranking targets, English requirements,
              and risk profile.
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center rounded-full border border-[#e0ddd8] bg-white px-4 py-2 text-sm font-medium text-[#1a3d2e] shadow-sm transition hover:border-[#3d7a5a] hover:bg-[#e8f2ec]"
          >
            Back to rankings
          </Link>
        </div>

        {shortlistContext.length > 0 ? (
          <section className="mb-6 rounded-3xl border border-[#e0ddd8] bg-[#e8f2ec] p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-[#1a3d2e]">
              Using your shortlist ({shortlistContext.length})
            </h2>
            <p className="mt-2 text-sm text-[#6b7068]">
              These shortlisted universities are carried into your recommendation workflow.
            </p>
            <ul className="mt-4 space-y-2">
              {shortlistContext.map((item, index) => (
                <li
                  key={`${item.canonicalUniversityId}-${item.slug}-${index}`}
                  className="rounded-2xl border border-[#3d7a5a] bg-white px-4 py-3 text-sm font-medium text-[#1a3d2e]"
                >
                  {item.universityName}
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <section className="mb-6 rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-[#1a3d2e]">
              No shortlist detected. Start from rankings.
            </h2>
            <p className="mt-2 text-sm text-[#6b7068]">
              Add universities to your shortlist on the rankings page, then return here to continue.
            </p>
            <Link
              href="/"
              className="mt-4 inline-flex items-center justify-center rounded-full bg-[#1a3d2e] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
            >
              Back to rankings
            </Link>
          </section>
        )}

        {comparisonItems.length >= 2 ? (
          <section
            id="comparison"
            className="mb-6 rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm"
          >
            <h2 className="text-xl font-semibold text-[#1a3d2e]">Comparison</h2>
            <p className="mt-2 text-sm text-[#6b7068]">
              Compare shortlisted universities side by side before generating a final recommendation.
            </p>

            <div className="mt-5 overflow-x-auto">
              <table className="w-full border-collapse">
                <thead className="bg-[#f5f3ee] text-sm text-[#6b7068]">
                  <tr>
                    <th className="px-4 py-3 text-left">University</th>
                    <th className="px-4 py-3 text-left">Country</th>
                    <th className="px-4 py-3 text-left">Rank</th>
                    <th className="px-4 py-3 text-left">IELTS Min</th>
                    <th className="px-4 py-3 text-left">Matching Score</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonItems.map((item, index) => (
                    <tr
                      key={`${item.canonicalUniversityId}-${item.slug}-${index}`}
                      className="border-t border-[#e0ddd8]"
                    >
                      <td className="px-4 py-4 font-semibold text-[#1a1a1a]">
                        {item.universityName}
                      </td>
                      <td className="px-4 py-4 text-[#6b7068]">{item.country}</td>
                      <td
                        className={`px-4 py-4 ${
                          bestRank !== null && item.aggregatedRank === bestRank
                            ? "font-semibold text-[#1a3d2e]"
                            : "text-[#6b7068]"
                        }`}
                      >
                        #{formatRank(item.aggregatedRank)}
                      </td>
                      <td
                        className={`px-4 py-4 ${
                          bestIelts !== null && item.ieltsMin === bestIelts
                            ? "font-semibold text-[#1a3d2e]"
                            : "text-[#6b7068]"
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
                            ? "font-semibold text-[#1a3d2e]"
                            : "text-[#6b7068]"
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
              <div className="mt-6 rounded-2xl bg-[#f5f3ee] p-5">
                <h3 className="text-base font-semibold text-[#1a3d2e]">
                  Explanation
                </h3>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-[#6b7068]">
                  {comparisonExplanations.map((explanation) => (
                    <li key={explanation}>{explanation}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Country</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="Country"
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">IELTS Score</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                step="0.5"
                value={ielts}
                onChange={(e) => setIelts(Number(e.target.value))}
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Target Rank</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                value={targetRank}
                onChange={(e) => setTargetRank(Number(e.target.value))}
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Risk Profile</span>
              <select
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                value={riskProfile}
                onChange={(e) => setRiskProfile(e.target.value)}
              >
                <option value="conservative">conservative</option>
                <option value="balanced">balanced</option>
                <option value="aggressive">aggressive</option>
              </select>
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">TOEFL Score (optional)</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                value={toefl}
                onChange={(e) => setToefl(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 100"
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">GPA (optional)</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                step="0.1"
                value={gpa}
                onChange={(e) => setGpa(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 3.5"
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Duolingo Score (optional)</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                value={duolingo}
                onChange={(e) => setDuolingo(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 120"
              />
            </label>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              onClick={fetchRecommendations}
              className="inline-flex items-center justify-center rounded-full bg-[#1a3d2e] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42] disabled:cursor-not-allowed disabled:bg-[#c0bdb8]"
              disabled={loading}
            >
              {loading ? "Generating..." : "Generate Recommendations"}
            </button>
            <span className="text-sm text-[#6b7068]">
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
            <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-[#1a3d2e]">Summary</h2>
              <p className="mt-2 text-sm text-[#6b7068]">
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

function fitLevel(score: number | null | undefined) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "low";
  }
  if (score >= 80) {
    return "high";
  }
  if (score >= 60) {
    return "medium";
  }
  return "low";
}

export default function RecommendationPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
          <div className="mx-auto max-w-5xl px-6 py-10">
            <div className="rounded-2xl border border-[#e0ddd8] bg-white p-6 text-[#6b7068]">
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
    <div className="rounded-xl bg-[#f5f3ee] px-4 py-3">
      <div className="text-sm text-[#6b7068]">{label}</div>
      <div className="mt-1 font-medium text-[#1a1a1a]">{value}</div>
    </div>
  );
}

function AdmissionCompositeCard({
  composite,
}: {
  composite?: RecommendationItem["admissionComposite"];
}) {
  if (!composite) {
    return null;
  }

  const readinessTone =
    composite.admissionReadiness === "strong"
      ? "text-[#1a3d2e]"
      : composite.admissionReadiness === "moderate"
        ? "text-[#8a6116]"
        : composite.admissionReadiness === "weak"
          ? "text-[#8b3a2b]"
          : "text-[#6b7068]";

  const riskTone =
    composite.admissionRisk === "low"
      ? "text-[#1a3d2e]"
      : composite.admissionRisk === "medium"
        ? "text-[#8a6116]"
        : composite.admissionRisk === "high"
          ? "text-[#8b3a2b]"
          : "text-[#6b7068]";

  return (
    <div
      className="rounded-xl border border-[#e0ddd8] bg-[#fcfbf8] p-4"
      title={composite.reason || ""}
    >
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
        Admission Readiness
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <div className="text-xs text-[#6b7068]">Readiness</div>
          <div className={`mt-1 font-semibold capitalize ${readinessTone}`}>
            {composite.admissionReadiness}
          </div>
        </div>
        <div>
          <div className="text-xs text-[#6b7068]">Risk</div>
          <div className={`mt-1 font-semibold capitalize ${riskTone}`}>
            {composite.admissionRisk}
          </div>
        </div>
      </div>
      {(composite.topConcernLabels?.length || composite.topConcerns.length) > 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">
          Top concerns: {(composite.topConcernLabels && composite.topConcernLabels.length > 0
            ? composite.topConcernLabels
            : composite.topConcerns
          ).join(", ")}
        </div>
      ) : null}
    </div>
  );
}

function DecisionOutputCard({
  decision,
}: {
  decision?: RecommendationItem["decisionOutput"];
}) {
  if (!decision) {
    return null;
  }

  const strengthTone =
    decision.decisionStrength === "strong"
      ? "text-[#1a3d2e]"
      : decision.decisionStrength === "moderate"
        ? "text-[#8a6116]"
        : decision.decisionStrength === "weak"
          ? "text-[#8b3a2b]"
          : "text-[#6b7068]";

  const actionLabel = decision.decisionAction.replace(/_/g, " ");

  return (
    <div className="rounded-xl border border-[#e0ddd8] bg-[#fffdf8] p-4">
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
        Suggested Action
      </div>
      <div className="mt-3 text-sm text-[#6b7068]">Action</div>
      <div className="mt-1 font-semibold capitalize text-[#1a1a1a]">{actionLabel}</div>
      <div className="mt-3 text-sm text-[#6b7068]">Confidence</div>
      <div className={`mt-1 font-semibold capitalize ${strengthTone}`}>
        {decision.decisionStrength}
      </div>
      <div className="mt-3 text-sm leading-6 text-[#6b7068]">{decision.decisionReason}</div>
      {decision.recommendedNextSteps.length > 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">
          {decision.recommendedNextSteps.slice(0, 3).map((step) => (
            <div key={step}>- {step}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function DecisionStrategyCard({
  strategy,
}: {
  strategy?: RecommendationItem["decisionStrategy"];
}) {
  if (!strategy) {
    return null;
  }

  return (
    <div
      className="rounded-xl border border-[#e0ddd8] bg-[#fcfbf8] p-4"
      title={strategy.reason}
    >
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
        Application Strategy
      </div>
      <div className="mt-3 text-sm text-[#6b7068]">Primary</div>
      <div className="mt-1 font-semibold text-[#1a1a1a]">{strategy.primaryStrategy}</div>
      {strategy.supportingActions.length > 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">
          <div className="mb-1">Actions</div>
          {strategy.supportingActions.slice(0, 3).map((step) => (
            <div key={step}>• {step}</div>
          ))}
        </div>
      ) : null}
      {strategy.riskMitigation.length > 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">
          <div className="mb-1">Risk Mitigation</div>
          {strategy.riskMitigation.slice(0, 3).map((step) => (
            <div key={step}>• {step}</div>
          ))}
        </div>
      ) : null}
      <div className="mt-3 text-sm text-[#6b7068]">Timeline</div>
      <div className="mt-1 text-sm leading-6 text-[#6b7068]">{strategy.timelineHint}</div>
    </div>
  );
}

function DeadlineBadge({
  highlight,
  className,
}: {
  highlight?: RecommendationItem["deadlineHighlight"];
  className?: string;
}) {
  if (!highlight) {
    return null;
  }

  const urgencyStyle =
    highlight.urgency === "high"
      ? {
          icon: "🔴",
          tone: "border-[#f1c5bc] bg-[#fbefeb] text-[#8b3a2b]",
        }
      : highlight.urgency === "medium"
        ? {
            icon: "🟡",
            tone: "border-[#ead9a7] bg-[#fbf5e4] text-[#8a6116]",
          }
        : highlight.urgency === "low"
          ? {
              icon: "🟢",
              tone: "border-[#cfe5d7] bg-[#edf7f1] text-[#1a3d2e]",
            }
          : {
              icon: "⚪",
              tone: "border-[#d7d5d0] bg-[#f5f3ee] text-[#6b7068]",
            };

  const typeLabel =
    highlight.type && highlight.type !== "unknown"
      ? `${highlight.type.charAt(0).toUpperCase()}${highlight.type.slice(1)} Deadline`
      : "Deadline";

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${urgencyStyle.tone} ${className ?? ""}`}
      title={highlight.reason || highlight.message}
    >
      <span aria-hidden="true">{urgencyStyle.icon}</span>
      <span>{typeLabel}</span>
      <span className="text-current/70">·</span>
      <span>{highlight.date}</span>
    </div>
  );
}

function IeltsFitBadge({
  highlight,
  className,
}: {
  highlight?: RecommendationItem["ieltsFitHighlight"];
  className?: string;
}) {
  return <RequirementFitBadge highlight={highlight} className={className} />;
}

function RequirementFitBadge({
  highlight,
  className,
}: {
  highlight?:
    | RecommendationItem["ieltsFitHighlight"]
    | RecommendationItem["toeflFitHighlight"]
    | RecommendationItem["gpaFitHighlight"]
    | RecommendationItem["duolingoFitHighlight"];
  className?: string;
}) {
  if (!highlight) {
    return null;
  }

  const urgencyStyle =
    highlight.fitUrgency === "high"
      ? {
          icon: "🔴",
          tone: "border-[#f1c5bc] bg-[#fbefeb] text-[#8b3a2b]",
        }
      : highlight.fitUrgency === "medium"
        ? {
            icon: "🟡",
            tone: "border-[#ead9a7] bg-[#fbf5e4] text-[#8a6116]",
          }
        : highlight.fitUrgency === "low"
          ? {
              icon: "🟢",
              tone: "border-[#cfe5d7] bg-[#edf7f1] text-[#1a3d2e]",
            }
          : {
              icon: "⚪",
              tone: "border-[#d7d5d0] bg-[#f5f3ee] text-[#6b7068]",
            };

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${urgencyStyle.tone} ${className ?? ""}`}
      title={highlight.reason || highlight.message}
    >
      <span aria-hidden="true">{urgencyStyle.icon}</span>
      <span>{highlight.message}</span>
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
    <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
      <h2 className="text-2xl font-semibold text-[#1a3d2e]">{title}</h2>
      <p className="mt-2 text-sm text-[#6b7068]">{description}</p>

      {items.length === 0 ? (
        <div className="mt-5 rounded-xl bg-[#f5f3ee] p-4 text-[#6b7068]">
          No universities available in this bucket.
        </div>
      ) : (
        <div className="mt-5 grid gap-4">
          {items.map((item, index) => (
            <div
              key={`${title.toLowerCase()}-${item.canonicalUniversityId}-${index}`}
              className="rounded-2xl border border-[#e0ddd8] p-5"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="text-xl font-semibold text-[#1a1a1a]">
                    {item.universityName}
                  </div>
                  <div className="mt-1 text-sm text-[#6b7068]">{item.country}</div>
                </div>
                <div className="rounded-xl bg-[#f5f3ee] px-4 py-3 text-right">
                  <div className="text-xs uppercase tracking-[0.18em] text-[#6b7068]">
                    Fit Score
                  </div>
                  <div className="mt-1 flex items-center justify-end gap-2">
                    <div className="text-xl font-semibold text-[#1a3d2e]">
                      {formatScore(item.recommendationExplain?.fitScore ?? item.matchingScore)}
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] ${
                        fitLevel(item.recommendationExplain?.fitScore ?? item.matchingScore) === "high"
                          ? "bg-[#e8f2ec] text-[#1a3d2e]"
                          : fitLevel(item.recommendationExplain?.fitScore ?? item.matchingScore) === "medium"
                            ? "bg-[#f3ecd6] text-[#8a6116]"
                            : "bg-[#f3e7e4] text-[#8b3a2b]"
                      }`}
                    >
                      {fitLevel(item.recommendationExplain?.fitScore ?? item.matchingScore)}
                    </span>
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

              {item.ieltsFitHighlight || item.toeflFitHighlight || item.gpaFitHighlight || item.duolingoFitHighlight || item.deadlineHighlight ? (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {(item.surfaceSignals && item.surfaceSignals.length > 0
                    ? item.surfaceSignals
                    : [
                        { type: "ielts", emphasized: true },
                        { type: "toefl", emphasized: true },
                        { type: "gpa", emphasized: true },
                        { type: "duolingo", emphasized: true },
                        { type: "deadline", emphasized: true },
                      ]
                  ).map((signal) => {
                    const isPrimary = signal.emphasized !== false;
                    const badgeClass = isPrimary ? "" : "opacity-65";
                    const key = `${item.canonicalUniversityId}-${signal.type}`;

                    if (signal.type === "ielts" && item.ieltsFitHighlight) {
                      return <IeltsFitBadge key={key} highlight={item.ieltsFitHighlight} className={badgeClass} />;
                    }
                    if (signal.type === "toefl" && item.toeflFitHighlight) {
                      return <RequirementFitBadge key={key} highlight={item.toeflFitHighlight} className={badgeClass} />;
                    }
                    if (signal.type === "gpa" && item.gpaFitHighlight) {
                      return <RequirementFitBadge key={key} highlight={item.gpaFitHighlight} className={badgeClass} />;
                    }
                    if (signal.type === "duolingo" && item.duolingoFitHighlight) {
                      return <RequirementFitBadge key={key} highlight={item.duolingoFitHighlight} className={badgeClass} />;
                    }
                    if (signal.type === "deadline" && item.deadlineHighlight) {
                      return <DeadlineBadge key={key} highlight={item.deadlineHighlight} className={badgeClass} />;
                    }
                    return null;
                  })}
                </div>
              ) : null}

              {item.admissionComposite ? (
                <div className="mt-4">
                  <AdmissionCompositeCard composite={item.admissionComposite} />
                </div>
              ) : null}

              {item.decisionOutput ? (
                <div className="mt-4">
                  <DecisionOutputCard decision={item.decisionOutput} />
                </div>
              ) : null}

              {item.decisionStrategy ? (
                <div className="mt-4">
                  <DecisionStrategyCard strategy={item.decisionStrategy} />
                </div>
              ) : null}

              <div className="mt-4 rounded-xl bg-[#f5f3ee] p-4 text-sm leading-6 text-[#6b7068]">
                {item.explanation}
              </div>

              {item.recommendationExplain && (
                <div className="mt-4 rounded-xl border border-[#e0ddd8] bg-white p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
                    Why This Fits You
                  </div>
                  <div className="mt-3 space-y-2 text-sm text-[#415046]">
                    {item.recommendationExplain.reasons.map((reason) => (
                      <div key={reason}>✓ {reason}</div>
                    ))}
                  </div>

                  <div className="mt-4 text-xs font-semibold uppercase tracking-[0.14em] text-[#8b3a2b]">
                    Watch Out
                  </div>
                  <div className="mt-3 space-y-2 text-sm text-[#6b554f]">
                    {item.recommendationExplain.warnings.length > 0 ? (
                      item.recommendationExplain.warnings.map((warning) => (
                        <div key={warning}>⚠ {warning}</div>
                      ))
                    ) : (
                      <div>⚠ No major warnings detected from current data.</div>
                    )}
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-4">
                    <SummaryItem label="Ranking Fit" value={formatScore(item.recommendationExplain.dimensions.rankingFit)} />
                    <SummaryItem label="Risk Fit" value={formatScore(item.recommendationExplain.dimensions.riskFit)} />
                    <SummaryItem label="Language Fit" value={formatScore(item.recommendationExplain.dimensions.languageFit)} />
                    <SummaryItem label="Data Confidence" value={formatScore(item.recommendationExplain.dimensions.dataConfidence)} />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
