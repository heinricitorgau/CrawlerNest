import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export async function GET(request: NextRequest) {
  const apiBaseUrl = getApiBaseUrl();
  const upstreamUrl = new URL("/api/v1/rankings", apiBaseUrl);

  request.nextUrl.searchParams.forEach((value, key) => {
    upstreamUrl.searchParams.set(key, value);
  });

  try {
    const upstreamResponse = await fetch(upstreamUrl.toString(), {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    const rawBody = await upstreamResponse.text();

    return new NextResponse(rawBody, {
      status: upstreamResponse.status,
      headers: {
        "content-type":
          upstreamResponse.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      {
        success: false,
        error: "Unable to load rankings. Please confirm the API server is running.",
      },
      { status: 502 }
    );
  }
}
