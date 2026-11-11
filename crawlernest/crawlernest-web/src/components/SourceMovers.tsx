"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CaveatBanner } from "@/components/CaveatBanner";
import { DATASET_SOURCES, DATASET_YEARS, DEFAULT_RANKING_YEAR } from "@/lib/datasetScope";
import { RANK_DELTA_REASON_TEXT } from "@/lib/rankDeltaPresentation";
import { universityPath } from "@/lib/site";

/**
 * The largest exact rank movements of one source between an edition and the held edition before it
 * (GET /api/v1/analytics/source-movers). One source at a time: ranks from different sources are never mixed.
 * Banded and withheld movements are counted, not listed, and every count says what it is.
 */

export type Mover = {
  canonicalUniversityId: number;
  universityName: string;
  slug: string | null;
  country: string | null;
  priorRankDisplay: string;
  rankDisplay: string;
  /** Negative is better: a smaller rank number. */
  rankDelta: number;
};

export type SourceMoversData = {
  source: string;
  ranking_year: number;
  prior_year: number | null;
  withheld_reason?: string;
  risers: Mover[];
  fallers: Mover[];
  counts: Record<string, number>;
  caveats: string[];
};

/** The counts in words; a reason without its own wording is shown by name rather than guessed at. */
export function describeCounts(data: SourceMoversData): string[] {
  const out: string[] = [];
  const counts = data.counts ?? {};
  const prior = data.prior_year;
  if (counts.exact) out.push(`${counts.exact.toLocaleString()} universities compared on exact ranks`);
  if (counts.banded) out.push(`${counts.banded.toLocaleString()} with a printed band in one edition (an interval, not listed)`);
  for (const [reason, count] of Object.entries(counts)) {
    if (["exact", "banded"].includes(reason) || reason.startsWith("only_in_") || !count) continue;
    out.push(`${count.toLocaleString()} not compared: ${RANK_DELTA_REASON_TEXT[reason] ?? reason}`);
  }
  const onlyCurrent = counts[`only_in_${data.ranking_year}`];
  const onlyPrior = prior != null ? counts[`only_in_${prior}`] : undefined;
  if (onlyCurrent) out.push(`${onlyCurrent.toLocaleString()} ranked here in ${data.ranking_year} but not in ${prior} as held`);
  if (onlyPrior) out.push(`${onlyPrior.toLocaleString()} ranked here in ${prior} but not in ${data.ranking_year} as held`);
  return out;
}

function withheldText(data: SourceMoversData): string {
  if (data.withheld_reason === "no_prior_edition_held") {
    return `No edition before ${data.ranking_year} is held, so there is nothing to compare with.`;
  }
  return `No ${data.source} edition of ${data.prior_year != null && data.withheld_reason?.endsWith(String(data.prior_year)) ? data.prior_year : data.ranking_year} is held here, so no ${data.source} movement into ${data.ranking_year} is shown. It is not compared with an older edition instead.`;
}

function MoverTable({ title, rows, data }: { title: string; rows: Mover[]; data: SourceMoversData }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-bold text-slate-600">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-xs text-slate-400">None.</p>
      ) : (
        <table className="w-full border border-slate-200 bg-white text-sm">
          <thead className="bg-slate-50">
            <tr>
              {["University", String(data.prior_year), String(data.ranking_year), "Change"].map((h) => (
                <th key={h} className="border-b border-slate-200 px-3 py-2 text-left text-xs font-bold text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.canonicalUniversityId} className="border-b border-slate-100 last:border-0">
                <td className="px-3 py-2">
                  {m.slug ? (
                    <Link href={`${universityPath(m.slug)}?year=${data.ranking_year}`} className="font-medium text-slate-900 hover:underline">
                      {m.universityName}
                    </Link>
                  ) : (
                    <span className="font-medium text-slate-900">{m.universityName}</span>
                  )}
                  {m.country ? <span className="ml-1 text-xs text-slate-400">{m.country}</span> : null}
                </td>
                <td className="px-3 py-2 font-mono text-slate-500">{m.priorRankDisplay}</td>
                <td className="px-3 py-2 font-mono text-slate-700">{m.rankDisplay}</td>
                <td className={`px-3 py-2 font-mono text-xs ${m.rankDelta < 0 ? "text-emerald-700" : "text-rose-700"}`}>
                  {m.rankDelta < 0 ? `↑ ${-m.rankDelta}` : `↓ ${m.rankDelta}`}
                  <span className="sr-only">{m.rankDelta < 0 ? " places up" : " places down"}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

type State = { status: "loading" } | { status: "error"; message: string } | { status: "ok"; data: SourceMoversData };

export function SourceMovers() {
  const [source, setSource] = useState<string>(DATASET_SOURCES[1] ?? "THE");
  const [year, setYear] = useState<number>(DEFAULT_RANKING_YEAR);
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/analytics/source-movers?source=${encodeURIComponent(source)}&year=${year}&limit=10`)
      .then(async (res) => {
        const json = await res.json();
        if (!res.ok || !json?.success) throw new Error(json?.error ?? json?.message ?? `HTTP ${res.status}`);
        if (!cancelled) setState({ status: "ok", data: json.data as SourceMoversData });
      })
      .catch((err: unknown) => {
        if (!cancelled) setState({ status: "error", message: err instanceof Error ? err.message : "Fetch failed" });
      });
    return () => {
      cancelled = true;
    };
  }, [source, year]);

  const years = [...DATASET_YEARS].sort((a, b) => b - a).slice(0, -1);
  const data = state.status === "ok" ? state.data : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <div role="group" aria-label="Source" className="flex">
          {DATASET_SOURCES.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={s === source}
              onClick={() => { setState({ status: "loading" }); setSource(s); }}
              className={`border px-3 py-1.5 text-xs font-semibold ${s === source ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700"}`}
            >
              {s}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-600">
          Edition
          <select
            value={year}
            onChange={(e) => { setState({ status: "loading" }); setYear(Number(e.target.value)); }}
            className="border border-slate-300 bg-white px-2 py-1"
          >
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        {data?.prior_year != null ? (
          <span className="text-xs text-slate-500">compared with the {data.prior_year} edition</span>
        ) : null}
      </div>

      {state.status === "loading" ? <div className="h-24 animate-pulse rounded bg-slate-100" /> : null}
      {state.status === "error" ? (
        <div className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{state.message}</div>
      ) : null}
      {data ? (
        <>
          {data.withheld_reason ? (
            <p className="border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-700">{withheldText(data)}</p>
          ) : (
            <>
              <div className="grid gap-6 md:grid-cols-2">
                <MoverTable title={`Largest rises in ${data.source}`} rows={data.risers} data={data} />
                <MoverTable title={`Largest falls in ${data.source}`} rows={data.fallers} data={data} />
              </div>
              <ul className="mt-3 space-y-0.5 text-xs text-slate-500">
                {describeCounts(data).map((line) => <li key={line}>{line}</li>)}
              </ul>
            </>
          )}
          <CaveatBanner className="mt-3" caveats={data.caveats} />
        </>
      ) : null}
    </div>
  );
}
