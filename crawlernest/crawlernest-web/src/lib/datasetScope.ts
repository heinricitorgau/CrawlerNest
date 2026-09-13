/**
 * What the warehouse holds, as the frontend sees it.
 *
 * Mirrors `DATASET_YEARS` and `DEFAULT_RANKING_YEAR` in
 * `crawlernest/core/dataset.py` and `DatasetScope.DATASET_YEARS` in Java.
 * Python's `test_caveat_contract` compares the three, so a change here needs the
 * same change there. Changing it is a data-migration step, not an edit.
 */

/** Every ranking edition the warehouse holds, newest first. */
export const DATASET_YEARS: readonly number[] = [2026];

/** The year a query uses when the caller names none: the newest edition held. */
export const DEFAULT_RANKING_YEAR: number = Math.max(...DATASET_YEARS);
