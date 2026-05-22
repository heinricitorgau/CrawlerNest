import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const LOCAL_BACKEND_CANDIDATES = [
  "http://localhost:8080",
  "http://127.0.0.1:8080",
  "http://[::1]:8080",
] as const;

export async function GET(request: NextRequest) {
  const configuredBase = getApiBaseUrl();
  const candidates: string[] = (() => {
    try {
      const u = new URL(configuredBase);
      if (
        u.origin === "http://localhost:8080" ||
        u.origin === "http://127.0.0.1:8080"
      ) {
        return [...LOCAL_BACKEND_CANDIDATES];
      }
      return [u.origin];
    } catch {
      return [...LOCAL_BACKEND_CANDIDATES];
    }
  })();

  const params = request.nextUrl.searchParams.toString();

  for (const base of candidates) {
    try {
      const upstreamUrl = `${base}/api/v1/recommendations/explain${params ? `?${params}` : ""}`;
      const res = await fetch(upstreamUrl, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      const body = await res.text();
      return new NextResponse(body, {
        status: res.status,
        headers: {
          "content-type": res.headers.get("content-type") ?? "application/json",
          "Cache-Control": "no-store",
        },
      });
    } catch {
      // try next candidate
    }
  }

  return NextResponse.json(
    { success: false, error: "API server unavailable" },
    { status: 502 }
  );
}
