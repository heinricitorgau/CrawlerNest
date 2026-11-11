"use client";

import { useEffect, useState } from "react";

/**
 * GET a CrawlerNest JSON endpoint (`{ success, data, metadata: { caveats } }`) and follow its state.
 *
 * Each settled result is kept with the path it answers. "Loading" is derived -- the stored result is for another
 * path, or there is none -- instead of being set at the start of the effect, so a new path never shows the previous
 * path's data and the effect only ever sets state from the response. Replaces three copies of the same hook
 * (analytics, data quality, system status).
 */

export type ApiResource<T> =
  | { status: "loading" }
  | { status: "ok"; data: T; caveats: string[] }
  | { status: "error"; message: string };

type Settled<T> = { path: string; result: Exclude<ApiResource<T>, { status: "loading" }> };

export function useApiResource<T>(path: string): ApiResource<T> {
  const [settled, setSettled] = useState<Settled<T> | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(path, { cache: "no-store" })
      .then(async (res) => {
        const json = (await res.json()) as {
          success?: boolean;
          data?: T;
          metadata?: { caveats?: string[] };
          error?: string;
        };
        if (cancelled) return;
        setSettled({
          path,
          result:
            !res.ok || json.success === false
              ? { status: "error", message: json.error ?? `HTTP ${res.status}` }
              : { status: "ok", data: json.data as T, caveats: json.metadata?.caveats ?? [] },
        });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSettled({ path, result: { status: "error", message: err instanceof Error ? err.message : "Fetch failed" } });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  return settled?.path === path ? settled.result : { status: "loading" };
}
