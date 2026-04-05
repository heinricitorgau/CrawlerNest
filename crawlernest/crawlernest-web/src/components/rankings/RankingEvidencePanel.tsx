"use client";

import { formatRank } from "@/lib/format";
import type { RankingPresentationRow } from "@/types/ranking";

type EvidenceRow = {
  source: "QS" | "THE" | "ARWU";
  rank: number | null;
  hasLargeDifference: boolean;
};

type Props = {
  item: RankingPresentationRow;
};

function buildEvidenceRows(item: RankingPresentationRow): EvidenceRow[] {
  const sources = item.aggregationExplain?.sources;
  const availableRanks = (["QS", "THE", "ARWU"] as const)
    .map((source) => sources?.[source] ?? null)
    .filter((value): value is number => value != null);
  const bestRank = availableRanks.length > 0 ? Math.min(...availableRanks) : null;

  return (["QS", "THE", "ARWU"] as const).map((source) => {
    const rank = sources?.[source] ?? null;
    return {
      source,
      rank,
      hasLargeDifference:
        rank != null && bestRank != null && Math.abs(rank - bestRank) > 20,
    };
  });
}

function buildEvidenceHint(rows: EvidenceRow[]): string {
  const available = rows.filter((row) => row.rank != null);
  if (available.length <= 1) {
    return "Only one source available";
  }

  const ranks = available.map((row) => row.rank as number);
  const spread = Math.max(...ranks) - Math.min(...ranks);
  if (spread <= 5) {
    return "Strong agreement across ranking sources";
  }
  if (spread <= 20) {
    return "Moderate variation across sources";
  }
  return "High disagreement — interpret carefully";
}

function buildTrustSources(item: RankingPresentationRow): string {
  return (["QS", "THE", "ARWU"] as const)
    .filter((source) => item.trustExplain?.sources[source] != null)
    .join(", ");
}

export default function RankingEvidencePanel({ item }: Props) {
  if (
    !item.aggregationExplain ||
    item.aggregationExplain.availableSourceCount <= 0
  ) {
    return null;
  }

  const evidenceRows = buildEvidenceRows(item);
  const evidenceHint = buildEvidenceHint(evidenceRows);
  const trustSources = buildTrustSources(item);
  const trustSourceCount = trustSources.split(", ").filter(Boolean).length;

  return (
    <div className="mt-2 rounded-xl border border-[#e0ddd8] bg-[#f5f3ee] p-3 text-[11px] text-[#4f544d] shadow-sm">
      <div className="font-semibold text-[#1a1a1a]">Ranking Evidence</div>
      <div className="mt-2 space-y-1.5">
        {evidenceRows.map((row) => (
          <div key={row.source} className="flex items-center justify-between">
            <span className="font-medium text-[#4f544d]">{row.source}</span>
            <span
              className={`font-semibold ${
                row.hasLargeDifference ? "text-[#8b3a2b]" : "text-[#1a1a1a]"
              }`}
            >
              {row.rank != null ? `#${formatRank(row.rank)}` : "—"}
              {row.hasLargeDifference ? "  Large difference" : ""}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-2 border-t border-[#ddd7cf] pt-2">
        <div className="flex items-center justify-between">
          <span>Aggregated Rank (weighted)</span>
          <span className="font-semibold text-[#1a1a1a]">
            {item.aggregationExplain.aggregatedRankValue.toFixed(2)}
          </span>
        </div>

        <div className="mt-2 font-semibold text-[#1a1a1a]">Weights</div>
        <div className="mt-1 space-y-1">
          {(["QS", "THE", "ARWU"] as const).map((source) => (
            <div key={source} className="flex items-center justify-between">
              <span>{source}</span>
              <span>
                {Math.round((item.aggregationExplain?.weights[source] ?? 0) * 100)}
                %
              </span>
            </div>
          ))}
        </div>

        <div className="mt-2 rounded-lg bg-white/70 px-2.5 py-2 text-[#6b7068]">
          {evidenceHint}
        </div>

        {item.trustLevel && item.trustExplain && item.trustScore != null && (
          <div className="mt-2 border-t border-[#ddd7cf] pt-2">
            <div className="flex items-center justify-between">
              <span>Trust</span>
              <span className="font-semibold uppercase text-[#1a1a1a]">
                {item.trustLevel} ({Math.round(item.trustScore)})
              </span>
            </div>
            <div className="mt-1">
              Sources: {trustSourceCount} ({trustSources || "—"})
            </div>
            <div className="mt-1">
              Consistency:{" "}
              {item.trustExplain.consistencyScore >= 100
                ? "strong"
                : item.trustExplain.consistencyScore >= 70
                  ? "moderate"
                  : "weak"}{" "}
              (std = {item.trustExplain.stdDeviation.toFixed(1)})
            </div>
            <div className="mt-1">
              Coverage:{" "}
              {item.trustExplain.coverageScore >= 100
                ? "full"
                : item.trustExplain.coverageScore >= 65
                  ? "partial"
                  : "limited"}
            </div>
            <div className="mt-2">
              <div className="font-semibold text-[#1a1a1a]">Trust Analysis</div>
              <div className="mt-1 space-y-1">
                {(item.trustExplain.notes ?? []).map((note) => (
                  <div key={note}>
                    {note.toLowerCase().includes("strong agreement") ? "✓" : "⚠"}{" "}
                    {note}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
