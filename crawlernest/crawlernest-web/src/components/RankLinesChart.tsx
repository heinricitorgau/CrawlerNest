"use client";

import { useId, useState } from "react";
import type { RankHistoryPoint } from "@/types/university";

/**
 * Printed ranks over held editions, one line per series, with a coverage strip that says what every gap is.
 *
 * Shared by the university page (one line per source) and the compare page (one line per university, one chart
 * per source). The rules hold for both:
 * - no line crosses a gap or a change of the source's entry for the university;
 * - a banded rank is drawn as its band with a hollow marker at the lower bound, never as one position;
 * - a gap is either an edition this warehouse does not hold (hatched) or a held edition without this entry
 *   (outlined), and neither is worded as the source declining to rank;
 * - nothing is computed across lines or editions.
 *
 * Identity is never colour alone: each line has a validated categorical colour in a fixed order, its own marker
 * shape, a direct label, a hover readout and a table column.
 */

export type MarkerShape = "circle" | "square" | "diamond" | "triangle";

export type RankLine = {
  key: string;
  /** Short, for the direct label, the strip and the table header. */
  label: string;
  color: string;
  shape: MarkerShape;
  points: RankHistoryPoint[];
  /** The sentence for one point: hover, strip tooltip, table cell title, screen readers. */
  describe: (point: RankHistoryPoint) => string;
};

/** Validated categorical slots 1-4 (light surface), in the order lines are assigned them. */
export const LINE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"] as const;
export const LINE_SHAPES: readonly MarkerShape[] = ["circle", "square", "diamond", "triangle"];

