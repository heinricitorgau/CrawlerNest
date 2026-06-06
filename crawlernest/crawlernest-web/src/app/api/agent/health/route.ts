import { NextResponse } from "next/server";

import { getAgentProviderStatus } from "@/lib/agentModelProvider";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
  Pragma: "no-cache",
  Expires: "0",
};

export async function GET() {
  const status = getAgentProviderStatus();
  return NextResponse.json(
    {
      success: true,
      status: "ok",
      generation: {
        configured: status.configured,
        providerLabel: status.providerLabel,
        modelName: status.modelName,
        baseUrl: status.baseUrl,
        reason: status.reason,
      },
    },
    {
      status: 200,
      headers: NO_STORE_HEADERS,
    }
  );
}
