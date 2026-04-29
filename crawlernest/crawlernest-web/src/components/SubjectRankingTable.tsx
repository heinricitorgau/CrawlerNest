"use client";

import Link from "next/link";

import type { SubjectRankingRow } from "@/types/subjectRanking";

type Props = {
  items: SubjectRankingRow[];
  loading: boolean;
};

function formatScore(score?: number | null) {
  if (typeof score !== "number" || !Number.isFinite(score)) {
    return "-";
  }

  return score.toFixed(1);
}

export default function SubjectRankingTable({ items, loading }: Props) {
  const safeItems = Array.isArray(items) ? items : [];

  return (
    <div className="overflow-x-auto border border-gray-200 bg-white shadow-sm">
      <table className="ranking-table min-w-full">
        <thead>
          <tr>
            <th className="w-24 text-center">Rank</th>
            <th>University</th>
            <th>Country</th>
            <th className="w-32 text-right">Score</th>
            <th className="w-28 text-center">Source</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 6 }).map((_, index) => (
              <tr key={`subject-ranking-loading-${index}`}>
                <td colSpan={5} className="px-4 py-4">
                  <div className="h-6 animate-pulse bg-gray-100" />
                </td>
              </tr>
            ))
          ) : safeItems.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-20 text-center text-slate-500">
                No subject ranking data available for this selection.
              </td>
            </tr>
          ) : (
            safeItems.map((item) => {
              const universityHref = item.canonicalSlug
                ? `/universities/${item.canonicalSlug}`
                : "#";

              return (
                <tr
                  key={`${item.subjectKey}-${item.rankingYear}-${item.canonicalUniversityId}-${item.rankPosition}`}
                >
                  <td className="border-r border-gray-50 text-center font-bold text-slate-900">
                    {item.rankDisplay || item.rankPosition}
                  </td>
                  <td className="font-medium">
                    {item.canonicalSlug ? (
                      <Link
                        href={universityHref}
                        className="text-blue-600 underline-offset-4 transition-colors hover:text-blue-800 hover:underline"
                      >
                        {item.universityName || "Unknown university"}
                      </Link>
                    ) : (
                      <span>{item.universityName || "Unknown university"}</span>
                    )}
                    <div className="mt-1 text-xs text-slate-500">
                      {item.subjectName}
                    </div>
                  </td>
                  <td className="text-slate-600">{item.countryName || "-"}</td>
                  <td className="text-right font-mono font-semibold text-slate-700">
                    {formatScore(item.score)}
                  </td>
                  <td className="text-center">
                    <span className="inline-flex min-w-12 justify-center border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold text-slate-700">
                      {item.sourceCode || "QS"}
                    </span>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
