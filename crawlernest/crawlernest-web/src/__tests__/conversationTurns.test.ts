import {
  buildConversationTurns,
  type ConversationSourceEntry,
} from "@/lib/conversationTurns";

function entry(
  prompt: string,
  explanation?: string,
  error?: string | null
): ConversationSourceEntry {
  return {
    prompt,
    error: error ?? null,
    response: explanation
      ? { data: { data: { explanation } } }
      : null,
  };
}

describe("buildConversationTurns", () => {
  it("flattens prompt/response pairs into alternating turns", () => {
    const turns = buildConversationTurns([
      entry("How is the aggregated rank computed?", "It combines the sources."),
      entry("And which sources are those?", "QS, THE and ARWU."),
    ]);

    expect(turns).toEqual([
      { role: "user", content: "How is the aggregated rank computed?" },
      { role: "assistant", content: "It combines the sources." },
      { role: "user", content: "And which sources are those?" },
      { role: "assistant", content: "QS, THE and ARWU." },
    ]);
  });

  it("keeps the user turn of a request still in flight", () => {
    const turns = buildConversationTurns([
      entry("Answered question", "The answer."),
      entry("Still waiting"),
    ]);

    // No fabricated assistant turn: an empty one would be stored as though the
    // agent had answered with nothing.
    expect(turns).toEqual([
      { role: "user", content: "Answered question" },
      { role: "assistant", content: "The answer." },
      { role: "user", content: "Still waiting" },
    ]);
  });

  it("records a failure as the assistant turn the user actually saw", () => {
    const turns = buildConversationTurns([
      entry("Something that failed", undefined, "Agent provider unavailable."),
    ]);

    // Dropping this would leave a question with nothing after it, reading as
    // though the agent never replied rather than as though it failed.
    expect(turns).toEqual([
      { role: "user", content: "Something that failed" },
      { role: "assistant", content: "Agent provider unavailable." },
    ]);
  });

  it("prefers the explanation over the error when both are present", () => {
    const turns = buildConversationTurns([
      entry("Partial failure", "Here is a partial answer.", "some warning"),
    ]);

    expect(turns).toEqual([
      { role: "user", content: "Partial failure" },
      { role: "assistant", content: "Here is a partial answer." },
    ]);
  });

  it("trims surrounding whitespace on both roles", () => {
    const turns = buildConversationTurns([
      entry("  padded question  ", "  padded answer  "),
    ]);

    expect(turns).toEqual([
      { role: "user", content: "padded question" },
      { role: "assistant", content: "padded answer" },
    ]);
  });

  it("skips an entry whose prompt is only whitespace", () => {
    const turns = buildConversationTurns([entry("   ", "an answer")]);

    // The API rejects a turn with empty content, so a blank prompt must not
    // reach it and fail the whole save.
    expect(turns).toEqual([{ role: "assistant", content: "an answer" }]);
  });

  it("ignores a whitespace-only explanation", () => {
    const turns = buildConversationTurns([entry("a question", "   ")]);

    expect(turns).toEqual([{ role: "user", content: "a question" }]);
  });

  it("returns nothing for an empty history", () => {
    expect(buildConversationTurns([])).toEqual([]);
  });

  it("survives a response missing the nested explanation path", () => {
    const turns = buildConversationTurns([
      { prompt: "a question", error: null, response: { data: {} } },
    ]);

    expect(turns).toEqual([{ role: "user", content: "a question" }]);
  });
});
