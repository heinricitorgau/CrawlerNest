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

/** A restored history entry, matching the agent page's RunEntry shape. */
export type RestoredEntry = {
  id: string;
  prompt: string;
  restoredReply: string | null;
};

/**
 * The inverse of {@link buildConversationTurns}: pairs a flat transcript back
 * into the prompt/response entries the chat window renders.
 *
 * Assistant turns attach to the user turn before them. A transcript that opens
 * with an assistant turn -- possible, since a failed first exchange stores its
 * error -- would otherwise have nowhere to put it, so it becomes an entry with
 * an empty prompt rather than being dropped.
 *
 * Ids are generated here rather than restored: the originals belonged to a
 * previous run of the page and nothing persists them.
 */
export function runEntriesFromTurns(
  turns: readonly ConversationTurn[],
  makeId: () => string
): RestoredEntry[] {
  const entries: RestoredEntry[] = [];

  for (const turn of turns) {
    const content = typeof turn.content === "string" ? turn.content.trim() : "";
    if (!content) {
      continue;
    }

    if (turn.role === "user") {
      entries.push({ id: makeId(), prompt: content, restoredReply: null });
      continue;
    }

    const last = entries[entries.length - 1];
    if (last && last.restoredReply === null) {
      last.restoredReply = content;
    } else {
      // Two assistant turns in a row, or one with no question before it.
      entries.push({ id: makeId(), prompt: "", restoredReply: content });
    }
  }

  return entries;
}
