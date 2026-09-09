import { NextRequest, NextResponse } from "next/server";

import {
  generateAgentChatResponse,
  validateAgentMessage,
} from "@/lib/agentModelProvider";
import { runEngineTask } from "@/lib/agentEngineTask";
import { getAgentApiBaseUrl } from "@/lib/api";

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

  // Two passes over the same message. The engine pass reads the warehouse and
  // attaches the response-level disclosures this route had no way of knowing
  // about -- which year the answer actually describes, above all. The model
  // pass writes the prose, as it always did.
  //
  // They run together rather than in sequence: the model is not handed the
  // engine's rows (its prompt is advisory and un-grounded by design), so
  // awaiting the engine first would only add its latency to every data
  // question. The engine pass never throws and never blocks -- a skipped or
  // failed one leaves the reply exactly as it was.
  const rawContext = (payload as Record<string, unknown>).context;
  const [engine, result] = await Promise.all([
    runEngineTask(String(message), {
      baseUrl: getAgentApiBaseUrl(),
      context:
        rawContext && typeof rawContext === "object" && !Array.isArray(rawContext)
          ? (rawContext as Record<string, unknown>)
          : undefined,
    }),
    generateAgentChatResponse(String(message)),
  ]);

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
            // True the moment the engine pass runs: it calls ranking_tools,
            // which reads the warehouse. Still readonly, still no writes -- but
            // "no tools were executed" stopped being true when this route
            // gained a first pass, and leaving it hardcoded would have made the
            // disclosure block itself carry a false one.
            toolsExecuted: engine.consulted,
            shellExecuted: false,
            dbWrites: false,
            pipelineRuns: false,
            route: "/api/agent/chat",
            engineConsulted: engine.consulted,
            ...(engine.skippedReason ? { engineSkipped: engine.skippedReason } : {}),
          },
        },
        traces: [],
        // Engine disclosures first: they qualify the answer, where the
        // provider's notes describe how it was produced. AgentWarningBanner
        // renders the coded ones and drops the rest.
        warnings: [...engine.warnings, ...result.warnings],
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
