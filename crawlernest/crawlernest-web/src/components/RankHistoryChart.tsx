"use client";

import { useState } from "react";
import { CaveatBanner } from "@/components/CaveatBanner";
import type { RankHistory, RankHistoryPoint, RankHistorySeries } from "@/types/university";

/**
 * A university's printed rank from each source, edition by edition.
 *
 * What it refuses to draw matters as much as what it draws:
 * - no line crosses a gap, and the coverage strip says which kind each gap is -- an edition this warehouse
 *   does not hold (the same for every university), or a held edition with no rank for this one here;
 * - no line joins two points where the source's entry for the university changed;
 * - a banded rank is drawn as its band, with a hollow marker at the lower bound, never as one position;
 * - nothing is computed across sources or editions. The caveats are the API's, rendered verbatim.
 *
 * Colours are the validated categorical slots 1-3 in a fixed order per source; each source also has its
 * own marker shape and a direct label, so identity is never colour alone.
 */

type SourceStyle = { color: string; shape: "circle" | "square" | "diamond" };

const SOURCE_STYLES: Record<string, SourceStyle> = {
  QS: { color: "#2a78d6", shape: "circle" },
  THE: { color: "#eb6834", shape: "square" },
  ARWU: { color: "#1baf7a", shape: "diamond" },
};
const FALLBACK_STYLE: SourceStyle = { color: "#52514e", shape: "circle" };

const WIDTH = 640;
const PLOT_HEIGHT = 260;
const MARGIN = { top: 14, right: 64, bottom: 28, left: 76 };
const PLOT_W = WIDTH - MARGIN.left - MARGIN.right;
const PLOT_H = PLOT_HEIGHT - MARGIN.top - MARGIN.bottom;
/** The coverage strip sits in the same SVG, so each cell is exactly under its edition's tick. */
const STRIP_ROW = 14;
const STRIP_GAP = 8;
const HATCH_ID = "rank-history-not-held";
const TICK_CANDIDATES = [1, 2, 5, 10, 20, 50, 100, 200, 300, 500, 1000, 2000];

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

type Segment = { from: RankHistoryPoint; to: RankHistoryPoint };

/** Consecutive editions that are both ranked, with no change of source entry between them. */
export function lineSegments(points: RankHistoryPoint[]): Segment[] {
  const segments: Segment[] = [];
  for (let i = 1; i < points.length; i++) {
    const from = points[i - 1];
    const to = points[i];
    if (from.status === "ranked" && to.status === "ranked" && !to.sourceIdentityChanged) {
      segments.push({ from, to });
    }
  }
  return segments;
}

/** The log-scale domain: from just above the best rank shown to just below the worst, so the ranks use the height. */
export function rankDomain(series: RankHistorySeries[]): [number, number] {
  let min = Infinity;
  let max = 0;
  for (const s of series) {
    for (const p of s.points) {
      if (p.status !== "ranked" || p.rankLower == null) continue;
      min = Math.min(min, p.rankLower);
      max = Math.max(max, p.rankUpper ?? p.rankLower, p.rankLower);
    }
  }
  if (!Number.isFinite(min)) return [1, 10];
  const lo = Math.max(1, min / 1.4);
  const hi = Math.max(max * 1.15, lo * 4);
  return [lo, hi];
}

function Marker({ shape, x, y, color, hollow }: { shape: SourceStyle["shape"]; x: number; y: number; color: string; hollow: boolean }) {
  const fill = hollow ? "var(--color-plate)" : color;
  const common = { fill, stroke: hollow ? color : "var(--color-plate)", strokeWidth: 2 };
  if (shape === "square") {
    return <rect x={x - 4.5} y={y - 4.5} width={9} height={9} rx={1.5} {...common} />;
  }
  if (shape === "diamond") {
    return <path d={`M ${x} ${y - 6} L ${x + 6} ${y} L ${x} ${y + 6} L ${x - 6} ${y} Z`} {...common} />;
  }
  return <circle cx={x} cy={y} r={5} {...common} />;
}

type RankHistoryChartProps = { history: RankHistory };

