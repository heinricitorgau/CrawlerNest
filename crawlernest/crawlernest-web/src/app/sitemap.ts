import type { MetadataRoute } from "next";
import { fetchJson } from "@/lib/api";
import { getSiteUrl, absoluteUrl, universityPath } from "@/lib/site";

// Per request: the list follows the warehouse, and the build has no API to read.
export const dynamic = "force-dynamic";

type SitemapEntriesResponse = {
  success: boolean;
  data: { slug: string; lastModified: string | null }[] | null;
};

/** Public pages with content of their own. "/" stands for /rankings, which names it canonical. */
const STATIC_PATHS = ["/", "/subject-rankings", "/analytics", "/data-quality", "/about"];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const site = getSiteUrl();
  // No public URL, no sitemap: entries would point at localhost.
  if (!site) return [];

  const entries: MetadataRoute.Sitemap = STATIC_PATHS.map((path) => ({ url: absoluteUrl(path, site)! }));
  try {
    // Active universities with at least one ranking row; merged records are left out by the API.
    const response = await fetchJson<SitemapEntriesResponse>("/api/v1/universities/sitemap-entries");
    for (const row of response.data ?? []) {
      if (!row.slug) continue;
      entries.push({
        url: absoluteUrl(universityPath(row.slug), site)!,
        ...(row.lastModified ? { lastModified: row.lastModified } : {}),
      });
    }
  } catch (error) {
    // The static pages are still right; a crawler retries the rest on its next visit.
    console.error("sitemap: could not read university entries", error);
  }
  return entries;
}
