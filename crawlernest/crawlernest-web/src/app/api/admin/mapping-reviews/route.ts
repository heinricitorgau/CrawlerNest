import { type NextRequest } from "next/server";

import { proxyGet, proxyPost } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

const ALLOWED_STATUS = new Set(["pending", "decided"]);

function buildQuery(request: NextRequest): string {
  const requested = request.nextUrl.searchParams.get("status") ?? "pending";
  const status = ALLOWED_STATUS.has(requested) ? requested : "pending";

  const rawLimit = Number.parseInt(request.nextUrl.searchParams.get("limit") ?? "", 10);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.min(rawLimit, 200) : 50;

  return `?status=${status}&limit=${limit}`;
}

export async function GET(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyGet(`/api/v1/admin/mapping-reviews${buildQuery(request)}`, cookieHeader);
}

export async function POST(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  // Forwarded as-is: the backend re-reads what was actually matched from the
  // mapping row, so nothing here is trusted for the stored evidence.
  const body = await request.text();
  return proxyPost("/api/v1/admin/mapping-reviews", body, cookieHeader);
}
