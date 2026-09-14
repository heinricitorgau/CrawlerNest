import { presentRankDelta, type RankDeltaTone } from "@/lib/rankDeltaPresentation";
import type { UniversityRanking } from "@/types/university";

/**
 * One source's rank change, as the API computed it.
 *
 * No hooks, so it renders on the server (university page) and inside client
 * components (comparison) alike. The label is visible; the full sentence is in
 * the title for pointer users and in screen-reader text for everyone else.
 */
const TONE_CLASS: Record<RankDeltaTone, string> = {
  up: "text-emerald-700",
  down: "text-rose-700",
  neutral: "text-slate-600",
  withheld: "text-slate-400",
  // A pill, not grey text: this is a statement about the institution, not a gap in
  // our data, and it is the one case where a reader might otherwise expect a number.
  entity_changed:
    "inline-flex items-center rounded-full border border-dashed border-amber-400 bg-amber-50 px-2 py-0.5 font-semibold text-amber-800",
};

type SourceRankChangeProps = {
  ranking: Pick<UniversityRanking, "source" | "rankDelta" | "rankDeltaReason" | "rankDisplay">;
  className?: string;
};

export function SourceRankChange({ ranking, className = "" }: SourceRankChangeProps) {
  const change = presentRankDelta(ranking);
  return (
    <span
      className={`whitespace-nowrap text-xs ${TONE_CLASS[change.tone]} ${className}`.trim()}
      title={change.detail}
      data-tone={change.tone}
    >
      <span aria-hidden="true">{change.label}</span>
      <span className="sr-only">
        {ranking.source}: {change.label === "—" ? "no rank change shown." : `${change.label}.`} {change.detail}
      </span>
    </span>
  );
}

/** True when at least one row shows a movement, so the rank-change caveat applies. */
export function anyRankChangeShown(rankings: ReadonlyArray<Pick<UniversityRanking, "rankDelta" | "rankDeltaReason">>): boolean {
  return rankings.some((row) => row.rankDelta?.direction && row.rankDeltaReason !== "entity_changed");
}

/** True when a row withholds its change because the entity changed, so the caveat still explains why. */
export function anyEntityChanged(rankings: ReadonlyArray<Pick<UniversityRanking, "rankDeltaReason">>): boolean {
  return rankings.some((row) => row.rankDeltaReason === "entity_changed");
}
