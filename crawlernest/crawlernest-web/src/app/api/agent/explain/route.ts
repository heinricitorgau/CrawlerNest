import { NextRequest, NextResponse } from "next/server";

import { getAgentApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
  Pragma: "no-cache",
  Expires: "0",
};

/**
 * Proxy to the agent's explain-only route.
 *
 * The agent turns rows the page is already displaying into prose; it does not
 * query the warehouse or recompute anything, so the explanation always
 * describes exactly what the user is looking at. The explanation is a
 * progressive enhancement: when the agent is unreachable this route answers 502
 * and the page simply renders without it.
 */
export async function POST(request: NextRequest) {
  const backendUrl = `${getAgentApiBaseUrl()}/api/v1/agent/explain`;

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      {
        success: false,
        error: "Invalid JSON body",
      },
      {
        status: 400,
        headers: NO_STORE_HEADERS,
      }
    );
  }

  try {
    const response = await fetch(backendUrl, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
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
        error: "Failed to reach agent API",
      },
      {
        status: 502,
        headers: NO_STORE_HEADERS,
      }
    );
  }
}
