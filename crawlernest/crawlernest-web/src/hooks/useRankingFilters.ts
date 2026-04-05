"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { countryBelongsToRegion, normalizeCountryName } from "@/lib/regionMap";
import type {
  RankingApiRow,
  RankingCountryOption,
  RankingsApiMetadata,
  RankingScope,
} from "@/types/ranking";

export function useRankingFilters(
  items: RankingApiRow[],
  metadata: RankingsApiMetadata
) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isClientReady, setIsClientReady] = useState(false);
  const [searchInput, setSearchInput] = useState("");

  useEffect(() => {
    setIsClientReady(true);
  }, []);

  const scope = isClientReady
    ? ((searchParams.get("scope") as RankingScope) ?? "global")
    : "global";
  const region = isClientReady ? (searchParams.get("region") ?? "Europe") : "Europe";
  const year = isClientReady ? Number(searchParams.get("year") ?? "2026") : 2026;
  const page = isClientReady ? Number(searchParams.get("page") ?? "1") : 1;
  const pageSize = isClientReady ? Number(searchParams.get("pageSize") ?? "20") : 20;
  const searchQuery = isClientReady ? (searchParams.get("search") ?? "") : "";
  const country = isClientReady ? (searchParams.get("country") ?? "") : "";
  const normalizedSelectedCountry = normalizeCountryName(country);

  const countryOptions = useMemo<RankingCountryOption[]>(() => {
    const metadataOptions = Array.isArray(metadata.countryOptions)
      ? metadata.countryOptions
      : [];

    if (metadataOptions.length > 0) {
      return metadataOptions
        .filter((option) => {
          const normalizedCountry = normalizeCountryName(option.name);
          if (!normalizedCountry) {
            return false;
          }
          if (scope === "region") {
            return countryBelongsToRegion(normalizedCountry, region);
          }
          return true;
        })
        .map((option) => ({
          code: option.code ?? null,
          name: normalizeCountryName(option.name),
          count: option.count,
        }))
        .filter((option) => Boolean(option.name))
        .sort((left, right) => left.name.localeCompare(right.name));
    }

    if (!Array.isArray(items) || items.length === 0) {
      return [];
    }

    const counts = new Map<string, number>();
    for (const item of items) {
      const rawCountry = typeof item.country === "string" ? item.country : "";
      const normalizedCountry = normalizeCountryName(rawCountry);
      if (!normalizedCountry) {
        continue;
      }
      if (scope === "region" && !countryBelongsToRegion(normalizedCountry, region)) {
        continue;
      }
      counts.set(normalizedCountry, (counts.get(normalizedCountry) ?? 0) + 1);
    }

    return Array.from(counts.entries())
      .map(([name, count]) => ({ code: null, name, count }))
      .sort((left, right) => left.name.localeCompare(right.name));
  }, [items, metadata.countryOptions, region, scope]);

  useEffect(() => {
    setSearchInput(searchQuery);
  }, [searchQuery]);

  const navigate = useCallback(
    (updates: Record<string, string | number | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === "") {
          params.delete(key);
        } else {
          params.set(key, String(value));
        }
      }
      router.replace(`/?${params.toString()}`);
    },
    [router, searchParams]
  );

  useEffect(() => {
    if (!isClientReady) {
      return;
    }
    const hasStaleRegion = scope === "global" && searchParams.has("region");
    const hasDependentCountry = hasStaleRegion && searchParams.has("country");
    if (hasStaleRegion || hasDependentCountry) {
      navigate({ region: null, country: null, page: 1 });
    }
  }, [isClientReady, navigate, scope, searchParams]);

  useEffect(() => {
    if (!isClientReady || !country) {
      return;
    }
    if (countryOptions.length === 0) {
      return;
    }
    const matchingCountry = countryOptions.find(
      (option) =>
        option.code === country ||
        normalizeCountryName(option.name) === normalizedSelectedCountry
    );
    if (!matchingCountry) {
      navigate({ country: null, page: 1 });
      return;
    }
    if (matchingCountry.name !== normalizedSelectedCountry) {
      navigate({ country: matchingCountry.name, page: 1 });
    }
  }, [country, countryOptions, isClientReady, navigate, normalizedSelectedCountry]);

  return {
    isClientReady,
    searchInput,
    setSearchInput,
    scope,
    region,
    year,
    page,
    pageSize,
    searchQuery,
    country,
    normalizedSelectedCountry,
    countryOptions,
    navigate,
  };
}