export function RankHistoryChart({ history }: RankHistoryChartProps) {
  const [hoverYear, setHoverYear] = useState<number | null>(null);
  const { years, series } = history;
  const ranked = series.filter((s) => s.points.some((p) => p.status === "ranked"));

  if (years.length === 0 || ranked.length === 0) {
    return (
      <div>
        <p className="text-sm text-slate-500 italic">
          No source rank is held for this university in any edition here.
        </p>
        <CaveatBanner className="mt-3" caveats={history.caveats} />
      </div>
    );
  }

  const [minRank, maxRank] = rankDomain(series);
  const logMin = Math.log(minRank);
  const logSpan = Math.log(maxRank) - logMin;
  const y = (rank: number) => MARGIN.top + ((Math.log(Math.min(Math.max(rank, minRank), maxRank)) - logMin) / logSpan) * PLOT_H;
  // Inset so the first and last editions' markers and cells clear the axis labels.
  const inset = 14;
  const step = years.length > 1 ? (PLOT_W - 2 * inset) / (years.length - 1) : 0;
  const x = (year: number) => MARGIN.left + (years.length > 1 ? inset + years.indexOf(year) * step : PLOT_W / 2);
  const bottom = MARGIN.top + PLOT_H;
  const stripTop = PLOT_HEIGHT + STRIP_GAP;
  const height = stripTop + series.length * STRIP_ROW + 4;
  const cellW = Math.min(step || PLOT_W, 40) - 3;
  const ticks = TICK_CANDIDATES.filter((t) => t >= minRank && t <= maxRank);

  // Direct labels at each series' latest ranked point, nudged apart so they never overlap.
  const labels = ranked
    .map((s) => {
      const last = [...s.points].reverse().find((p) => p.status === "ranked")!;
      return { source: s.source, y: y(last.rankLower ?? 1) };
    })
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) {
    labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 13);
  }

  const hovered = hoverYear == null ? null : series.map((s) => ({ source: s.source, point: s.points.find((p) => p.year === hoverYear) }));
  const hoverLeftPct = hoverYear == null ? 0 : (x(hoverYear) / WIDTH) * 100;

  return (
    <div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${height}`}
          className="w-full h-auto"
          role="img"
          aria-label={`Rank by source and edition, ${years[0]} to ${years[years.length - 1]}. Better ranks are higher; the scale is logarithmic. The table below lists every value.`}
          onMouseLeave={() => setHoverYear(null)}
        >
          <defs>
            <pattern id={HATCH_ID} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="2" height="5" fill="var(--color-paper-3)" />
            </pattern>
          </defs>
          {/* Recessive grid: rank 1 at the top, log scale so a move from 5 to 3 is visible beside 500 to 300. */}
          {ticks.map((t) => (
            <g key={t}>
              <line x1={MARGIN.left} x2={MARGIN.left + PLOT_W} y1={y(t)} y2={y(t)} stroke="var(--color-paper-2)" strokeWidth={1} />
              <text x={MARGIN.left - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize={10} fill="var(--color-muted)">
                {t}
              </text>
            </g>
          ))}
          {years.map((year) => (
            <text key={year} x={x(year)} y={bottom + 18} textAnchor="middle" fontSize={10} fill="var(--color-muted)">
              {years.length > 8 ? `’${String(year).slice(2)}` : year}
            </text>
          ))}

          {hoverYear != null ? (
            <line x1={x(hoverYear)} x2={x(hoverYear)} y1={MARGIN.top} y2={bottom} stroke="var(--color-rule)" strokeWidth={1} />
          ) : null}

          {series.map((s) => {
            const style = styleFor(s.source);
            return (
              <g key={s.source}>
                {lineSegments(s.points).map(({ from, to }) => (
                  <line
                    key={`${from.year}-${to.year}`}
                    x1={x(from.year)}
                    y1={y(from.rankLower ?? 1)}
                    x2={x(to.year)}
                    y2={y(to.rankLower ?? 1)}
                    stroke={style.color}
                    strokeWidth={2}
                    strokeLinecap="round"
                  />
                ))}
                {s.points
                  .filter((p) => p.status === "ranked")
                  .map((p) => {
                    const lower = p.rankLower ?? 1;
                    const banded = p.rankUpper !== lower;
                    const top = y(lower);
                    const end = p.rankUpper == null ? bottom : y(p.rankUpper);
                    return (
                      <g key={p.year}>
                        {banded ? (
                          <line
                            x1={x(p.year)}
                            x2={x(p.year)}
                            y1={top}
                            y2={end}
                            stroke={style.color}
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeDasharray={p.rankUpper == null ? "3 3" : undefined}
                            opacity={0.55}
                          />
                        ) : null}
                        <Marker shape={style.shape} x={x(p.year)} y={top} color={style.color} hollow={banded} />
                      </g>
                    );
                  })}
              </g>
            );
          })}

          {labels.map((label) => (
            <text key={label.source} x={MARGIN.left + PLOT_W + 12} y={label.y} dy="0.32em" fontSize={11} fontWeight={700} fill="var(--color-ink-2)">
              {label.source}
            </text>
          ))}

          {/* Coverage strip: one row per source, one cell per edition, aligned with the ticks above. */}
          {series.map((s, row) => {
            const rowY = stripTop + row * STRIP_ROW;
            return (
              <g key={`strip-${s.source}`}>
                <text x={4} y={rowY + 5} dy="0.32em" textAnchor="start" fontSize={9} fontWeight={700} fill="var(--color-ink-2)">
                  {s.source}
                </text>
                {years.map((year) => {
                  const p = s.points.find((point) => point.year === year);
                  const status = p?.status ?? "not_in_edition";
                  const common = { x: x(year) - cellW / 2, y: rowY, width: cellW, height: 10, rx: 2 };
                  return (
                    <rect
                      key={year}
                      {...common}
                      data-status={status}
                      fill={status === "ranked" ? styleFor(s.source).color : status === "edition_not_held" ? `url(#${HATCH_ID})` : "var(--color-plate)"}
                      stroke={status === "not_in_edition" ? "var(--color-rule)" : "none"}
                      strokeWidth={1}
                    >
                      <title>{p ? describePoint(s.source, p) : `${s.source} ${year}`}</title>
                    </rect>
                  );
                })}
              </g>
            );
          })}

          {/* Hit targets: one column per edition, wider than any mark. */}
          {years.map((year) => (
            <rect
              key={year}
              x={x(year) - (step || PLOT_W) / 2}
              y={MARGIN.top}
              width={step || PLOT_W}
              height={height - MARGIN.top}
              fill="transparent"
              onMouseEnter={() => setHoverYear(year)}
            />
          ))}
        </svg>

        {hovered ? (
          <div
            role="status"
            className="pointer-events-none absolute top-1 z-10 min-w-[12rem] rounded border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm"
            style={hoverLeftPct > 60 ? { right: `${100 - hoverLeftPct + 2}%` } : { left: `${hoverLeftPct + 2}%` }}
          >
            <p className="mb-1 font-bold text-slate-900">{hoverYear} edition</p>
            <ul className="space-y-0.5">
              {hovered.map(({ source, point }) => (
                <li key={source} className="flex items-center gap-2 text-slate-700">
                  <svg width="12" height="12" viewBox="-6 -6 12 12" aria-hidden="true">
                    <Marker shape={styleFor(source).shape} x={0} y={0} color={styleFor(source).color} hollow={point?.status !== "ranked"} />
                  </svg>
                  {point ? describePoint(source, point) : `${source}: —`}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <CoverageLegend history={history} />

      <details className="mt-3 text-xs">
        <summary className="cursor-pointer font-semibold text-slate-600">Table view</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="ranking-table">
            <thead>
              <tr>
                <th>Edition</th>
                {series.map((s) => (
                  <th key={s.source} className="text-center">{s.source}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...years].reverse().map((year) => (
                <tr key={year}>
                  <td className="font-semibold">{year}</td>
                  {series.map((s) => {
                    const p = s.points.find((point) => point.year === year);
                    return (
                      <td key={s.source} className="text-center font-mono" title={p ? describePoint(s.source, p) : undefined}>
                        {cellText(p)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <CaveatBanner className="mt-3" caveats={history.caveats} />
    </div>
  );
}

export function cellText(point: RankHistoryPoint | undefined): string {
  if (!point) return "—";
  if (point.status === "edition_not_held") return "no edition held";
  if (point.status === "not_in_edition") return "not in edition";
  const rank = point.rankDisplay ?? String(point.rankLower ?? "");
  return point.archived ? `${rank}*` : rank;
}

/** The key to the coverage strip under the chart. */
function CoverageLegend({ history }: { history: RankHistory }) {
  const anyArchived = history.series.some((s) => s.points.some((p) => p.archived));
  const hatch = { background: "repeating-linear-gradient(45deg, var(--color-paper-3) 0 2px, transparent 2px 5px)" };
  return (
    <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-600">
      <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm bg-slate-500" aria-hidden="true" /> ranked (filled marker: one position; hollow marker and bar: a printed band)</li>
      <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm border border-slate-300 bg-white" aria-hidden="true" /> edition held, no rank for this university here</li>
      <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm" aria-hidden="true" style={hatch} /> no edition of this source held here</li>
      {anyArchived ? <li>* in the table: an edition read from an Internet Archive capture</li> : null}
    </ul>
  );
}
