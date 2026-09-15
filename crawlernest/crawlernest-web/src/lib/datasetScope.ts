/**
 * What the warehouse holds, as the frontend sees it.
 *
 * Mirrors `DATASET_YEARS` and `DEFAULT_RANKING_YEAR` in
 * `crawlernest/core/dataset.py` and `DatasetScope.DATASET_YEARS` in Java.
 * Python's `test_caveat_contract` compares the three, so a change here needs the
 * same change there. Changing it is a data-migration step, not an edit.
 */

/** Every ranking edition the warehouse holds, newest first. */
export const DATASET_YEARS: readonly number[] = [2026, 2025];

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
