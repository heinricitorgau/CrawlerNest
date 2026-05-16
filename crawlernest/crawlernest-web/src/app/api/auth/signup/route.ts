import { type NextRequest } from "next/server";
import { proxyPost } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyPost("/api/v1/auth/signup", body);
}
