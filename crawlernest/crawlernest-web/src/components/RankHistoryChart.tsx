"use client";

import { CaveatBanner } from "@/components/CaveatBanner";
import { RankLinesChart, cellText, lineSegments, rankDomain, type MarkerShape, type RankLine } from "@/components/RankLinesChart";
import type { RankHistory, RankHistoryPoint } from "@/types/university";

/**
 * A university's printed rank from each source, edition by edition: one line per source, drawn by
 * RankLinesChart (which holds the rules: no line across a gap, bands as bands, every gap labelled).
 * The caveats are the API's, rendered verbatim.
 *
 * Each source keeps a fixed colour and shape (categorical slots 1-3, validated), here and on the compare page.
 */

type SourceStyle = { color: string; shape: MarkerShape };

const SOURCE_STYLES: Record<string, SourceStyle> = {
  QS: { color: "#2a78d6", shape: "circle" },
  THE: { color: "#eb6834", shape: "square" },
  ARWU: { color: "#1baf7a", shape: "diamond" },
};
const FALLBACK_STYLE: SourceStyle = { color: "#52514e", shape: "circle" };

export { cellText, lineSegments, rankDomain };

export function styleFor(source: string): SourceStyle {
  return SOURCE_STYLES[source] ?? FALLBACK_STYLE;
}

/** What a point says in words: the tooltip, the table and the screen reader all read this. */
export function describePoint(source: string, point: RankHistoryPoint): string {
  if (point.status === "edition_not_held") {
    return `No ${source} ${point.year} edition is held here`;
  }
  if (point.status === "not_in_edition") {
    return `Not in the ${source} ${point.year} edition as held here`;
  }
  const notes: string[] = [];
  if (point.archived) notes.push("from an Internet Archive capture");
  if (point.sourceIdentityChanged) notes.push(`${source} entry changed`);
  if (point.suspiciousMerge) notes.push("match flagged for review");
  const rank = point.rankDisplay ?? String(point.rankLower ?? "");
  return `${source} ${point.year}: ${rank}${notes.length ? ` (${notes.join("; ")})` : ""}`;
}

type RankHistoryChartProps = { history: RankHistory };

export function RankHistoryChart({ history }: RankHistoryChartProps) {
  const { years, series } = history;
  const anyRanked = series.some((s) => s.points.some((p) => p.status === "ranked"));

  if (years.length === 0 || !anyRanked) {
    return (
      <div>
        <p className="text-sm text-slate-500 italic">
          No source rank is held for this university in any edition here.
        </p>
        <CaveatBanner className="mt-3" caveats={history.caveats} />
      </div>
    );
  }

  const lines: RankLine[] = series.map((s) => ({
    key: s.source,
    label: s.source,
    ...styleFor(s.source),
    points: s.points,
    describe: (point) => describePoint(s.source, point),
  }));

  return (
    <div>
      <RankLinesChart
        years={years}
        lines={lines}
        ariaLabel={`Rank by source and edition, ${years[0]} to ${years[years.length - 1]}.`}
        notInEditionLabel="edition held, no rank for this university here"
      />
      <CaveatBanner className="mt-3" caveats={history.caveats} />
    </div>
  );
}
