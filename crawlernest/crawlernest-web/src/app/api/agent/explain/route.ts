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

  // Honour whatever the caller asked for rather than choosing here, so the
  // component decides between the streaming and one-shot transports and this
  // route stays a proxy.
  const wantsStream = (request.headers.get("accept") ?? "").includes(
    "text/event-stream"
  );

  try {
    const response = await fetch(backendUrl, {
      method: "POST",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Accept: wantsStream ? "text/event-stream" : "application/json",
      },
      body: JSON.stringify(payload),
    });

    const contentType =
      response.headers.get("content-type") ?? "application/json";

    // Pass the body through unread. Calling response.text() here would wait for
    // the upstream to finish before sending anything, which is the one thing a
    // stream must not do -- the page would sit silent and then paint the whole
    // explanation at once, exactly as it did before there was a stream.
    if (contentType.includes("text/event-stream") && response.body) {
      return new NextResponse(response.body, {
        status: response.status,
        headers: {
          "content-type": contentType,
          // Next buffers a streamed response behind a compressing proxy unless
          // told not to; without this the deltas arrive in one burst.
          "X-Accel-Buffering": "no",
          ...NO_STORE_HEADERS,
        },
      });
    }

    const rawBody = await response.text();

    return new NextResponse(rawBody, {
      status: response.status,
      headers: {
        "content-type": contentType,
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
