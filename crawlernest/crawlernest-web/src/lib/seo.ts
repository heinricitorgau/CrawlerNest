import { DATASET_SOURCES } from "@/lib/datasetScope";
import type { UniversityDetail } from "@/types/university";

/** "QS, THE and ARWU", from the ingested set rather than a list written into copy. */
export function sourceListText(sources: readonly string[] = DATASET_SOURCES): string {
  if (sources.length <= 1) return sources.join("");
  return `${sources.slice(0, -1).join(", ")} and ${sources[sources.length - 1]}`;
}

/** The site-wide description. No university count: it changes with every backfill. */
export function siteDescription(): string {
  return (
    `University rankings from ${sourceListText()}, side by side by edition, ` +
    "with each rank shown as the source printed it and every gap in our coverage disclosed."
  );
}

/**
 * A university page's meta description, from the warehouse rows the page shows.
 *
 * Each rank is the one the source printed ("=122", "151-200"). A source the warehouse
 * holds no rank for in this edition is named as *our* gap, never as the source
 * declining to rank the university: coverage is partial. Nothing here comes from the
 * Wikipedia introduction, which is not warehouse data.
 */
export function universityDescription(detail: UniversityDetail): string {
  const edition = detail.rankingYear ?? null;
  const ranked = new Map<string, string>();
  for (const row of detail.sourceRankings ?? []) {
    if (edition != null && row.year != null && row.year !== edition) continue;
    if (row.rank == null && !row.rankDisplay) continue;
    if (!ranked.has(row.source)) ranked.set(row.source, row.rankDisplay || String(row.rank));
  }

  const where = detail.country ? `${detail.universityName}, ${detail.country}` : detail.universityName;
  const editionText = edition != null ? ` ${edition}` : "";
  const held = DATASET_SOURCES.filter((source) => ranked.has(source));
  const missing = DATASET_SOURCES.filter((source) => !ranked.has(source));

  if (held.length === 0) {
    return `${where}. CrawlerNest holds no${editionText} ranking for it from ${sourceListText()}.`;
  }
  const ranks = held.map((source) => `${source} ${ranked.get(source)}`).join(", ");
  const gap = missing.length > 0 ? ` CrawlerNest holds no ${sourceListText(missing)} rank for this edition.` : "";
  return `${where}.${editionText} rankings as each source printed them: ${ranks}.${gap}`;
}
