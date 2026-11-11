import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

/** GET /api/analytics/source-movers?source=&year=&limit= -> the read-only API endpoint of the same name. */
export async function GET(request: NextRequest) {
  const upstream = new URL("/api/v1/analytics/source-movers", getApiBaseUrl());
  for (const key of ["source", "year", "limit"]) {
    const value = request.nextUrl.searchParams.get(key);
    if (value) upstream.searchParams.set(key, value);
  }
  try {
    const res = await fetch(upstream.toString(), { cache: "no-store", headers: { Accept: "application/json" } });
    return new NextResponse(await res.text(), {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json({ success: false, error: "API server unavailable" }, { status: 502 });
  }
}
