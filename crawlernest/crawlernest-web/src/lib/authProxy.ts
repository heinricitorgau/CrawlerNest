import { getApiBaseUrl } from "@/lib/api";
import { headers } from "next/headers";
import { NextResponse } from "next/server";

const TIMEOUT_MS = 10_000;

export type ProxyMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

async function proxy(
  method: ProxyMethod,
  path: string,
  body?: string,
  cookieHeader?: string,
  timeoutMs: number = TIMEOUT_MS
): Promise<NextResponse> {
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), timeoutMs);
  const forwarded = await forwardedFor();

  try {
    const res = await fetch(`${getApiBaseUrl()}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(cookieHeader ? { Cookie: cookieHeader } : {}),
        ...(forwarded ? { "X-Forwarded-For": forwarded } : {}),
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

/**
 * The visitor's address chain, passed on so the API's rate limits count visitors rather than this server.
 * Next.js fills `x-forwarded-for` from the socket when the request has none, and keeps one the request
 * brought: behind a reverse proxy that appends to it, the right-most hop is the visitor; exposed directly,
 * a visitor can write their own. The API believes the header only from its trusted proxies
 * (`CRAWLERNEST_TRUSTED_PROXIES`) and reads the right-most untrusted hop.
 */
async function forwardedFor(): Promise<string | undefined> {
  try {
    const value = (await headers()).get("x-forwarded-for")?.trim();
    return value ? value : undefined;
  } catch {
    // Called outside a request (a test, a script): nothing to forward.
    return undefined;
  }
}

export const proxyPost = (path: string, body: string, cookieHeader?: string) =>
  proxy("POST", path, body, cookieHeader);

export const proxyGet = (path: string, cookieHeader?: string) =>
  proxy("GET", path, undefined, cookieHeader);

export const proxyDelete = (path: string, cookieHeader?: string) =>
  proxy("DELETE", path, undefined, cookieHeader);

/**
 * Any method; `body` undefined sends none. For routes that forward several verbs
 * to one path. `timeoutMs` is for the rare call that waits on a model.
 */
export const proxyRequest = (method: ProxyMethod, path: string, body?: string, cookieHeader?: string, timeoutMs?: number) =>
  proxy(method, path, body, cookieHeader, timeoutMs);
