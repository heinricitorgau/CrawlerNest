import { type NextRequest } from "next/server";
import { proxyPost } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

/** Forwards to the Java PasswordResetController. Open, like signin: the caller cannot sign in. */
export async function POST(request: NextRequest) {
  return proxyPost("/api/v1/auth/password-reset/confirm", await request.text());
}
