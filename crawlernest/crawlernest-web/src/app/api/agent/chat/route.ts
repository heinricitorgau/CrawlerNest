import { NextRequest, NextResponse } from "next/server";

import {
  generateAgentChatResponse,
  validateAgentMessage,
} from "@/lib/agentModelProvider";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const NO_STORE_HEADERS = {
  "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
  Pragma: "no-cache",
  Expires: "0",
};

export async function POST(request: NextRequest) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return safeJson(
      {
        success: false,
        error: "Invalid JSON body.",
      },
      400
    );
  }

  const message =
    payload && typeof payload === "object"
      ? (payload as Record<string, unknown>).message
      : undefined;
  const validationError = validateAgentMessage(message);
  if (validationError) {
    return safeJson(
      {
        success: false,
        error: validationError,
      },
      400
    );
  }

  const result = await generateAgentChatResponse(String(message));
  const paragraphs = result.text
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);

  return safeJson(
    {
      success: result.ok,
      error: result.ok ? undefined : result.text,
      data: {
        taskId: crypto.randomUUID(),
        status: result.ok ? "success" : "error",
        message: result.ok ? "Agent advisory response" : "Agent provider unavailable",
        data: {
          type: "agent_chat",
          title: result.ok ? "Agent Advisory Response" : "Agent Provider Unavailable",
          explanation: result.text,
          explanationParagraphs: paragraphs.length > 0 ? paragraphs : [result.text],
          items: [
            {
              label: "/analytics",
              kind: "page",
              description: "Review trends and source disagreement.",
            },
            {
              label: "/rankings",
              kind: "page",
              description: "Inspect global ranking records.",
            },
            {
              label: "/recommendations",
              kind: "page",
              description: "Explore deterministic recommendation output.",
            },
            {
              label: "/system-status",
              kind: "page",
              description: "Check operational readiness and diagnostics.",
            },
          ],
          meta: {
            providerLabel: result.providerLabel,
            modelName: result.modelName,
            baseUrl: result.baseUrl,
            readonly: true,
            toolsExecuted: false,
            shellExecuted: false,
            dbWrites: false,
            pipelineRuns: false,
            route: "/api/agent/chat",
          },
        },
        traces: [],
        warnings: result.warnings,
      },
    },
    result.ok ? 200 : 503
  );
}

function safeJson(payload: unknown, status: number) {
  return NextResponse.json(payload, {
    status,
    headers: NO_STORE_HEADERS,
  });
}
