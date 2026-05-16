import { type NextRequest } from "next/server";
import { proxyPost, proxyDelete } from "@/lib/authProxy";

export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ canonicalUniversityId: string }> }
) {
  const { canonicalUniversityId } = await params;
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyPost(
    `/api/v1/user/saved-universities/${encodeURIComponent(canonicalUniversityId)}`,
    "{}",
    cookieHeader
  );
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ canonicalUniversityId: string }> }
) {
  const { canonicalUniversityId } = await params;
  const cookieHeader = request.headers.get("cookie") ?? undefined;
  return proxyDelete(
    `/api/v1/user/saved-universities/${encodeURIComponent(canonicalUniversityId)}`,
    cookieHeader
  );
}
