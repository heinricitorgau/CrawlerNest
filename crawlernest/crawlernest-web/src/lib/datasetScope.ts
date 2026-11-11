/**
 * What the warehouse holds, as the frontend sees it.
 *
 * Mirrors `DATASET_YEARS` and `DEFAULT_RANKING_YEAR` in
 * `crawlernest/core/dataset.py` and `DatasetScope.DATASET_YEARS` in Java.
 * Python's `test_caveat_contract` compares the three, so a change here needs the
 * same change there. Changing it is a data-migration step, not an edit.
 */

/**
 * Which editions each source actually covers, newest first.
 *
 * Mirrors `DATASET_COVERAGE` in `crawlernest/core/dataset.py` and
 * `DatasetScope.DATASET_COVERAGE` in Java. ARWU and THE reach back to 2015; QS has
 * gaps (no 2015, 2016, 2021). The snapshot caveat names a source, so rendering it over every
 * held edition would tell a reader that ten editions with no QS row in them are
 * a snapshot of the QS published tables.
 */
export const DATASET_COVERAGE: Readonly<Record<string, readonly number[]>> = {
  QS: [2026, 2025, 2024, 2023, 2022, 2020, 2019, 2018, 2017],
  THE: [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015],
  ARWU: [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015],
};

/**
 * The (source, edition) pairs the warehouse holds that were not crawled from the source
 * directly, with the date of the Internet Archive capture the ranks were read from. An
 * edition in `DATASET_COVERAGE` and not here was crawled live.
 *
 * Mirrors `DATASET_ARCHIVE_EDITIONS` in `crawlernest/core/dataset.py`; `test_caveat_contract`
 * compares the literals, and the dates with the archive manifest and its ingest receipts.
 */
export const DATASET_ARCHIVE_EDITIONS: Readonly<Record<string, Readonly<Record<number, string>>>> = {
  QS: { 2024: "2026-03-29", 2023: "2026-05-10", 2022: "2022-04-09", 2020: "2021-02-16", 2019: "2021-02-21", 2018: "2021-02-12", 2017: "2022-04-26" },
};

/** The capture date of an archive-sourced edition, or null when it was crawled live. */
export function archiveCaptureDate(source: string, year: number): string | null {
  return DATASET_ARCHIVE_EDITIONS[source]?.[year] ?? null;
}

/** One source's editions that were crawled from it directly, newest first. */
export function liveYears(source: string): number[] {
  return (DATASET_COVERAGE[source] ?? []).filter((year) => archiveCaptureDate(source, year) === null);
}

/** Ranking sources ingested, widest first. Mirrors `DATASET_SOURCES` in Python. */
export const DATASET_SOURCES: readonly string[] = ["QS", "THE", "ARWU"];

/**
 * Every ranking edition the warehouse holds, newest first.
 *
 * The union of `DATASET_COVERAGE`, written out because `test_caveat_contract`
 * reads this literal and compares it with the Python and Java ones.
 */
export const DATASET_YEARS: readonly number[] = [
  2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015,
];

/**
 * The sources holding ranks for an edition, in `DATASET_SOURCES` order. Empty
 * for an edition the warehouse does not hold.
 */
export function sourcesForYear(year: number): string[] {
  return DATASET_SOURCES.filter((source) => (DATASET_COVERAGE[source] ?? []).includes(year));
}

/**
 * Which editions hold *subject* ranking rows, per source.
 *
 * Separate from `DATASET_COVERAGE` because subject coverage is not world-ranking
 * coverage: `warehouse.subject_ranking_record` holds 1,068 rows, all QS, all for
 * 2026. QS's world ranks reach back to 2025 and ARWU's to 2015, and neither
 * implies a subject table.
 *
 * Without this the subject page offered every edition the warehouse holds and
 * eleven of the twelve returned nothing, under a heading that still read
 * "2018 edition · QS" -- a source attributed to an edition it has no subject row
 * in.
 */
export const SUBJECT_DATASET_COVERAGE: Readonly<Record<string, readonly number[]>> = {
  QS: [2026],
};

/** Editions with subject ranking rows, newest first. */
export const SUBJECT_DATASET_YEARS: readonly number[] = [2026];

/** The sources holding subject rows for an edition; empty when none do. */
export function subjectSourcesForYear(year: number): string[] {
  return DATASET_SOURCES.filter(
    (source) => (SUBJECT_DATASET_COVERAGE[source] ?? []).includes(year),
  );
}

/** True when the edition has subject ranking rows at all. */
export function hasSubjectData(year: number): boolean {
  return subjectSourcesForYear(year).length > 0;
}

/** The year a query uses when the caller names none: the newest edition held. */
export const DEFAULT_RANKING_YEAR: number = Math.max(...DATASET_YEARS);

/** The query parameter that carries the selected edition, so a shared link keeps it. */
export const YEAR_QUERY_PARAM = "year";

export type SelectedYear = {
  /** The edition to read: always one the warehouse holds. */
  year: number;
  /** What the URL asked for, verbatim; null when it named none. */
  requested: string | null;
  /** False when the URL named an edition that is not held, so `year` is the default instead. */
  requestedHeld: boolean;
};

/**
 * The edition a page should read for a `?year=` value. Same rule as
 * `DatasetScope.resolveRankingYear` in Java and `resolve_ranking_year` in Python,
 * except that where the API reads nothing for an unheld year, a page falls back to
 * the default and says so -- an empty table with no explanation reads as "no
 * universities", not as "no such edition".
 */
export function resolveSelectedYear(raw: string | null | undefined): SelectedYear {
  const requested = raw == null || raw.trim() === "" ? null : raw.trim();
  if (requested === null) {
    return { year: DEFAULT_RANKING_YEAR, requested: null, requestedHeld: true };
  }
  const parsed = /^\d{4}$/.test(requested) ? Number(requested) : NaN;
  if (DATASET_YEARS.includes(parsed)) {
    return { year: parsed, requested, requestedHeld: true };
  }
  return { year: DEFAULT_RANKING_YEAR, requested, requestedHeld: false };
}

/** `href` with `?year=` set, keeping any query it already has. */
export function hrefWithYear(href: string, year: number): string {
  const [path, query = ""] = href.split("?", 2);
  const params = new URLSearchParams(query);
  params.set(YEAR_QUERY_PARAM, String(year));
  return `${path}?${params.toString()}`;
}

/**
 * An in-app link that keeps the edition being viewed. The default edition needs
 * no parameter -- a plain link already shows it -- so only another edition is
 * written into the URL. One rule for every link between year-aware pages.
 */
export function hrefForEdition(href: string, year: number): string {
  return year === DEFAULT_RANKING_YEAR ? href : hrefWithYear(href, year);
}
