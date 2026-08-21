import { type NextRequest } from "next/server";

import { proxyGet } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  const query = (request.nextUrl.searchParams.get("q") ?? "").slice(0, 120);
  return proxyGet(
    `/api/v1/admin/mapping-reviews/canonical-search?q=${encodeURIComponent(query)}&limit=20`,
    cookieHeader
  );
}
