import { type NextRequest } from "next/server";
import { proxyPost } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

/** Ends every token issued to the signed-in account, on every device, and clears this browser's cookie. */
export async function POST(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyPost("/api/v1/auth/signout-everywhere", "{}", cookieHeader);
}
