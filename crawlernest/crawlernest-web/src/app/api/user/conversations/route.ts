import { type NextRequest } from "next/server";
import { proxyGet, proxyPost } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyGet("/api/v1/user/conversations", cookieHeader);
}

export async function POST(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  const body = await request.text();
  return proxyPost("/api/v1/user/conversations", body, cookieHeader);
}
