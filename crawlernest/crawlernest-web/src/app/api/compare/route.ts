import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
  Pragma: "no-cache",
  Expires: "0",
};

export async function POST(request: NextRequest) {
  const apiBaseUrl = getApiBaseUrl();
  const upstreamUrl = new URL("/api/v1/compare", apiBaseUrl);

  try {
    const body = await request.text();
    const upstreamResponse = await fetch(upstreamUrl.toString(), {
      method: "POST",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body,
    });

    const rawBody = await upstreamResponse.text();

    return new NextResponse(rawBody, {
      status: upstreamResponse.status,
      headers: {
        "content-type":
          upstreamResponse.headers.get("content-type") ?? "application/json",
        ...NO_STORE_HEADERS,
      },
    });
  } catch {
    return NextResponse.json(
      {
        success: false,
        error: "Unable to load comparison. Please confirm the API server is running.",
      },
      {
        status: 502,
        headers: NO_STORE_HEADERS,
      }
    );
  }
}
