"use client";

import { useId } from "react";

import { useSelectedYear } from "@/hooks/useSelectedYear";
import { DATASET_YEARS } from "@/lib/datasetScope";

type YearSelectorProps = {
  /** "nav" is compact for the header; "page" matches the pages' filter controls. */
  variant?: "nav" | "page";
  className?: string;
  /**
   * Editions to offer. Defaults to every edition the warehouse holds, which is
   * right for the world-ranking pages. A surface whose data covers fewer
   * editions passes its own list -- the subject page offers only the editions
   * that hold subject rows, so the control cannot propose eleven empty years.
   *
   * This changes what is offered, not how `?year=` is read: which editions exist
   * is a fact about the warehouse and is resolved the same way on every page.
   */
  years?: readonly number[];
};

const SELECT_CLASS: Record<NonNullable<YearSelectorProps["variant"]>, string> = {
  nav: "rounded border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-700 outline-none focus:border-slate-400",
  page: "rounded-xl border border-[#e0ddd8] bg-white px-4 py-3 outline-none transition focus:border-[#1a3d2e]",
};

/**
 * Choose which ranking edition a page shows. Only held editions are offered, so
 * the control cannot select a year that returns nothing; a link that names one
 * anyway gets a visible note rather than a silently different year.
 *
 * Uses `useSearchParams`: render inside `<Suspense>`, with
 * {@link YearSelectorFallback} as the fallback.
 */
export function YearSelector({
  variant = "page",
  className = "",
  years = DATASET_YEARS,
}: YearSelectorProps) {
  const id = useId();
  const noteId = `${id}-note`;
  const { year, requested, requestedHeld, setYear } = useSelectedYear();
  // The selected edition is always offered, even when it is not one this
  // surface has data for: a select whose value is absent from its options
  // renders blank and hides which edition the page is actually showing.
  const options = years.includes(year) ? years : [...years, year].sort((a, b) => b - a);

  return (
    <div className={`flex flex-col gap-1 ${className}`.trim()}>
      <div className={variant === "nav" ? "flex items-center gap-2" : "flex flex-col gap-2"}>
        <label
          htmlFor={id}
          className={variant === "nav" ? "text-xs font-medium text-slate-500" : "text-sm font-medium text-[#1a3d2e]"}
        >
          {variant === "nav" ? "Edition" : "Ranking edition"}
        </label>
        <select
          id={id}
          className={SELECT_CLASS[variant]}
          value={year}
          aria-describedby={requestedHeld ? undefined : noteId}
          onChange={(event) => setYear(Number(event.target.value))}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
      {requestedHeld ? null : (
        <p id={noteId} role="status" className="text-xs text-[#8a6116]">
          No {requested} edition is held. Showing {year}.
        </p>
      )}
    </div>
  );
}

/** What renders before the URL is readable: the default edition, disabled. */
export function YearSelectorFallback({
  variant = "page",
  className = "",
  years = DATASET_YEARS,
}: YearSelectorProps) {
  const first = years[0] ?? DATASET_YEARS[0];
  return (
    <div className={`flex flex-col gap-1 ${className}`.trim()} aria-hidden="true">
      <div className={variant === "nav" ? "flex items-center gap-2" : "flex flex-col gap-2"}>
        <span className={variant === "nav" ? "text-xs font-medium text-slate-500" : "text-sm font-medium text-[#1a3d2e]"}>
          {variant === "nav" ? "Edition" : "Ranking edition"}
        </span>
        <select className={SELECT_CLASS[variant]} disabled value={first} onChange={() => {}}>
          <option value={first}>{first}</option>
        </select>
      </div>
    </div>
  );
}
