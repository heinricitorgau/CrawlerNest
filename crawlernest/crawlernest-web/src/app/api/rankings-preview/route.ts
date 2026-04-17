import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

// Deprecated: preview-only workaround route retained for manual experiments.
// Main rankings flow must not use this route.
// Canonical production-like path is /api/rankings -> /api/v1/rankings.

const BACKEND_PREVIEW_URL = "http://localhost:8080/api/v1/preview/universities";

// Demo universities: MIT, Oxford, Harvard, Stanford, Cambridge
const DEMO_CANONICAL_IDS = [1, 3, 4, 6, 5];

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "") || "mit";
}

function toNumber(value: unknown, fallback: number): number {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}


// 根據排名計算 compositeScore
function calculateCompositeScore(bestRank: number | null | undefined): number {
  if (bestRank === null || bestRank === undefined || bestRank <= 0) {
    return 0;
  }
  return 100 - bestRank * 2;
}

function transformPreviewToRankingItem(preview: Record<string, any>): Record<string, any> {
  const rankingSummary = preview?.rankingSummary ?? {};
  const admissionSummary = preview?.admissionSummary ?? {};
  const identitySummary = preview?.identitySummary ?? {};
  const universityName = String(preview?.universityDisplayName ?? preview?.normalizedUniversityName ?? "Unknown");
  const countries = Array.isArray(admissionSummary?.countries) ? admissionSummary.countries : [];
  const country = countries.length > 0 ? String(countries[0]) : (identitySummary?.countryName || "Unknown");

  // 從 rankingSummary 取 bestRank
  const bestRank = rankingSummary?.bestRank;
  const aggregatedRank = typeof bestRank === "number" && bestRank > 0 ? bestRank : 999;
  const compositeScore = calculateCompositeScore(bestRank);

  return {
    canonicalUniversityId: toNumber(preview?.canonicalUniversityId, 0),
    universityName,
    country,
    aggregatedRank,
    globalRank: aggregatedRank,
    scopeRank: aggregatedRank,
    compositeScore,
    rankingYear: toNumber(rankingSummary?.bestRankingYear, 2026),
    primarySource: String(rankingSummary?.bestSource ?? "Preview"),
    sourceCount: toNumber(rankingSummary?.sourceCount, 1),
    slug: String(identitySummary?.canonicalSlug ?? slugify(universityName)),
  };
}

export async function GET(request: NextRequest) {
  try {
    const items: Record<string, unknown>[] = [];
    const errors: string[] = [];

    // Fetch all demo universities
    for (const canonicalId of DEMO_CANONICAL_IDS) {
      try {
        const previewUrl = new URL(BACKEND_PREVIEW_URL);
        previewUrl.searchParams.set("canonicalUniversityId", String(canonicalId));

        const response = await fetch(previewUrl.toString(), {
          cache: "no-store",
        });

        if (!response.ok) {
          errors.push(`Failed to fetch university ${canonicalId}: HTTP ${response.status}`);
          continue;
        }

        const body = await response.json();
        const preview = body?.data ?? {};

        if (preview?.canonicalUniversityId) {
          items.push(transformPreviewToRankingItem(preview));
        }
      } catch (err) {
        errors.push(`Error fetching university ${canonicalId}: ${err instanceof Error ? err.message : "Unknown error"}`);
      }
    }

    // Sort by aggregated rank
    items.sort((a, b) => (a.aggregatedRank as number) - (b.aggregatedRank as number));

    // countryOptions: 取出所有出現過的國家
    const countrySet = new Set<string>();
    for (const item of items) {
      const country = String(item.country ?? "");
      if (country && country !== "Unknown") countrySet.add(country);
    }
    const countryOptions = Array.from(countrySet).sort().map((name) => ({ code: name, name, count: items.filter(i => String(i.country ?? "") === name).length }));

    if (items.length === 0) {
      return NextResponse.json(
        {
          success: false,
          error: "Unable to load preview rankings. No data available.",
          details: errors,
        },
        {
          status: 502,
          headers: {
            "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
          },
        }
      );
    }

    return NextResponse.json(
      {
        success: true,
        data: {
          items,
        },
        metadata: {
          totalCount: items.length,
          page: 1,
          pageSize: 20,
          countryOptions,
        },
      },
      {
        headers: {
          "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
          "X-CrawlerNest-Deprecated": "true",
        },
      }
    );
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error: "Unable to load preview rankings. Preview backend request failed.",
      },
      {
        status: 502,
        headers: {
          "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
          "X-CrawlerNest-Deprecated": "true",
        },
      }
    );
  }
}
