"use client";

import Link from "next/link";
import { formatRank, formatScore } from "@/lib/format";

type RankingItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  compositeScore: number;
  sourceCount: number;
  slug: string;
};

interface RankingTableProps {
  items: RankingItem[];
}

export default function RankingTable({ items }: RankingTableProps) {
  return (
    <div className="overflow-x-auto border border-gray-200 rounded-lg shadow-sm bg-white">
      <table className="ranking-table min-w-full">
        <thead>
          <tr>
            <th className="w-20 text-center">Rank</th>
            <th>University</th>
            <th>Location</th>
            <th className="w-32 text-right">Agg. Score</th>
            <th className="w-32 text-center">Sources</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-20 text-center text-slate-500 italic">
                No universities found matching your criteria.
              </td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.canonicalUniversityId} className="group">
                <td className="text-center font-bold text-slate-900 border-r border-gray-50">
                  {formatRank(item.aggregatedRank)}
                </td>
                <td className="font-medium">
                  <Link 
                    href={`/universities/${item.slug}`}
                    className="text-blue-600 hover:text-blue-800 hover:underline underline-offset-4 decoration-2 decoration-blue-100 transition-colors"
                  >
                    {item.universityName}
                  </Link>
                </td>
                <td className="text-slate-600">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400">📍</span>
                    {item.country}
                  </div>
                </td>
                <td className="text-right font-mono font-semibold text-slate-700">
                  {formatScore(item.compositeScore)}
                </td>
                <td className="text-center">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-800 border border-slate-200">
                    {item.sourceCount} sources
                  </span>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
