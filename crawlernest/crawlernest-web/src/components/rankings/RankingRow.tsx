"use client";

import Link from "next/link";

import type { RankingPresentationRow } from "@/types/ranking";
import RankingEvidencePanel from "@/components/rankings/RankingEvidencePanel";

type Props = {
  item: RankingPresentationRow;
  inShortlist: boolean;
  onToggleShortlist: (item: RankingPresentationRow) => void;
};

export default function RankingRow({
  item,
  inShortlist,
  onToggleShortlist,
}: Props) {
  const slug = item.slug || "";
  const title = item.title || "Unknown university";
  const country = item.country || "—";

  return (
    <tr
      key={`${item.canonicalUniversityId}-${slug}-${item.shortlistRank}`}
      className="border-t border-[#e0ddd8] transition hover:bg-[#f5f3ee]"
    >
      <td className="px-4 py-3.5 text-center font-bold text-[#1a3d2e]">
        <div>{item.primaryRankLabel}</div>
        {item.secondaryRankLabel && (
          <div className="mt-0.5 text-[11px] font-medium text-[#6b7068]">
            {item.secondaryRankLabel}
          </div>
        )}
      </td>
      <td className="px-4 py-3.5">
        <Link
          href={slug ? `/universities/${slug}` : "#"}
          className="font-medium text-[#1a1a1a] underline decoration-[#c0bdb8] underline-offset-2 transition hover:text-[#1a3d2e] hover:decoration-[#1a3d2e]"
        >
          {title}
        </Link>
        <div className="mt-1 flex items-center gap-2 text-xs text-[#6b7068]">
          <span>{item.subtitle}</span>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${
              item.badgeTone === "accent"
                ? "bg-[#e8f2ec] text-[#1a3d2e]"
                : "bg-[#f0ede7] text-[#6b7068]"
            }`}
          >
            {item.badgeLabel}
          </span>
          {item.trustLevel && (
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 font-semibold uppercase tracking-[0.08em] ${
                item.trustLevel === "high"
                  ? "bg-[#e8f2ec] text-[#1a3d2e]"
                  : item.trustLevel === "medium"
                    ? "bg-[#f3ecd6] text-[#8a6116]"
                    : "bg-[#f3e7e4] text-[#8b3a2b]"
              }`}
            >
              {item.trustLevel}{" "}
              {item.trustScore != null ? Math.round(item.trustScore) : ""}
            </span>
          )}
          {item.trustLevel === "low" && (
            <span className="text-[11px] font-medium text-[#8b3a2b]">
              Limited data — interpret with caution.
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3.5 text-[#6b7068]">{country}</td>
      <td className="px-4 py-3.5 text-right font-mono font-semibold text-[#1a1a1a]">
        <div>{item.scoreLabel}</div>
        <div className="mt-0.5 text-[11px] font-sans font-medium text-[#6b7068]">
          {item.scoreCaption}
        </div>
      </td>
      <td className="px-4 py-3.5 text-center">
        <span className="inline-flex items-center rounded-full bg-[#e8f2ec] px-2.5 py-0.5 text-xs font-medium text-[#1a3d2e]">
          {item.sourceCoverageLabel}
        </span>
        <div className="mt-1 text-[11px] text-[#6b7068]">
          {item.rankingUniverseLabel}
        </div>
        {item.aggregationExplain && item.aggregationExplain.availableSourceCount > 0 && (
          <details className="mt-2 text-left">
            <summary className="cursor-pointer text-[11px] font-medium text-[#1a3d2e]">
              Ranking Evidence
            </summary>
            <RankingEvidencePanel item={item} />
          </details>
        )}
      </td>
      <td className="px-4 py-3.5 text-center">
        <button
          onClick={() => onToggleShortlist(item)}
          title={inShortlist ? "Remove from shortlist" : "Add to shortlist"}
          className={`h-7 w-7 rounded-full text-sm font-bold transition ${
            inShortlist
              ? "bg-[#1a3d2e] text-white"
              : "bg-[#f5f3ee] text-[#6b7068] hover:bg-[#e8f2ec] hover:text-[#1a3d2e]"
          }`}
        >
          {inShortlist ? "✓" : "+"}
        </button>
      </td>
    </tr>
  );
}
