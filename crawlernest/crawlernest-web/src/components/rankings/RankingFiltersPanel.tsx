"use client";

import { useEffect, useRef, useState } from "react";

import { normalizeCountryName } from "@/lib/regionMap";
import type { RankingCountryOption, RankingScope } from "@/types/ranking";

type Props = {
  year: number;
  scope: RankingScope;
  region: string;
  country: string;
  pageSize: number;
  countryOptions: RankingCountryOption[];
  regionOptions: string[];
  onUpdate: (updates: Record<string, string | number | null>) => void;
};

export default function RankingFiltersPanel({
  year,
  scope,
  region,
  country,
  pageSize,
  countryOptions,
  regionOptions,
  onUpdate,
}: Props) {
  const countryFilterRef = useRef<HTMLDivElement | null>(null);
  const [countryFilterOpen, setCountryFilterOpen] = useState(false);
  const [countryFilterSearch, setCountryFilterSearch] = useState("");

  // A new scope, region or country closes and clears the country picker. Adjusted during render when the filter
  // changes (React's pattern for resetting state on a prop change), rather than in an effect after it.
  const filterKey = `${scope}|${region}|${country}`;
  const [seenFilterKey, setSeenFilterKey] = useState(filterKey);
  if (seenFilterKey !== filterKey) {
    setSeenFilterKey(filterKey);
    setCountryFilterSearch("");
    setCountryFilterOpen(false);
  }

  useEffect(() => {
    if (!countryFilterOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!countryFilterRef.current?.contains(event.target as Node)) {
        setCountryFilterOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [countryFilterOpen]);

  const countryFilterLabel =
    scope === "region" ? `${region} Countries` : "Country";
  const countryPlaceholder =
    scope === "region" ? `All countries in ${region}` : "All countries";
  const countrySearchPlaceholder =
    scope === "region"
      ? `Search countries in ${region}...`
      : "Search countries...";
  const selectedCountryOption = country
    ? countryOptions.find(
        (option) =>
          normalizeCountryName(option.name) === normalizeCountryName(country) ||
          (option.code !== null && option.code === country)
      ) ?? null
    : null;
  const selectedCountryValue =
    selectedCountryOption?.name ?? normalizeCountryName(country);
  const normalizedCountrySearch = countryFilterSearch.trim().toLowerCase();
  const visibleCountryOptions = normalizedCountrySearch
    ? countryOptions.filter((option) =>
        option.name.toLowerCase().includes(normalizedCountrySearch)
      )
    : countryOptions;

  return (
    <div className="rounded-2xl border border-(--color-rule) bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-xs font-bold text-(--color-muted)">
        Filters
      </h3>

      <div className="mb-5">
        <label className="mb-1.5 block text-xs font-semibold text-(--color-ink)">
          Year
        </label>
        <select
          value={year}
          onChange={(e) => onUpdate({ year: e.target.value, page: 1 })}
          className="w-full rounded-lg border border-(--color-rule) bg-(--color-paper) px-3 py-2 text-sm outline-none transition focus:border-(--color-ink)"
        >
          <option value="2026">2026</option>
          <option value="2025">2025</option>
          <option value="2024">2024</option>
        </select>
      </div>

      <div className="mb-5">
        <label className="mb-1.5 block text-xs font-semibold text-(--color-ink)">
          Scope
        </label>
        <div className="flex overflow-hidden rounded-lg border border-(--color-rule)">
          {(["global", "region"] as const).map((nextScope) => (
            <button
              key={nextScope}
              onClick={() =>
                onUpdate({
                  scope: nextScope,
                  region: nextScope === "global" ? null : region,
                  country: null,
                  page: 1,
                })
              }
              className={`flex-1 py-2 text-xs font-semibold capitalize transition ${
                scope === nextScope
                  ? "bg-(--color-ink) text-white"
                  : "bg-white text-(--color-muted) hover:bg-(--color-paper)"
              }`}
            >
              {nextScope}
            </button>
          ))}
        </div>
      </div>

      {scope === "region" && (
        <div className="mb-5">
          <label className="mb-1.5 block text-xs font-semibold text-(--color-ink)">
            Region
          </label>
          <select
            value={region}
            onChange={(e) =>
              onUpdate({ region: e.target.value, country: null, page: 1 })
            }
            className="w-full rounded-lg border border-(--color-rule) bg-(--color-paper) px-3 py-2 text-sm outline-none transition focus:border-(--color-ink)"
          >
            {regionOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="mb-5">
        <label className="mb-1.5 block text-xs font-semibold text-(--color-ink)">
          {countryFilterLabel}
        </label>
        <div ref={countryFilterRef} className="relative">
          <button
            type="button"
            onClick={() => setCountryFilterOpen((value) => !value)}
            className="flex w-full items-center justify-between rounded-lg border border-(--color-rule) bg-(--color-paper) px-3 py-2 text-sm outline-none transition hover:border-(--color-ink) focus:border-(--color-ink)"
            aria-expanded={countryFilterOpen}
            aria-haspopup="listbox"
          >
            <span className="truncate text-left text-(--color-ink)">
              {selectedCountryValue || countryPlaceholder}
            </span>
            <span className="ml-2 text-xs text-(--color-muted)">
              {countryFilterOpen ? "▲" : "▼"}
            </span>
          </button>

          {countryFilterOpen && (
            <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-30 rounded-xl border border-(--color-rule) bg-white p-3 shadow-lg">
              <input
                type="text"
                value={countryFilterSearch}
                onChange={(e) => setCountryFilterSearch(e.target.value)}
                placeholder={countrySearchPlaceholder}
                className="w-full rounded-lg border border-(--color-rule) bg-(--color-paper) px-3 py-2 text-sm outline-none transition focus:border-(--color-ink) focus:bg-white"
              />

              <div className="mt-3 max-h-56 overflow-y-auto rounded-lg border border-(--color-rule) bg-(--color-paper)">
                <button
                  type="button"
                  onClick={() => {
                    onUpdate({ country: null, page: 1 });
                    setCountryFilterOpen(false);
                  }}
                  className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition hover:bg-white ${
                    !selectedCountryValue
                      ? "bg-white font-semibold text-(--color-ink)"
                      : "text-(--color-ink)"
                  }`}
                >
                  <span>{countryPlaceholder}</span>
                  {!selectedCountryValue && (
                    <span className="text-xs text-(--color-ink)">Selected</span>
                  )}
                </button>

                {visibleCountryOptions.length > 0 ? (
                  visibleCountryOptions.map((option) => {
                    const isSelected = selectedCountryValue === option.name;
                    return (
                      <button
                        key={option.code ?? option.name}
                        type="button"
                        onClick={() => {
                          onUpdate({ country: option.name, page: 1 });
                          setCountryFilterOpen(false);
                        }}
                        className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm transition hover:bg-white ${
                          isSelected
                            ? "bg-white font-semibold text-(--color-ink)"
                            : "text-(--color-ink)"
                        }`}
                      >
                        <span className="truncate">{option.name}</span>
                        <span className="ml-3 text-xs text-(--color-muted)">
                          {option.count}
                        </span>
                      </button>
                    );
                  })
                ) : (
                  <div className="px-3 py-4 text-sm italic text-(--color-muted)">
                    No countries match your search.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mb-5">
        <label className="mb-1.5 block text-xs font-semibold text-(--color-ink)">
          Per Page
        </label>
        <select
          value={pageSize}
          onChange={(e) => onUpdate({ pageSize: e.target.value, page: 1 })}
          className="w-full rounded-lg border border-(--color-rule) bg-(--color-paper) px-3 py-2 text-sm outline-none transition focus:border-(--color-ink)"
        >
          <option value="20">20</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select>
      </div>

      <button
        onClick={() =>
          onUpdate({
            scope: "global",
            region: null,
            country: null,
            year: 2026,
            search: null,
            page: 1,
          })
        }
        className="w-full rounded-lg border border-(--color-rule) py-2 text-xs font-semibold text-(--color-muted) transition hover:border-(--color-ink) hover:text-(--color-ink)"
      >
        Reset Filters
      </button>
    </div>
  );
}
