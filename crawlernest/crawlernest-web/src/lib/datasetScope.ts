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
 * `DatasetScope.DATASET_COVERAGE` in Java. ARWU reaches back to 2015; QS and THE
 * begin at 2025. The snapshot caveat names a source, so rendering it over every
 * held edition would tell a reader that ten editions with no QS row in them are
 * a snapshot of the QS published tables.
 */
export const DATASET_COVERAGE: Readonly<Record<string, readonly number[]>> = {
  QS: [2026, 2025],
  THE: [2026, 2025],
  ARWU: [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015],
};

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
