import { normalizeAuthError } from "@/lib/authMessages";
import type { ConversationTurn } from "@/lib/conversationTurns";

/**
 * Client for the Java ConversationController (`/api/v1/user/conversations`,
 * reached through the Next proxy at `/api/user/conversations`).
 *
 * These calls return a result object rather than throwing. Every caller has to
 * tell an expired session apart from a server that is down — one prompts a
 * sign-in, the other is a retry — and a thrown Error flattens that distinction
 * into a string the UI would have to re-parse.
 */

export type ConversationSummary = {
  id: number;
  sessionId: string;
  title: string;
  turnCount: number;
  /** First user message, truncated server-side; null when there is no user turn. */
  preview: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ConversationDetail = {
  id: number;
  sessionId: string;
  title: string;
  turns: ConversationTurn[];
  createdAt: string;
  updatedAt: string;
};

export type ConversationApiFailure = {
  ok: false;
  /**
   * `unauthenticated` means sign in again; `not_found` means the row is gone or
   * belongs to someone else (the API answers 404 for both on purpose);
   * `rejected` is a body the server refused and can be fixed by sending less;
   * `unavailable` covers a down backend and a dead network alike.
   */
  reason: "unauthenticated" | "not_found" | "rejected" | "unavailable";
  message: string;
};

export type ConversationApiResult<T> = { ok: true; data: T } | ConversationApiFailure;

const LIST_PATH = "/api/user/conversations";

function itemPath(id: number): string {
  return `${LIST_PATH}/${encodeURIComponent(String(id))}`;
}

function failureFor(status: number, payload: unknown): ConversationApiFailure {
  const message = normalizeAuthError(status, payload);
  if (status === 401) {
    return { ok: false, reason: "unauthenticated", message };
  }
  if (status === 404) {
    return { ok: false, reason: "not_found", message };
  }
  if (status === 400) {
    return { ok: false, reason: "rejected", message };
  }
  return { ok: false, reason: "unavailable", message };
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    // A proxy error page or an empty body: not fatal, the status still carries
    // enough to classify the failure.
    return null;
  }
}

/**
 * Keeps only turns the chat window can actually render.
 *
 * turns_json is a JSONB column, so what comes back is whatever was stored, and
 * a malformed row would otherwise put `undefined` into React state and render
 * as an empty bubble. Filtering here means the restore path can assume every
 * turn has a role and a string body.
 */
export function normalizeTurns(raw: unknown): ConversationTurn[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const turns: ConversationTurn[] = [];
  for (const candidate of raw) {
    if (!candidate || typeof candidate !== "object") {
      continue;
    }
    const { role, content } = candidate as { role?: unknown; content?: unknown };
    if (typeof content !== "string") {
      continue;
    }
    turns.push({
      role: role === "assistant" ? "assistant" : "user",
      content,
    });
  }
  return turns;
}

function toSummary(raw: unknown): ConversationSummary | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const row = raw as Record<string, unknown>;
  if (typeof row.id !== "number") {
    return null;
  }
  return {
    id: row.id,
    sessionId: typeof row.sessionId === "string" ? row.sessionId : "",
    title: typeof row.title === "string" ? row.title : "Untitled conversation",
    turnCount: typeof row.turnCount === "number" ? row.turnCount : 0,
    preview: typeof row.preview === "string" ? row.preview : null,
    createdAt: typeof row.createdAt === "string" ? row.createdAt : "",
    updatedAt: typeof row.updatedAt === "string" ? row.updatedAt : "",
  };
}

/** Every saved conversation for the signed-in user, newest activity first. */
export async function getConversations(): Promise<ConversationApiResult<ConversationSummary[]>> {
  let response: Response;
  try {
    response = await fetch(LIST_PATH, { credentials: "include", cache: "no-store" });
  } catch {
    return { ok: false, reason: "unavailable", message: "Could not connect. Please check your connection." };
  }

  const payload = await readJson(response);
  if (!response.ok) {
    return failureFor(response.status, payload);
  }

  const rows = (payload as { data?: unknown })?.data;
  const items = Array.isArray(rows)
    ? rows.map(toSummary).filter((row): row is ConversationSummary => row !== null)
    : [];
  return { ok: true, data: items };
}

/** One saved conversation with its full transcript. */
export async function getConversationById(
  id: number
): Promise<ConversationApiResult<ConversationDetail>> {
  let response: Response;
  try {
    response = await fetch(itemPath(id), { credentials: "include", cache: "no-store" });
  } catch {
    return { ok: false, reason: "unavailable", message: "Could not connect. Please check your connection." };
  }

  const payload = await readJson(response);
  if (!response.ok) {
    return failureFor(response.status, payload);
  }

  const row = (payload as { data?: Record<string, unknown> })?.data;
  if (!row || typeof row !== "object" || typeof row.id !== "number") {
    return { ok: false, reason: "unavailable", message: "Could not load your data. Please try again." };
  }

  return {
    ok: true,
    data: {
      id: row.id,
      sessionId: typeof row.sessionId === "string" ? row.sessionId : "",
      title: typeof row.title === "string" ? row.title : "Untitled conversation",
      turns: normalizeTurns(row.turnsJson),
      createdAt: typeof row.createdAt === "string" ? row.createdAt : "",
      updatedAt: typeof row.updatedAt === "string" ? row.updatedAt : "",
    },
  };
}

/** Removes one saved conversation. A row owned by someone else answers not_found. */
export async function deleteConversation(id: number): Promise<ConversationApiResult<null>> {
  let response: Response;
  try {
    response = await fetch(itemPath(id), { method: "DELETE", credentials: "include" });
  } catch {
    return { ok: false, reason: "unavailable", message: "Could not connect. Please check your connection." };
  }

  if (!response.ok) {
    return failureFor(response.status, await readJson(response));
  }
  return { ok: true, data: null };
}

/**
 * Stores a transcript against a session id, replacing what that session last
 * saved. The title is omitted deliberately: the API derives one from the
 * opening question so saving never has to stop and ask for a name.
 */
export async function saveConversation(
  sessionId: string,
  turns: ConversationTurn[]
): Promise<ConversationApiResult<{ id: number }>> {
  let response: Response;
  try {
    response = await fetch(LIST_PATH, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId, turns }),
    });
  } catch {
    return { ok: false, reason: "unavailable", message: "Could not connect. Please check your connection." };
  }

  const payload = await readJson(response);
  if (!response.ok) {
    return failureFor(response.status, payload);
  }

  const id = (payload as { data?: { id?: unknown } })?.data?.id;
  return { ok: true, data: { id: typeof id === "number" ? id : -1 } };
}
