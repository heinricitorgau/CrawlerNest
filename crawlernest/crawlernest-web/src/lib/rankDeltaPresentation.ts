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

export type RankDeltaTone = "up" | "down" | "neutral" | "withheld";

export type RankDeltaPresentation = {
  /** Short cell text, e.g. "↑ 3 since 2025". */
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
    "The institution or its source entry changed between editions (for example a merger or rename), so the two ranks do not describe the same entity.",
  suspicious_merge: "The match between this source's entry and this university was flagged for review in one of the editions.",
  rank_display_missing:
    "The printed rank for one of the editions was not recorded, and the stored position alone would overstate its precision.",
  composite_rank_not_comparable:
    "A composite rank moves when source coverage changes, so it is not compared across editions.",
};

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

export function presentRankDelta(row: Pick<UniversityRanking, "rankDelta" | "rankDeltaReason">): RankDeltaPresentation {
  const delta: RankDelta | null = row.rankDelta ?? null;
  if (!delta || !delta.direction) {
    const reason = row.rankDeltaReason ?? "";
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

  // Banded: only an interval is known. Up means both bounds are negative.
  if (delta.direction === "up") {
    const nearest = delta.max != null ? Math.abs(delta.max) : null;
    const farthest = delta.min != null ? Math.abs(delta.min) : null;
    return {
      label: `↑ banded${since}`,
      detail: `Up ${span(nearest, farthest)}${since}${was}; ${BAND_NOTE}.`,
      tone: "up",
    };
  }
  if (delta.direction === "down") {
    return {
      label: `↓ banded${since}`,
      detail: `Down ${span(delta.min, delta.max)}${since}${was}; ${BAND_NOTE}.`,
      tone: "down",
    };
  }
  return {
    label: `Within band${since}`,
    detail: `The bands in both editions overlap, so the direction of any movement is unknown${was}; ${BAND_NOTE}.`,
    tone: "neutral",
  };
}
