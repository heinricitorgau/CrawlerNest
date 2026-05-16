import { type NextRequest } from "next/server";
import { proxyGet, proxyDelete } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyGet(
    `/api/v1/user/saved-recommendations/${encodeURIComponent(id)}`,
    cookieHeader
  );
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyDelete(
    `/api/v1/user/saved-recommendations/${encodeURIComponent(id)}`,
    cookieHeader
  );
}
