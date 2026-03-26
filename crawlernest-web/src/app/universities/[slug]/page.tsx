import Link from "next/link";

import { fetchJson } from "@/lib/api";
import { formatRank, formatRankingScore, formatScore } from "@/lib/format";
import type {
  UniversityDetail,
  UniversityDetailResponse,
} from "@/types/university";

type UniversityDetailPageProps = {
  params: Promise<{
    slug: string;
  }>;
};

function formatDate(value?: string): string | null {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString();
}

function formatValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  return String(value);
}

function renderAdmissionValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  return JSON.stringify(value);
}

function DetailCard({
  title,
  subtitle,
  children,
}: Readonly<{
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-3xl border border-gray-200 bg-white p-7 shadow-sm">
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
        {subtitle ? <p className="text-sm text-gray-500">{subtitle}</p> : null}
      </div>
      <div className="mt-5 border-t border-gray-100 pt-5">{children}</div>
    </section>
  );
}

function KeyValueGrid({
  items,
}: Readonly<{
  items: Array<{ label: string; value: string }>;
}>) {
  return (
    <dl className="grid gap-4 sm:grid-cols-2">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl bg-gray-50 px-4 py-3">
          <dt className="text-sm text-gray-500">{item.label}</dt>
          <dd className="mt-1 text-base font-medium text-gray-900">
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function getQuickInsight(rank: number | null | undefined) {
  if (rank === null || rank === undefined) {
    return {
      label: "Profile still forming",
      tone: "bg-gray-100 text-gray-700",
      description:
        "A clear positioning signal is not available yet because the aggregated rank is missing.",
      competitiveness:
        "Competitiveness cannot be interpreted confidently until ranking coverage improves.",
    };
  }

  if (rank <= 50) {
    return {
      label: "Top-tier university",
      tone: "bg-blue-100 text-blue-800",
      description:
        "This university currently sits in the top global tier based on aggregated ranking.",
      competitiveness:
        "This is a highly competitive university with strong global standing.",
    };
  }

  if (rank <= 150) {
    return {
      label: "Strong target university",
      tone: "bg-emerald-100 text-emerald-800",
      description:
        "This university appears to be a strong target with credible international positioning.",
      competitiveness:
        "This is a competitive option with solid global recognition.",
    };
  }

  return {
    label: "Safer option",
    tone: "bg-gray-100 text-gray-700",
    description:
      "This university may offer a more accessible pathway relative to higher-ranked options.",
    competitiveness:
      "This looks like a safer application option within a broader shortlist.",
  };
}

async function fetchUniversityDetail(
  slug: string
): Promise<UniversityDetailResponse> {
  return fetchJson<UniversityDetailResponse>(
    `/api/v1/universities/by-slug/${encodeURIComponent(slug)}`
  );
}

function NotFoundState({ slug }: Readonly<{ slug: string }>) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-8 text-center">
      <h2 className="text-xl font-semibold text-gray-900">University not found</h2>
      <p className="mt-3 text-gray-600">
        No university detail data is available for <span className="font-medium">{slug}</span>.
      </p>
    </div>
  );
}

function ErrorState({ message }: Readonly<{ message: string }>) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
      {message}
    </div>
  );
}