const WIDTH = 640;
const PLOT_HEIGHT = 260;
const MARGIN = { top: 14, bottom: 28, left: 76 };
const STRIP_ROW = 14;
const STRIP_GAP = 8;
const TICK_CANDIDATES = [1, 2, 5, 10, 20, 50, 100, 200, 300, 500, 1000, 2000];

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
export function rankDomain(lines: { points: RankHistoryPoint[] }[]): [number, number] {
  let min = Infinity;
  let max = 0;
  for (const line of lines) {
    for (const p of line.points) {
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

export function cellText(point: RankHistoryPoint | undefined): string {
  if (!point) return "—";
  if (point.status === "edition_not_held") return "no edition held";
  if (point.status === "not_in_edition") return "not in edition";
  const rank = point.rankDisplay ?? String(point.rankLower ?? "");
  return point.archived ? `${rank}*` : rank;
}

export function Marker({ shape, x, y, color, hollow }: { shape: MarkerShape; x: number; y: number; color: string; hollow: boolean }) {
  const fill = hollow ? "var(--color-plate)" : color;
  const common = { fill, stroke: hollow ? color : "var(--color-plate)", strokeWidth: 2 };
  if (shape === "square") {
    return <rect x={x - 4.5} y={y - 4.5} width={9} height={9} rx={1.5} {...common} />;
  }
  if (shape === "diamond") {
    return <path d={`M ${x} ${y - 6} L ${x + 6} ${y} L ${x} ${y + 6} L ${x - 6} ${y} Z`} {...common} />;
  }
  if (shape === "triangle") {
    return <path d={`M ${x} ${y - 6} L ${x + 6} ${y + 5} L ${x - 6} ${y + 5} Z`} {...common} />;
  }
  return <circle cx={x} cy={y} r={5} {...common} />;
}

type RankLinesChartProps = {
  years: number[];
  lines: RankLine[];
  ariaLabel: string;
  /** What a hollow strip cell means here ("edition held, no rank for this university here"). */
  notInEditionLabel: string;
};

export function RankLinesChart({ years, lines, ariaLabel, notInEditionLabel }: RankLinesChartProps) {
  const [hoverYear, setHoverYear] = useState<number | null>(null);
  // Unique per chart: the compare page draws several on one page, and pattern ids are document-wide.
  const hatchId = `rank-hatch-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const ranked = lines.filter((line) => line.points.some((p) => p.status === "ranked"));

  // Room on the right for the longest direct label, within reason.
  const longest = Math.max(4, ...ranked.map((line) => line.label.length));
  const right = Math.min(150, 16 + longest * 6.4);
  const plotW = WIDTH - MARGIN.left - right;
  const plotH = PLOT_HEIGHT - MARGIN.top - MARGIN.bottom;

  const [minRank, maxRank] = rankDomain(lines);
  const logMin = Math.log(minRank);
  const logSpan = Math.log(maxRank) - logMin || 1;
  const y = (rank: number) => MARGIN.top + ((Math.log(Math.min(Math.max(rank, minRank), maxRank)) - logMin) / logSpan) * plotH;
  // Inset so the first and last editions' markers and cells clear the axis labels.
  const inset = 14;
  const step = years.length > 1 ? (plotW - 2 * inset) / (years.length - 1) : 0;
  const x = (year: number) => MARGIN.left + (years.length > 1 ? inset + years.indexOf(year) * step : plotW / 2);
  const bottom = MARGIN.top + plotH;
  const stripTop = PLOT_HEIGHT + STRIP_GAP;
  const height = stripTop + lines.length * STRIP_ROW + 4;
  const cellW = Math.min(step || plotW, 40) - 3;
  const ticks = TICK_CANDIDATES.filter((t) => t >= minRank && t <= maxRank);

  // Direct labels at each line's latest ranked point, nudged apart so they never overlap.
  const labels = ranked
    .map((line) => {
      const last = [...line.points].reverse().find((p) => p.status === "ranked")!;
      return { key: line.key, label: line.label, y: y(last.rankLower ?? 1) };
    })
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) {
    labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 13);
  }

  const hoverLeftPct = hoverYear == null ? 0 : (x(hoverYear) / WIDTH) * 100;
  const anyArchived = lines.some((line) => line.points.some((p) => p.archived));
  const hatch = { background: "repeating-linear-gradient(45deg, var(--color-paper-3) 0 2px, transparent 2px 5px)" };

  return (
    <div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${height}`}
          className="w-full h-auto"
          role="img"
          aria-label={`${ariaLabel} Better ranks are higher; the scale is logarithmic. The table below lists every value.`}
          onMouseLeave={() => setHoverYear(null)}
        >
          <defs>
            <pattern id={hatchId} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="2" height="5" fill="var(--color-paper-3)" />
            </pattern>
          </defs>
          {/* Recessive grid: rank 1 at the top, log scale so a move from 5 to 3 is visible beside 500 to 300. */}
          {ticks.map((t) => (
            <g key={t}>
              <line x1={MARGIN.left} x2={MARGIN.left + plotW} y1={y(t)} y2={y(t)} stroke="var(--color-paper-2)" strokeWidth={1} />
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

          {lines.map((line) => (
            <g key={line.key}>
              {lineSegments(line.points).map(({ from, to }) => (
                <line
                  key={`${from.year}-${to.year}`}
                  x1={x(from.year)}
                  y1={y(from.rankLower ?? 1)}
                  x2={x(to.year)}
                  y2={y(to.rankLower ?? 1)}
                  stroke={line.color}
                  strokeWidth={2}
                  strokeLinecap="round"
                />
              ))}
              {line.points
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
                          stroke={line.color}
                          strokeWidth={2}
                          strokeLinecap="round"
                          strokeDasharray={p.rankUpper == null ? "3 3" : undefined}
                          opacity={0.55}
                        />
                      ) : null}
                      <Marker shape={line.shape} x={x(p.year)} y={top} color={line.color} hollow={banded} />
                    </g>
                  );
                })}
            </g>
          ))}

          {labels.map((label) => (
            <text key={label.key} x={MARGIN.left + plotW + 12} y={label.y} dy="0.32em" fontSize={11} fontWeight={700} fill="var(--color-ink-2)">
              {label.label}
            </text>
          ))}

          {/* Coverage strip: one row per line, one cell per edition, aligned with the ticks above. */}
          {lines.map((line, row) => {
            const rowY = stripTop + row * STRIP_ROW;
            return (
              <g key={`strip-${line.key}`}>
                <text x={4} y={rowY + 5} dy="0.32em" textAnchor="start" fontSize={9} fontWeight={700} fill="var(--color-ink-2)">
                  {line.label.length > 11 ? `${line.label.slice(0, 10)}…` : line.label}
                </text>
                {years.map((year) => {
                  const p = line.points.find((point) => point.year === year);
                  const status = p?.status ?? "not_in_edition";
                  return (
                    <rect
                      key={year}
                      x={x(year) - cellW / 2}
                      y={rowY}
                      width={cellW}
                      height={10}
                      rx={2}
                      data-status={status}
                      fill={status === "ranked" ? line.color : status === "edition_not_held" ? `url(#${hatchId})` : "var(--color-plate)"}
                      stroke={status === "not_in_edition" ? "var(--color-rule)" : "none"}
                      strokeWidth={1}
                    >
                      <title>{p ? line.describe(p) : `${line.label} ${year}`}</title>
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
              x={x(year) - (step || plotW) / 2}
              y={MARGIN.top}
              width={step || plotW}
              height={height - MARGIN.top}
              fill="transparent"
              onMouseEnter={() => setHoverYear(year)}
            />
          ))}
        </svg>

        {hoverYear != null ? (
          <div
            role="status"
            className="pointer-events-none absolute top-1 z-10 min-w-[12rem] max-w-[22rem] rounded border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm"
            style={hoverLeftPct > 60 ? { right: `${100 - hoverLeftPct + 2}%` } : { left: `${hoverLeftPct + 2}%` }}
          >
            <p className="mb-1 font-bold text-slate-900">{hoverYear} edition</p>
            <ul className="space-y-0.5">
              {lines.map((line) => {
                const point = line.points.find((p) => p.year === hoverYear);
                return (
                  <li key={line.key} className="flex items-center gap-2 text-slate-700">
                    <svg width="12" height="12" viewBox="-6 -6 12 12" aria-hidden="true" className="shrink-0">
                      <Marker shape={line.shape} x={0} y={0} color={line.color} hollow={point?.status !== "ranked"} />
                    </svg>
                    {point ? line.describe(point) : `${line.label}: —`}
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
      </div>

      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-600">
        <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm bg-slate-500" aria-hidden="true" /> ranked (filled marker: one position; hollow marker and bar: a printed band)</li>
        <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm border border-slate-300 bg-white" aria-hidden="true" /> {notInEditionLabel}</li>
        <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-4 rounded-sm" aria-hidden="true" style={hatch} /> no edition of this source held here</li>
        {anyArchived ? <li>* in the table: an edition read from an Internet Archive capture</li> : null}
      </ul>

      <details className="mt-3 text-xs">
        <summary className="cursor-pointer font-semibold text-slate-600">Table view</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="ranking-table">
            <thead>
              <tr>
                <th>Edition</th>
                {lines.map((line) => (
                  <th key={line.key} className="text-center">{line.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...years].reverse().map((year) => (
                <tr key={year}>
                  <td className="font-semibold">{year}</td>
                  {lines.map((line) => {
                    const p = line.points.find((point) => point.year === year);
                    return (
                      <td key={line.key} className="text-center font-mono" title={p ? line.describe(p) : undefined}>
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
    </div>
  );
}
