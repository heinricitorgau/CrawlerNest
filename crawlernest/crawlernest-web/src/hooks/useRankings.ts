"use client";

import { useEffect, useMemo, useState } from "react";

import type { RankingApiRow, RankingsApiMetadata, RankingScope } from "@/types/ranking";

type Params = {
  isClientReady: boolean;
  page: number;
  pageSize: number;
  year: number;
  scope: RankingScope;
  region: string;
  searchQuery: string;
  country: string;
};

export function useRankings({
  isClientReady,
  page,
  pageSize,
  year,
  scope,
  region,
  searchQuery,
  country,
}: Params) {
  const [items, setItems] = useState<RankingApiRow[]>([]);
  const [metadata, setMetadata] = useState<RankingsApiMetadata>({});
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isClientReady) {
      return;
    }

    let isMounted = true;
    const controller = new AbortController();

    async function fetchRankings() {
      setLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          page: String(page),
          pageSize: String(pageSize),
          year: String(year),
          scope,
          ...(scope === "region" ? { region } : {}),
          ...(searchQuery ? { search: searchQuery } : {}),
          ...(country ? { country } : {}),
          _ts: Date.now().toString(),
        });

        const res = await fetch(`/api/rankings?${params.toString()}`, {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const payload = await res.json();

        if (!res.ok || payload?.success === false) {
          throw new Error(payload?.data?.error || `HTTP ${res.status}`);
        }

        if (isMounted) {
          const resolvedItems = Array.isArray(payload?.data?.items) ? payload.data.items : [];
          const resolvedMetadata =
            payload?.data?.metadata && typeof payload.data.metadata === "object"
              ? payload.data.metadata
              : {};

          setItems(resolvedItems);
          setTotalCount(
            typeof resolvedMetadata?.totalCount === "number"
              ? resolvedMetadata.totalCount
              : 0
          );
          setMetadata(resolvedMetadata);
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }

        if (isMounted) {
          const message =
            err instanceof Error && err.message
              ? err.message
              : "Failed to load rankings. Please try again.";
          setError(
            message === "HTTP 500" || message.startsWith("HTTP ")
              ? "Failed to load rankings. Please try again."
              : message
          );
          setItems([]);
          setTotalCount(0);
          setMetadata({});
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchRankings();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [country, isClientReady, page, pageSize, region, scope, searchQuery, year]);

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
