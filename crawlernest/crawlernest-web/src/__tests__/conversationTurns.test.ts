import {
  buildConversationTurns,
  runEntriesFromTurns,
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

describe("runEntriesFromTurns", () => {
  let counter = 0;
  const makeId = () => `id-${++counter}`;

  beforeEach(() => {
    counter = 0;
  });

  it("pairs each assistant turn onto the question before it", () => {
    const entries = runEntriesFromTurns(
      [
        { role: "user", content: "First question" },
        { role: "assistant", content: "First answer" },
        { role: "user", content: "Second question" },
        { role: "assistant", content: "Second answer" },
      ],
      makeId
    );

    expect(entries).toEqual([
      { id: "id-1", prompt: "First question", restoredReply: "First answer" },
      { id: "id-2", prompt: "Second question", restoredReply: "Second answer" },
    ]);
  });

  it("round-trips a transcript built by buildConversationTurns", () => {
    const original = [
      { prompt: "Q1", error: null, response: { data: { data: { explanation: "A1" } } } },
      { prompt: "Q2", error: null, response: { data: { data: { explanation: "A2" } } } },
    ];

    const restored = runEntriesFromTurns(buildConversationTurns(original), makeId);

    expect(restored.map((e) => [e.prompt, e.restoredReply])).toEqual([
      ["Q1", "A1"],
      ["Q2", "A2"],
    ]);
  });

  it("leaves a question with no answer unpaired", () => {
    const entries = runEntriesFromTurns(
      [
        { role: "user", content: "Answered" },
        { role: "assistant", content: "Answer" },
        { role: "user", content: "Never answered" },
      ],
      makeId
    );

    // The caller renders this as "no reply was stored" rather than as a pending
    // request, which would spin forever.
    expect(entries[1]).toEqual({
      id: "id-2",
      prompt: "Never answered",
      restoredReply: null,
    });
  });

  it("keeps an assistant turn that opens the transcript", () => {
    const entries = runEntriesFromTurns(
      [{ role: "assistant", content: "Orphaned reply" }],
      makeId
    );

    // Reachable: a first exchange that failed stores its error as the assistant
    // turn, and the user turn can be missing if the prompt was blank.
    expect(entries).toEqual([
      { id: "id-1", prompt: "", restoredReply: "Orphaned reply" },
    ]);
  });

  it("does not let a second assistant turn overwrite the first", () => {
    const entries = runEntriesFromTurns(
      [
        { role: "user", content: "A question" },
        { role: "assistant", content: "First reply" },
        { role: "assistant", content: "Second reply" },
      ],
      makeId
    );

    expect(entries).toEqual([
      { id: "id-1", prompt: "A question", restoredReply: "First reply" },
      { id: "id-2", prompt: "", restoredReply: "Second reply" },
    ]);
  });

  it("drops turns whose content is only whitespace", () => {
    const entries = runEntriesFromTurns(
      [
        { role: "user", content: "   " },
        { role: "user", content: "Real question" },
        { role: "assistant", content: "  Real answer  " },
      ],
      makeId
    );

    expect(entries).toEqual([
      { id: "id-1", prompt: "Real question", restoredReply: "Real answer" },
    ]);
  });

  it("gives every entry a distinct id", () => {
    const entries = runEntriesFromTurns(
      [
        { role: "user", content: "One" },
        { role: "user", content: "Two" },
        { role: "user", content: "Three" },
      ],
      makeId
    );

    // React keys off these; a repeat would make the list render wrong.
    expect(new Set(entries.map((e) => e.id)).size).toBe(3);
  });

  it("returns nothing for an empty transcript", () => {
    expect(runEntriesFromTurns([], makeId)).toEqual([]);
  });
});
