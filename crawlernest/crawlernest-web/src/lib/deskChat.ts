/**
 * The desk's chat goes through the same `/api/agent/chat` route as /agent, so it
 * gets the same engine pass and the same disclosures. This file only reduces
 * that route's envelope to what a chat bubble needs.
 */

export interface DeskChatReply {
  ok: boolean;
  text: string;
  /** `response.data.warnings`, untouched. AgentWarningBanner does the filtering. */
  warnings: unknown;
}

interface AgentChatEnvelope {
  success?: boolean;
  error?: string;
  data?: {
    message?: string;
    data?: { explanation?: string };
    warnings?: unknown;
  };
}

export const DESK_CHAT_UNREACHABLE = "Could not reach the agent. Check that the web server and the agent API are running.";

export async function sendDeskPrompt(
  message: string,
  sessionId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<DeskChatReply> {
  let res: Response;
  let json: AgentChatEnvelope;
  try {
    res = await fetchImpl("/api/agent/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    json = (await res.json()) as AgentChatEnvelope;
  } catch {
    return { ok: false, text: DESK_CHAT_UNREACHABLE, warnings: [] };
  }

  const ok = res.ok && json.success === true;
  const text =
    json.data?.data?.explanation ??
    (ok ? undefined : json.error ?? json.data?.message) ??
    (ok ? "" : "Agent request failed.");
  return { ok, text, warnings: json.data?.warnings ?? [] };
}
