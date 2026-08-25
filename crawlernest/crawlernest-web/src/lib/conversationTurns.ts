/**
 * Turns the agent page's run history into the transcript shape the API stores.
 *
 * The page keeps prompt/response pairs; warehouse.saved_conversation keeps
 * role-tagged turns, matching the shape the Python agent's ConversationStore
 * already uses. The conversion lives here rather than in the component so the
 * edge cases below can be tested without rendering a page.
 */

export type ConversationTurn = {
  role: "user" | "assistant";
  content: string;
};

/** The subset of the page's RunEntry that a transcript actually needs. */
export type ConversationSourceEntry = {
  prompt: string;
  error?: string | null;
  response?: {
    data?: {
      data?: {
        explanation?: string;
      };
    };
  } | null;
};

/**
 * Pulls the assistant's reply out of an entry.
 *
 * An entry that failed carries its error rather than an explanation. Keeping
 * that as the assistant turn preserves what the user actually saw; dropping it
 * would leave a question in the transcript with nothing after it, which reads
 * as though the agent never answered rather than as though it failed.
 */
function assistantText(entry: ConversationSourceEntry): string | null {
  const explanation = entry.response?.data?.data?.explanation;
  if (typeof explanation === "string" && explanation.trim()) {
    return explanation.trim();
  }
  if (typeof entry.error === "string" && entry.error.trim()) {
    return entry.error.trim();
  }
  return null;
}

/**
 * Flattens run history into alternating user/assistant turns.
 *
 * A request still in flight contributes only its user turn: there is no reply
 * yet, and inventing an empty one would be stored as though the agent had
 * answered with nothing.
 */
export function buildConversationTurns(
  entries: readonly ConversationSourceEntry[]
): ConversationTurn[] {
  const turns: ConversationTurn[] = [];

  for (const entry of entries) {
    const prompt = typeof entry.prompt === "string" ? entry.prompt.trim() : "";
    if (prompt) {
      turns.push({ role: "user", content: prompt });
    }

    const reply = assistantText(entry);
    if (reply) {
      turns.push({ role: "assistant", content: reply });
    }
  }

  return turns;
}
