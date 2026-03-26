import { RankingsResponse } from "@/types/rankings";

export async function fetchRankings(): Promise<RankingsResponse> {
  const res = await fetch(
    "http://localhost:8080/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2026",
    {
      cache: "no-store",
    }
  );

  if (!res.ok) {
    throw new Error("Failed to fetch rankings");
  }

  return res.json();
}