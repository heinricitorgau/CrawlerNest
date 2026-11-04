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
      className="border-t border-(--color-rule) transition hover:bg-(--color-paper)"
    >
      <td className="px-4 py-3.5 text-center font-bold text-(--color-ink)">
        <div>{item.primaryRankLabel}</div>
        {item.secondaryRankLabel && (
          <div className="mt-0.5 text-[11px] font-medium text-(--color-muted)">
            {item.secondaryRankLabel}
          </div>
        )}
      </td>
      <td className="px-4 py-3.5">
        <Link
          href={slug ? `/universities/${slug}` : "#"}
          className="font-medium text-(--color-ink) underline decoration-(--color-rule) underline-offset-2 transition hover:text-(--color-ink) hover:decoration-(--color-ink)"
        >
          {title}
        </Link>
        <div className="mt-1 flex items-center gap-2 text-xs text-(--color-muted)">
          <span>{item.subtitle}</span>
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 font-medium ${
              item.badgeTone === "accent"
                ? "bg-(--color-paper-2) text-(--color-ink)"
                : "bg-(--color-paper-2) text-(--color-muted)"
            }`}
          >
            {item.badgeLabel}
          </span>
          {item.trustLevel && (
            <span
              className={`inline-flex items-center px-2 py-0.5 font-semibold ${
                item.trustLevel === "high"
                  ? "bg-(--color-paper-2) text-(--color-ink)"
                  : item.trustLevel === "medium"
                    ? "bg-(--color-paper-2) text-(--color-warn)"
                    : "bg-(--color-paper-2) text-(--color-error)"
              }`}
            >
              {item.trustLevel}{" "}
              {item.trustScore != null ? Math.round(item.trustScore) : ""}
            </span>
          )}
          {item.trustLevel === "low" && (
            <span className="text-[11px] font-medium text-(--color-error)">
              Limited data — interpret with caution.
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3.5 text-(--color-muted)">{country}</td>
      <td className="px-4 py-3.5 text-right font-mono font-semibold text-(--color-ink)">
        <div>{item.scoreLabel}</div>
        <div className="mt-0.5 text-[11px] font-sans font-medium text-(--color-muted)">
          {item.scoreCaption}
        </div>
      </td>
      <td className="px-4 py-3.5 text-center">
        <span className="inline-flex items-center bg-(--color-paper-2) px-2.5 py-0.5 text-xs font-medium text-(--color-ink)">
          {item.sourceCoverageLabel}
        </span>
        <div className="mt-1 text-[11px] text-(--color-muted)">
          {item.rankingUniverseLabel}
        </div>
        {item.aggregationExplain && item.aggregationExplain.availableSourceCount > 0 && (
          <details className="mt-2 text-left">
            <summary className="cursor-pointer text-[11px] font-medium text-(--color-ink)">
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
          className={`h-7 w-7 text-sm font-bold transition ${
            inShortlist
              ? "bg-(--color-ink) text-white"
              : "bg-(--color-paper) text-(--color-muted) hover:bg-(--color-paper-2) hover:text-(--color-ink)"
          }`}
        >
          {inShortlist ? "✓" : "+"}
        </button>
      </td>
    </tr>
  );
}
