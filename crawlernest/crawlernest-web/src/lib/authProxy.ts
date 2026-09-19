import { getApiBaseUrl } from "@/lib/api";
import { NextResponse } from "next/server";

const TIMEOUT_MS = 10_000;

async function proxy(
  method: "GET" | "POST" | "DELETE",
  path: string,
  body?: string,
  cookieHeader?: string
): Promise<NextResponse> {
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const res = await fetch(`${getApiBaseUrl()}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(cookieHeader ? { Cookie: cookieHeader } : {}),
      },
      ...(body !== undefined ? { body } : {}),
      signal: controller.signal,
    });
    clearTimeout(tid);

    const text = await res.text();
    const response = new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });

    // Forward the API's cookie to the browser. It carries the signed token
    // (crawlernest_token); http-only, so the page never reads it itself, and
    // SameSite=Strict, which the browser evaluates against this origin.
    const rawSetCookie = res.headers.get("set-cookie");
    if (rawSetCookie) {
      response.headers.set("Set-Cookie", rawSetCookie);
    }

    return response;
  } catch (err) {
    clearTimeout(tid);
    const isTimeout = err instanceof Error && err.name === "AbortError";
    return NextResponse.json(
      {
        success: false,
        error: isTimeout
          ? "Request timed out."
          : "Authentication service unavailable.",
      },
      { status: 503 }
    );
  }
}

export const proxyPost = (path: string, body: string, cookieHeader?: string) =>
  proxy("POST", path, body, cookieHeader);

export const proxyGet = (path: string, cookieHeader?: string) =>
  proxy("GET", path, undefined, cookieHeader);

export const proxyDelete = (path: string, cookieHeader?: string) =>
  proxy("DELETE", path, undefined, cookieHeader);
