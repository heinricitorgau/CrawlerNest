import { NextResponse, type NextRequest } from "next/server";
import { proxyRequest, type ProxyMethod } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

/**
 * Forwards /api/user/desk/** to the Java DeskController at /api/v1/user/desk/**.
 *
 * One catch-all instead of a file per resource, so the path is checked here
 * before it is joined onto the API URL: lower-case words and numeric ids only,
 * at most three segments. Anything else -- "..", an encoded slash, a query
 * smuggled into a segment -- answers 404 without reaching the API.
 */
const SEGMENT = /^[a-z0-9-]{1,40}$/;
const MAX_SEGMENTS = 3;
const ALLOWED_PARAMS = new Set(["status", "sprintId", "stage", "subject"]);

/**
 * Essay scoring waits on a model: up to the API's 60 s per call, and one retry
 * when the reply is unreadable. Everything else keeps the proxy's 10 s.
 */
const ESSAY_EVALUATE_TIMEOUT_MS = 130_000;

type Context = { params: Promise<{ path: string[] }> };

async function forward(method: ProxyMethod, request: NextRequest, { params }: Context) {
  const { path } = await params;
  if (path.length === 0 || path.length > MAX_SEGMENTS || !path.every((segment) => SEGMENT.test(segment))) {
    return NextResponse.json({ success: false, error: "Not found." }, { status: 404 });
  }

  const query = new URLSearchParams();
  request.nextUrl.searchParams.forEach((value, key) => {
    if (ALLOWED_PARAMS.has(key)) query.append(key, value);
  });
  const suffix = query.size > 0 ? `?${query.toString()}` : "";

  const body = method === "GET" || method === "DELETE" ? undefined : await request.text();
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  const timeoutMs = path.join("/") === "essays/evaluate" ? ESSAY_EVALUATE_TIMEOUT_MS : undefined;
  return proxyRequest(method, `/api/v1/user/desk/${path.join("/")}${suffix}`, body, cookieHeader, timeoutMs);
}

export const GET = (request: NextRequest, context: Context) => forward("GET", request, context);
export const POST = (request: NextRequest, context: Context) => forward("POST", request, context);
export const PATCH = (request: NextRequest, context: Context) => forward("PATCH", request, context);
export const PUT = (request: NextRequest, context: Context) => forward("PUT", request, context);
export const DELETE = (request: NextRequest, context: Context) => forward("DELETE", request, context);
