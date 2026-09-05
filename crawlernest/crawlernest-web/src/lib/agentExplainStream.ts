/**
 * Reader for the agent explain route's `text/event-stream` transport.
 *
 * Kept out of the component so the framing can be tested without React. Frame
 * boundaries are the part that breaks quietly: a chunk from the network is not
 * a frame, and a naive reader that treats each `read()` as one message drops
 * text whenever a frame straddles two chunks. That failure is invisible in a
 * test that feeds the whole body at once, so the tests here deliberately split
 * mid-frame and mid-word.
 *
 * What arrives as a delta is already-verified text -- see the docstring on
 * `_write_explain_stream` in the agent API. Deltas are only sent for
 * model-written answers, so receiving one is itself the signal that the answer
 * is `source === "llm"`; a deterministic fallback streams its terminal frame
 * and no deltas, and the page renders nothing, exactly as it does over JSON.
 */

export type ExplainStatusFrame = { type: "status"; phase: string };

export type ExplainDeltaFrame = { type: "delta"; text: string };

export type ExplainDoneFrame = {
  type: "done";
  success?: boolean;
  taskKind?: string | null;
  source?: string | null;
  modelName?: string | null;
  warning?: string | null;
  paragraphs?: string[];
  explanation?: string | null;
};

export type ExplainFrame =
  | ExplainStatusFrame
  | ExplainDeltaFrame
  | ExplainDoneFrame;

const DONE_SENTINEL = "[DONE]";

/**
 * Yield each parsed frame from an SSE body.
 *
 * Malformed frames are skipped rather than thrown: one unreadable frame is a
 * lost fragment, but aborting the read would discard the terminal frame too,
 * and with it the source and warning the page needs to decide what to show.
 */
export async function* readExplainStream(
  body: ReadableStream<Uint8Array>
): AsyncGenerator<ExplainFrame> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      // `stream: true` keeps a multi-byte character split across two chunks
      // from being decoded as two replacement characters.
      buffer += decoder.decode(value, { stream: true });

      let newlineAt: number;
      while ((newlineAt = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, newlineAt);
        buffer = buffer.slice(newlineAt + 1);
        const frame = parseFrameLine(line);
        if (frame) {
          yield frame;
        }
      }
    }

    // A body that ended without a trailing newline still has one frame left.
    const trailing = parseFrameLine(buffer + decoder.decode());
    if (trailing) {
      yield trailing;
    }
  } finally {
    reader.releaseLock();
  }
}

function parseFrameLine(line: string): ExplainFrame | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data:")) {
    return null; // blank separator, comment, or a keep-alive
  }
  const body = trimmed.slice("data:".length).trim();
  if (!body || body === DONE_SENTINEL) {
    return null;
  }
  try {
    const parsed = JSON.parse(body);
    if (parsed && typeof parsed === "object" && typeof parsed.type === "string") {
      return parsed as ExplainFrame;
    }
    return null;
  } catch {
    return null;
  }
}

/** Split accumulated text the way the server splits its `paragraphs`. */
export function splitParagraphs(text: string): string[] {
  return text
    .split("\n\n")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}
