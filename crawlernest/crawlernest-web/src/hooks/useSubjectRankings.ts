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

export function useSubjectRankings({
  subject,
  year,
  page,
  pageSize,
  country = "",
  search = "",
}: Params) {
  const [items, setItems] = useState<SubjectRankingRow[]>([]);
  const [metadata, setMetadata] = useState<Partial<SubjectRankingMetadata>>({});
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!subject) {
      setItems([]);
      setMetadata({});
      setTotalCount(0);
      setLoading(false);
      return;
    }

    let isMounted = true;
    const controller = new AbortController();

    async function fetchSubjectRankings() {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          subject,
          year: String(year),
          page: String(page),
          pageSize: String(pageSize),
          ...(country.trim() ? { country: country.trim() } : {}),
          ...(search.trim() ? { search: search.trim() } : {}),
          _ts: Date.now().toString(),
        });

        const response = await fetch(`/api/subject-rankings?${params.toString()}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        const payload = (await response.json()) as SubjectRankingsApiResponse;

        if (!response.ok || payload.success === false) {
          throw new Error(
            payload?.data?.error ||
              payload?.error ||
              `Subject rankings request failed with HTTP ${response.status}`
          );
        }

        if (isMounted) {
          const resolvedItems = Array.isArray(payload.data?.items)
            ? payload.data.items
            : [];
          const resolvedMetadata =
            payload.data?.metadata && typeof payload.data.metadata === "object"
              ? payload.data.metadata
              : {};

          setItems(resolvedItems);
          setMetadata(resolvedMetadata);
          setTotalCount(
            typeof resolvedMetadata.totalCount === "number"
              ? resolvedMetadata.totalCount
              : resolvedItems.length
          );
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }

        if (isMounted) {
          setItems([]);
          setMetadata({});
          setTotalCount(0);
          setError(
            err instanceof Error && err.message
              ? err.message
              : "Failed to load subject rankings."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchSubjectRankings();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [country, page, pageSize, search, subject, year]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(totalCount / pageSize)),
    [pageSize, totalCount]
  );

  return {
    items,
    metadata,
    totalCount,
    loading,
    error,
    totalPages,
  };
}
