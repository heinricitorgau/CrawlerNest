/**
 * Words for one source's rank change, derived only from what the API computed.
 *
 * The API (clawer.service.SourceRankDelta, mirroring crawlernest/core/rank_delta.py)
 * decides whether a movement exists and in which direction. This module never
 * re-derives a direction from the sign, never subtracts ranks itself, and takes no
 * composite or display rank -- so a trend claim on the page can only say what the
 * evidence says.
 *
 * Direction words are "up"/"down"/"unchanged", not "improved"/"declined": a rank
 * moving is a fact about a table, not a verdict on a university.
 */
import type { RankDelta, UniversityRanking } from "@/types/university";

/**
 * `entity_changed` is its own tone rather than a kind of `withheld`: the other
 * withheld reasons are gaps in our data, while this one says the two editions
 * describe different institutions, and a reader should not take it for "no data".
 */
export type RankDeltaTone = "up" | "down" | "neutral" | "withheld" | "entity_changed";

export type RankDeltaPresentation = {
  /** Short cell text, e.g. "↑ 3 since 2025" or "↑ 601–610 → 551–560". */
  label: string;
  /** Full sentence for a title attribute or screen readers. */
  detail: string;
  tone: RankDeltaTone;
};

/** Why no movement is shown, keyed by the API's reason codes. */
export const RANK_DELTA_REASON_TEXT: Record<string, string> = {
  single_year_dataset: "Only one edition of this source is held, so there is nothing to compare against.",
  no_prior_row:
    "No rank from this source is held for the prior edition. That is a gap in this platform's data, not a statement that the source did not rank it.",
  no_current_row: "No rank from this source is held for this edition.",
  entity_changed:
    "The institution or its entry in this source changed between editions: a merger, split or rename, or the source listing it under a different entry. The two ranks do not describe the same entity, so no change is shown.",
  suspicious_merge: "The match between this source's entry and this university was flagged for review in one of the editions.",
  rank_display_missing:
    "The printed rank for one of the editions was not recorded, and the stored position alone would overstate its precision.",
  composite_rank_not_comparable:
    "A composite rank moves when source coverage changes, so it is not compared across editions.",
};

/**
 * Cell text for `entity_changed`. Not "Merged": the code also covers a split, a
 * rename and a source re-keying its entry, and the API does not say which.
 */
export const ENTITY_CHANGED_LABEL = "Entity changed";

const FALLBACK_REASON = "No rank change is available for this source.";
const BAND_NOTE = "the source publishes a band, not an exact rank";

function places(n: number): string {
  return `${n} ${n === 1 ? "place" : "places"}`;
}

/** "between 51 and 149 places" or "at least 1 place" when one side is open. */
function span(lowest: number | null, highest: number | null): string {
  if (lowest != null && highest != null) return `between ${lowest} and ${highest} places`;
  return `at least ${places(lowest ?? highest ?? 0)}`;
}

/**
 * "601–610 → 551–560": both editions as the source printed them. Null unless both
 * printed ranks are known, so an interval is never assembled from a lower bound.
 */
export function rankInterval(priorRankDisplay: string | null | undefined, rankDisplay: string | null | undefined): string | null {
  const prior = priorRankDisplay?.trim();
  const current = rankDisplay?.trim();
  return prior && current ? `${prior} → ${current}` : null;
}

export function presentRankDelta(
  row: Pick<UniversityRanking, "rankDelta" | "rankDeltaReason" | "rankDisplay">,
): RankDeltaPresentation {
  const reason = row.rankDeltaReason ?? "";
  // Checked before the delta: if the API ever sent movement alongside this reason,
  // the reason is the safer of the two to believe.
  if (reason === "entity_changed") {
    return { label: ENTITY_CHANGED_LABEL, detail: RANK_DELTA_REASON_TEXT.entity_changed, tone: "entity_changed" };
  }

  const delta: RankDelta | null = row.rankDelta ?? null;
  if (!delta || !delta.direction) {
    return { label: "—", detail: RANK_DELTA_REASON_TEXT[reason] ?? FALLBACK_REASON, tone: "withheld" };
  }

  const since = delta.priorYear != null ? ` since ${delta.priorYear}` : "";
  const was = delta.priorRankDisplay ? ` (was ${delta.priorRankDisplay})` : "";

  if (delta.value != null) {
    const magnitude = Math.abs(delta.value);
    if (delta.direction === "up") {
      return { label: `↑ ${magnitude}${since}`, detail: `Up ${places(magnitude)}${since}${was}.`, tone: "up" };
    }
    if (delta.direction === "down") {
      return { label: `↓ ${magnitude}${since}`, detail: `Down ${places(magnitude)}${since}${was}.`, tone: "down" };
    }
    return { label: `No change${since}`, detail: `Same rank as the prior edition${was}.`, tone: "neutral" };
  }

  // Banded: only an interval is known, so the cell shows the printed ranks, not a
  // number of places. Up means both bounds are negative.
  const interval = rankInterval(delta.priorRankDisplay, row.rankDisplay);
  const intervalNote = interval ? ` (${interval})` : was;
  if (delta.direction === "up") {
    const nearest = delta.max != null ? Math.abs(delta.max) : null;
    const farthest = delta.min != null ? Math.abs(delta.min) : null;
    return {
      label: interval ? `↑ ${interval}` : `↑ banded${since}`,
      detail: `Up ${span(nearest, farthest)}${since}${intervalNote}; ${BAND_NOTE}.`,
      tone: "up",
    };
  }
  if (delta.direction === "down") {
    return {
      label: interval ? `↓ ${interval}` : `↓ banded${since}`,
      detail: `Down ${span(delta.min, delta.max)}${since}${intervalNote}; ${BAND_NOTE}.`,
      tone: "down",
    };
  }
  return {
    label: interval ?? `Within band${since}`,
    detail: `The bands in both editions overlap, so the direction of any movement is unknown${intervalNote}; ${BAND_NOTE}.`,
    tone: "neutral",
  };
}
