"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { YEAR_QUERY_PARAM, resolveSelectedYear, type SelectedYear } from "@/lib/datasetScope";

/**
 * The edition selected in the URL, and a way to change it.
 *
 * The URL is the only store: two selectors on one page (the nav and the page's own)
 * read and write the same `?year=`, so they cannot disagree, and a shared link opens
 * on the same edition. Calls `useSearchParams`, so the caller must sit inside a
 * `<Suspense>` boundary or a production build fails.
 */
export function useSelectedYear(): SelectedYear & { setYear: (year: number) => void } {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const searchParams = useSearchParams();
  const selected = resolveSelectedYear(searchParams?.get(YEAR_QUERY_PARAM));

  const setYear = useCallback(
    (year: number) => {
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      params.set(YEAR_QUERY_PARAM, String(year));
      // A page number belongs to the edition it was paging through.
      params.delete("page");
      router.push(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  return { ...selected, setYear };
}
