import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/api";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const LOCAL_BACKEND_CANDIDATES = [
  "http://localhost:8080",
  "http://127.0.0.1:8080",
  "http://[::1]:8080",
] as const;

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
  Pragma: "no-cache",
  Expires: "0",
};
const UPSTREAM_TIMEOUT_MS = 5000;

function resolveBackendApiBaseUrls(request: NextRequest): string[] {
  const configuredBaseUrl = getApiBaseUrl();

  try {
    const candidateUrl = new URL(configuredBaseUrl);
    const requestOrigin = request.nextUrl.origin;
    const isLocalNextOrigin =
      candidateUrl.origin === requestOrigin ||
      candidateUrl.origin === "http://localhost:3000" ||
      candidateUrl.origin === "http://127.0.0.1:3000";

    if (isLocalNextOrigin) {
      return [...LOCAL_BACKEND_CANDIDATES];
    }

    return [candidateUrl.origin];
  } catch {
    return [...LOCAL_BACKEND_CANDIDATES];
  }
}

export async function GET(request: NextRequest) {
  const apiBaseUrls = resolveBackendApiBaseUrls(request);
  let lastError: unknown = null;

  for (const apiBaseUrl of apiBaseUrls) {
    const upstreamUrl = new URL("/api/v1/subject-rankings", apiBaseUrl);

    request.nextUrl.searchParams.forEach((value, key) => {
      upstreamUrl.searchParams.set(key, value);
    });

    try {
      const upstreamResponse = await fetch(upstreamUrl.toString(), {
        method: "GET",
        cache: "no-store",
        signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
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
          ...NO_STORE_HEADERS,
        },
      });
    } catch (error) {
      lastError = error;
      console.warn(
        "[api/subject-rankings] upstream_fetch_failed via=%s error=%o",
        apiBaseUrl,
        error
      );
    }
  }

  return NextResponse.json(
    {
      success: false,
      error:
        "Unable to load subject rankings. Please confirm the API server is running.",
      debug:
        process.env.NODE_ENV !== "production" && lastError instanceof Error
          ? { message: lastError.message }
          : undefined,
    },
    {
      status: 502,
      headers: NO_STORE_HEADERS,
    }
  );
}
