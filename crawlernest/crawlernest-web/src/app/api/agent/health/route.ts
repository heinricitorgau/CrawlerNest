import { NextResponse } from "next/server";

import { getAgentApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
  Pragma: "no-cache",
  Expires: "0",
};

export async function GET() {
  const backendUrl = `${getAgentApiBaseUrl()}/health`;

  try {
    const response = await fetch(backendUrl, {
      method: "GET",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
    });

    const rawBody = await response.text();

    return new NextResponse(rawBody, {
      status: response.status,
      headers: {
        "content-type":
          response.headers.get("content-type") ?? "application/json",
        ...NO_STORE_HEADERS,
      },
    });
  } catch {
    return NextResponse.json(
      {
        success: false,
        status: "offline",
        error: "Failed to reach agent API",
      },
      {
        status: 502,
        headers: NO_STORE_HEADERS,
      }
    );
  }
}
