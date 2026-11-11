import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

/**
 * GET /api/universities/{id}/rank-history -> /api/v1/universities/{id}/rank-history, for client components (the
 * compare page). The segment is named [slug] because it shares a folder with the slug route; here it must be the
 * numeric canonical id, and anything else is refused before reaching the API.
 */
export async function GET(_request: NextRequest, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (!/^\d+$/.test(slug)) {
    return NextResponse.json({ success: false, error: "A numeric university id is required." }, { status: 400 });
  }
  const upstreamUrl = new URL(`/api/v1/universities/${slug}/rank-history`, getApiBaseUrl());
  try {
    const upstream = await fetch(upstreamUrl.toString(), { cache: "no-store", headers: { Accept: "application/json" } });
    return new NextResponse(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { success: false, error: "Unable to load the rank history. Please confirm the API server is running." },
      { status: 502 }
    );
  }
}