function SourceRankingsTable({
  rankings,
}: Readonly<{
  rankings: UniversityDetail["sourceRankings"];
}>) {
  if (rankings.length === 0) {
    return (
      <div className="rounded-xl bg-gray-50 p-4 text-gray-600">
        Source rankings not available yet.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-gray-50 text-gray-600">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Source</th>
            <th className="px-4 py-3 text-left font-medium">Rank</th>
            <th className="px-4 py-3 text-left font-medium">Score</th>
            <th className="px-4 py-3 text-left font-medium">Year</th>
          </tr>
        </thead>
        <tbody>
          {rankings.map((ranking, index) => (
            <tr
              key={`${ranking.source}-${ranking.year}-${index}`}
              className="border-t border-gray-100"
            >
              <td className="px-4 py-3 text-gray-900">{ranking.source}</td>
              <td className="px-4 py-3 text-gray-700">
                {formatRank(ranking.rank)}
              </td>
              <td className="px-4 py-3 text-gray-700">
                {formatRankingScore(ranking.score)}
              </td>
              <td className="px-4 py-3 text-gray-700">
                {formatValue(ranking.year)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AdmissionRequirementsSection({
  admissionRequirements,
}: Readonly<{
  admissionRequirements: UniversityDetail["admissionRequirements"];
}>) {
  const entries = Object.entries(admissionRequirements ?? {});

  if (entries.length === 0) {
    return (
      <div className="rounded-xl bg-gray-50 p-4 text-gray-600">
        Admission requirements not available yet.
      </div>
    );
  }

  return (
    <dl className="space-y-3">
      {entries.map(([key, value]) => (
        <div
          key={key}
          className="flex flex-col gap-1 rounded-xl bg-gray-50 px-4 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
        >
          <dt className="text-sm font-medium uppercase tracking-wide text-gray-500">
            {key}
          </dt>
          <dd className="text-gray-900 sm:text-right">
            {renderAdmissionValue(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default async function UniversityDetailPage({
  params,
}: UniversityDetailPageProps) {
  const { slug } = await params;
  let detail: UniversityDetail | null = null;
  let timestamp: string | undefined;
  let error: string | null = null;

  try {
    const response = await fetchUniversityDetail(slug);
    if (!response.success || !response.data) {
      detail = null;
    } else {
      detail = response.data;
      timestamp = response.metadata?.timestamp;
    }
  } catch {
    error =
      "Unable to load university details. Please confirm the API is running on http://localhost:8080.";
  }

  const insight = getQuickInsight(detail?.aggregatedRanking?.displayRank);

  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-6">
          <Link
            href="/"
            className="inline-flex items-center rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:border-gray-300 hover:text-gray-900"
          >
            Back to rankings
          </Link>
        </div>

        {error ? (
          <ErrorState message={error} />
        ) : !detail ? (
          <NotFoundState slug={slug} />
        ) : (
          <div className="space-y-7">
            <header className="rounded-[2rem] border border-gray-200 bg-gray-50 p-8 shadow-sm">
              <p className="text-sm font-medium uppercase tracking-[0.18em] text-gray-500">
                University Detail
              </p>
              <h1 className="mt-4 text-4xl font-bold tracking-tight text-gray-900">
                {detail.universityName}
              </h1>
              <p className="mt-2 text-lg text-gray-600">{detail.country}</p>
              <div className="mt-4 flex flex-col gap-2 text-sm text-gray-500 sm:flex-row sm:flex-wrap sm:gap-6">
                <span>Slug: /universities/{detail.slug}</span>
                {timestamp ? <span>Updated: {formatDate(timestamp)}</span> : null}
              </div>
              <p className="mt-4 text-sm text-gray-500">
                Data aggregated from multiple ranking sources
              </p>
            </header>

            <DetailCard
              title="Quick Insight"
              subtitle="A fast read on how this university may fit into a decision shortlist."
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <span
                    className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${insight.tone}`}
                  >
                    {insight.label}
                  </span>
                  <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600">
                    {insight.description}
                  </p>
                  <p className="mt-2 text-sm font-medium text-gray-800">
                    {insight.competitiveness}
                  </p>
                </div>
                <div className="rounded-2xl bg-gray-50 px-5 py-4 text-right">
                  <p className="text-xs uppercase tracking-[0.18em] text-gray-500">
                    Current Rank
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-gray-900">
                    {detail.aggregatedRanking?.displayRank !== null &&
                    detail.aggregatedRanking?.displayRank !== undefined
                      ? `#${formatRank(detail.aggregatedRanking.displayRank)}`
                      : "Not available"}
                  </p>
                </div>
              </div>
            </DetailCard>

            <DetailCard
              title="Ranking"
              subtitle="Aggregated ranking position and composite signal from the current dataset."
            >
              <KeyValueGrid
                items={[
                  {
                    label: "Display Rank",
                    value: detail.aggregatedRanking
                      ? `#${formatRank(detail.aggregatedRanking.displayRank)}`
                      : "Not available",
                  },
                  {
                    label: "Composite Score",
                    value: detail.aggregatedRanking
                      ? formatScore(detail.aggregatedRanking.compositeScore)
                      : "Not available",
                  },
                  {
                    label: "Ranking Year",
                    value: detail.aggregatedRanking
                      ? formatValue(detail.aggregatedRanking.rankingYear)
                      : "Not available",
                  },
                  {
                    label: "Method Version",
                    value: detail.aggregatedRanking
                      ? formatValue(
                          detail.aggregatedRanking.aggregationMethodVersion
                        )
                      : "Not available",
                  },
                ]}
              />
            </DetailCard>

            <DetailCard
              title="Source Rankings"
              subtitle="Underlying source-by-source ranking evidence behind the profile."
            >
              <SourceRankingsTable rankings={detail.sourceRankings} />
            </DetailCard>

            <DetailCard
              title="Admission Requirements"
              subtitle="Structured admissions information captured so far for this university."
            >
              <AdmissionRequirementsSection
                admissionRequirements={detail.admissionRequirements}
              />
            </DetailCard>

            <DetailCard
              title="Data Quality"
              subtitle="Confidence indicators for how reliable and complete the current profile appears."
            >
              <KeyValueGrid
                items={[
                  {
                    label: "Recommendation Confidence",
                    value: detail.dataQuality
                      ? formatValue(detail.dataQuality.recommendationConfidence)
                      : "Not available",
                  },
                  {
                    label: "Confidence Label",
                    value: detail.dataQuality
                      ? formatValue(detail.dataQuality.confidenceLabel)
                      : "Not available",
                  },
                  {
                    label: "Confidence Reason",
                    value: detail.dataQuality
                      ? formatValue(detail.dataQuality.confidenceReason)
                      : "Not available",
                  },
                ]}
              />
            </DetailCard>

            <DetailCard
              title="Next Step"
              subtitle="Use these actions to move from evaluation into an application decision workflow."
            >
              <div className="flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center justify-center rounded-xl border border-gray-200 bg-gray-100 px-5 py-3 text-sm font-semibold text-gray-400"
                >
                  Compare universities
                </button>
                <button
                  type="button"
                  className="inline-flex items-center justify-center rounded-xl bg-gray-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-gray-800"
                >
                  Add to shortlist
                </button>
                <button
                  type="button"
                  disabled
                  className="inline-flex items-center justify-center rounded-xl border border-gray-200 bg-gray-100 px-5 py-3 text-sm font-semibold text-gray-400"
                >
                  Explore similar universities
                </button>
              </div>
            </DetailCard>
          </div>
        )}
      </div>
    </main>
  );
}
