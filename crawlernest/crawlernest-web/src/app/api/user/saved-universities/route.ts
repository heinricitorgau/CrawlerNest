import { type NextRequest } from "next/server";
import { proxyGet } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyGet("/api/v1/user/saved-universities", cookieHeader);
}
