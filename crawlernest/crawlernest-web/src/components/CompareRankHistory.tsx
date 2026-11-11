"use client";

import { useEffect, useState } from "react";
import { CaveatBanner } from "@/components/CaveatBanner";
import { describePoint } from "@/components/RankHistoryChart";
import { LINE_COLORS, LINE_SHAPES, RankLinesChart, type RankLine } from "@/components/RankLinesChart";
import type { RankHistory, RankHistoryResponse } from "@/types/university";

/**
 * The compared universities' printed ranks over every held edition: one chart per source, one line per university.
 *
 * Small multiples by source, never one chart across sources: a QS rank and a THE rank are different scales, and
 * nothing here combines them. Each university keeps the colour and shape of its place in the selection, so it is
 * the same line in every chart. Universities are compared within a source, edition by edition; no composite and
 * no movement is computed.
 */

export type CompareRankHistoryUniversity = { canonicalUniversityId: number; universityName: string };

const SMALL_WORDS = new Set(["of", "the", "and", "at", "de", "du", "di", "da", "y", "&", "for", "in"]);

/** A short label for the direct label and table header; the full name stays in every sentence. */
export function shortLabel(name: string): string {
  const trimmed = name.trim();
  const parenthetical = trimmed.match(/\(([^)]{2,10})\)\s*$/);
  if (parenthetical) return parenthetical[1];
  if (trimmed.length <= 18) return trimmed;
  const initials = trimmed
    .split(/[\s,\-–]+/)
    .filter((word) => word && !SMALL_WORDS.has(word.toLowerCase()))
    .map((word) => word[0].toUpperCase())
    .join("");
  if (initials.length >= 3) return initials;
  return `${trimmed.slice(0, 17)}…`;
}

/** Builds each source's lines from the histories, in selection order. Pure, for tests. */
export function linesBySource(
  universities: CompareRankHistoryUniversity[],
  histories: (RankHistory | null)[]
): { source: string; lines: RankLine[] }[] {
  const sources: string[] = [];
  for (const history of histories) {
    for (const series of history?.series ?? []) {
      if (!sources.includes(series.source)) sources.push(series.source);
    }
  }
  return sources.map((source) => ({
    source,
    lines: universities.flatMap((university, index) => {
      const series = histories[index]?.series.find((s) => s.source === source);
      if (!series) return [];
      return [{
        key: String(university.canonicalUniversityId),
        label: shortLabel(university.universityName),
        color: LINE_COLORS[index % LINE_COLORS.length],
        shape: LINE_SHAPES[index % LINE_SHAPES.length],
        points: series.points,
        describe: (point) => `${university.universityName} — ${describePoint(source, point)}`,
      }];
    }),
  }));
}

type State = { key: string; histories: (RankHistory | null)[]; failed: boolean } | null;

export function CompareRankHistory({ universities }: { universities: CompareRankHistoryUniversity[] }) {
  const key = universities.map((u) => u.canonicalUniversityId).join(",");
  const [state, setState] = useState<State>(null);

  useEffect(() => {
    if (universities.length < 2) return;
    let cancelled = false;
    Promise.all(
      universities.map(async (university) => {
        const response = await fetch(`/api/universities/${university.canonicalUniversityId}/rank-history`);
        if (!response.ok) return null;
        const payload = (await response.json()) as RankHistoryResponse;
        const data = payload.success ? payload.data : null;
        return data && Array.isArray(data.years) && Array.isArray(data.series) ? data : null;
      })
    )
      .then((histories) => {
        if (!cancelled) setState({ key, histories, failed: histories.every((h) => h == null) });
      })
      .catch(() => {
        if (!cancelled) setState({ key, histories: [], failed: true });
      });
    return () => {
      cancelled = true;
    };
    // `key` carries the selection; the array itself is a new object every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (universities.length < 2) return null;
  if (!state || state.key !== key) {
    return <p className="text-sm text-(--color-muted)">Loading rank histories…</p>;
  }
  if (state.failed) {
    return <p className="text-sm text-(--color-muted)">Rank histories are not available right now.</p>;
  }

  const years = state.histories.find((h) => h != null)?.years ?? [];
  const charts = linesBySource(universities, state.histories).filter((chart) =>
    chart.lines.some((line) => line.points.some((p) => p.status === "ranked"))
  );
  const caveats = state.histories.flatMap((h) => h?.caveats ?? []);

  return (
    <div>
      <div className="grid gap-6 xl:grid-cols-2">
        {charts.map(({ source, lines }) => (
          <figure key={source} className="m-0">
            <figcaption className="mb-2 text-sm font-semibold text-(--color-ink)">{source}</figcaption>
            <RankLinesChart
              years={years}
              lines={lines}
              ariaLabel={`${source} rank by edition for ${lines.map((l) => l.label).join(", ")}, ${years[0]} to ${years[years.length - 1]}.`}
              notInEditionLabel="edition held, this university not in it here"
            />
          </figure>
        ))}
      </div>
      {charts.length === 0 ? (
        <p className="text-sm text-(--color-muted)">No source ranks any of these universities in a held edition here.</p>
      ) : null}
      <CaveatBanner className="mt-4" caveats={caveats} />
    </div>
  );
}
