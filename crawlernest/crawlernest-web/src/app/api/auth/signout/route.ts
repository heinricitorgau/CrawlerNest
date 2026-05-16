import { type NextRequest } from "next/server";
import { proxyPost } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyPost("/api/v1/auth/signout", "{}", cookieHeader);
}
