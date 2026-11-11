"use client";

import { useEffect, useMemo, useState } from "react";

import type {
  SubjectRankingMetadata,
  SubjectRankingRow,
  SubjectRankingsApiResponse,
} from "@/types/subjectRanking";

type Params = {
  subject: string;
  year: number;
  page: number;
  pageSize: number;
  country?: string;
  search?: string;
};

type Settled = {
  key: string;
  items: SubjectRankingRow[];
  metadata: Partial<SubjectRankingMetadata>;
  totalCount: number;
  error: string | null;
};

const EMPTY_ITEMS: SubjectRankingRow[] = [];
const EMPTY_METADATA: Partial<SubjectRankingMetadata> = {};

/**
 * One subject's rankings for the given page and filters.
 *
 * Each settled response is kept with the request it answers, so "loading" is derived (the kept result is for
 * another request) and no state is reset at the start of the effect; with no subject chosen, nothing is fetched
 * and the result is empty by derivation.
 */
export function useSubjectRankings({
  subject,
  year,
  page,
  pageSize,
  country = "",
  search = "",
}: Params) {
  const key = JSON.stringify([subject, year, page, pageSize, country.trim(), search.trim()]);
  const [settled, setSettled] = useState<Settled | null>(null);

  useEffect(() => {
    if (!subject) return;
    let cancelled = false;
    const controller = new AbortController();
    const params = new URLSearchParams({
      subject,
      year: String(year),
      page: String(page),
      pageSize: String(pageSize),
      ...(country.trim() ? { country: country.trim() } : {}),
      ...(search.trim() ? { search: search.trim() } : {}),
      _ts: Date.now().toString(),
    });

    fetch(`/api/subject-rankings?${params.toString()}`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        const payload = (await response.json()) as SubjectRankingsApiResponse;
        if (!response.ok || payload.success === false) {
          throw new Error(
            payload?.data?.error || payload?.error || `Subject rankings request failed with HTTP ${response.status}`
          );
        }
        const items = Array.isArray(payload.data?.items) ? payload.data.items : [];
        const metadata =
          payload.data?.metadata && typeof payload.data.metadata === "object" ? payload.data.metadata : {};
        if (!cancelled) {
          setSettled({
            key,
            items,
            metadata,
            totalCount: typeof metadata.totalCount === "number" ? metadata.totalCount : items.length,
            error: null,
          });
        }
      })
      .catch((err: unknown) => {
        if (cancelled || (err instanceof Error && err.name === "AbortError")) return;
        setSettled({
          key,
          items: [],
          metadata: {},
          totalCount: 0,
          error: err instanceof Error && err.message ? err.message : "Failed to load subject rankings.",
        });
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [key, country, page, pageSize, search, subject, year]);

  const current = subject && settled?.key === key ? settled : null;
  // While the next request is in flight the last rows stay on screen, as before; with no subject there are none.
  const shown = subject ? (current ?? settled) : null;
  const totalCount = shown?.totalCount ?? 0;
  const totalPages = useMemo(() => Math.max(1, Math.ceil(totalCount / pageSize)), [pageSize, totalCount]);

  return {
    items: shown?.items ?? EMPTY_ITEMS,
    metadata: shown?.metadata ?? EMPTY_METADATA,
    totalCount,
    loading: Boolean(subject) && current === null,
    error: current?.error ?? null,
    totalPages,
  };
}
