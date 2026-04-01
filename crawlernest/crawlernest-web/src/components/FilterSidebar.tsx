"use client";

import { useState } from "react";

interface FilterSidebarProps {
  currentFilters: {
    countries: string[];
    range: string;
    sources: string[];
  };
  onFilterChange: (newFilters: { countries: string[]; range: string; sources: string[] }) => void;
}

const RANGE_OPTIONS = [
  { label: "Top 100", value: "100" },
  { label: "Top 200", value: "200" },
  { label: "Top 500", value: "500" },
  { label: "All", value: "all" },
];

const SOURCE_OPTIONS = [
  { label: "QS World University Rankings", value: "QS" },
  { label: "Times Higher Education (THE)", value: "THE" },
];

export default function FilterSidebar({
  currentFilters,
  onFilterChange,
}: FilterSidebarProps) {
  const [isSourceOpen, setIsSourceOpen] = useState(true);
  const [isRangeOpen, setIsRangeOpen] = useState(true);

  const toggleSource = (source: string) => {
    const nextSources = currentFilters.sources.includes(source)
      ? currentFilters.sources.filter((s) => s !== source)
      : [...currentFilters.sources, source];
    onFilterChange({ ...currentFilters, sources: nextSources });
  };

  const setRange = (range: string) => {
    onFilterChange({ ...currentFilters, range });
  };

  return (
    <aside className="w-64 flex-shrink-0 space-y-6">
      {/* ── Filter Header ── */}
      <div className="flex items-center justify-between pb-4 border-b border-gray-200">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">
          Refine Results
        </h3>
        <button
          onClick={() => onFilterChange({ countries: [], range: "all", sources: ["QS", "THE"] })}
          className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors"
        >
          Reset All
        </button>
      </div>

      {/* ── Ranking Sources ── */}
      <div className="space-y-3">
        <button
          onClick={() => setIsSourceOpen(!isSourceOpen)}
          className="flex w-full items-center justify-between text-sm font-bold text-slate-800"
        >
          <span>Ranking Source</span>
          <span className="text-xs text-slate-400">
            {isSourceOpen ? "▲" : "▼"}
          </span>
        </button>
        {isSourceOpen && (
          <div className="space-y-2 pl-1">
            {SOURCE_OPTIONS.map((opt) => (
              <label key={opt.value} className="flex items-center gap-3 group cursor-pointer">
                <input
                  type="checkbox"
                  checked={currentFilters.sources.includes(opt.value)}
                  onChange={() => toggleSource(opt.value)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-slate-600 group-hover:text-slate-900 transition-colors">
                  {opt.label}
                </span>
              </label>
            ))}
          </div>
        )}
      </div>

      {/* ── Ranking Range ── */}
      <div className="space-y-3">
        <button
          onClick={() => setIsRangeOpen(!isRangeOpen)}
          className="flex w-full items-center justify-between text-sm font-bold text-slate-800"
        >
          <span>Ranking Range</span>
          <span className="text-xs text-slate-400">
            {isRangeOpen ? "▲" : "▼"}
          </span>
        </button>
        {isRangeOpen && (
          <div className="grid grid-cols-2 gap-2">
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setRange(opt.value)}
                className={`py-1.5 px-2 text-xs font-medium rounded border transition-all ${
                  currentFilters.range === opt.value
                    ? "bg-blue-50 border-blue-200 text-blue-700 shadow-sm"
                    : "bg-white border-gray-200 text-slate-600 hover:border-gray-300"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Country Filter ── */}
      <div className="space-y-3 pt-4 border-t border-gray-100">
        <h4 className="text-sm font-bold text-slate-800">Country / Region</h4>
        <input
          type="text"
          placeholder="Search locations..."
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
        />
        <p className="text-[10px] text-slate-400 uppercase font-semibold">
          Popular Locations
        </p>
        <div className="flex flex-wrap gap-1.5">
          {["USA", "UK", "Australia", "Canada", "Germany", "Japan"].map((c) => (
            <button
              key={c}
              className="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs text-slate-600 hover:bg-slate-100 transition-colors"
            >
              {c}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
