import {
  deleteConversation,
  getConversationById,
  getConversations,
  normalizeTurns,
  saveConversation,
} from "@/lib/conversationsApi";

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

function mockFetch(response: Response | Error) {
  // Typed against `typeof fetch` so mock.calls carries the real argument tuple:
  // an untyped jest.fn() infers an empty tuple and reading calls[0][1] fails.
  const fn = jest.fn() as jest.MockedFunction<typeof fetch>;
  fn.mockImplementation(async () => {
    if (response instanceof Error) {
      throw response;
    }
    return response;
  });
  global.fetch = fn;
  return fn;
}

const SUMMARY_ROW = {
  id: 7,
  sessionId: "session-abc",
  title: "How rankings work",
  turnCount: 4,
  preview: "How is the aggregated rank computed?",
  createdAt: "2026-08-25T01:00:00Z",
  updatedAt: "2026-08-25T02:00:00Z",
};

describe("getConversations", () => {
  it("returns the caller's saved conversations", async () => {
    const fetchMock = mockFetch(jsonResponse(200, { data: [SUMMARY_ROW] }));

    const result = await getConversations();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/user/conversations",
      expect.objectContaining({ credentials: "include", cache: "no-store" })
    );
    expect(result).toEqual({ ok: true, data: [SUMMARY_ROW] });
  });

  it("reports an expired session distinctly from an outage", async () => {
    mockFetch(jsonResponse(401, { error: "Authentication required." }));

    const result = await getConversations();

    // The UI prompts a sign-in for one and offers a retry for the other, so
    // collapsing them into a single "failed" would give the wrong affordance.
    expect(result).toEqual(
      expect.objectContaining({ ok: false, reason: "unauthenticated" })
    );
  });

  it("reports an outage as unavailable", async () => {
    mockFetch(jsonResponse(503, { error: "Authentication service unavailable." }));

    const result = await getConversations();

    expect(result).toEqual(expect.objectContaining({ ok: false, reason: "unavailable" }));
  });

  it("treats a dead network as unavailable rather than throwing", async () => {
    mockFetch(new Error("ECONNREFUSED"));

    const result = await getConversations();

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toBe("unavailable");
      expect(result.message).not.toContain("ECONNREFUSED");
    }
  });

  it("survives a success body with no data array", async () => {
    mockFetch(jsonResponse(200, { success: true }));

    await expect(getConversations()).resolves.toEqual({ ok: true, data: [] });
  });

  it("drops rows with no usable id instead of rendering blanks", async () => {
    mockFetch(jsonResponse(200, { data: [SUMMARY_ROW, { title: "no id" }, null] }));

    const result = await getConversations();

    expect(result).toEqual({ ok: true, data: [SUMMARY_ROW] });
  });
});

describe("getConversationById", () => {
  it("returns the transcript", async () => {
    mockFetch(
      jsonResponse(200, {
        data: {
          id: 7,
          sessionId: "session-abc",
          title: "How rankings work",
          turnsJson: [
            { role: "user", content: "A question" },
            { role: "assistant", content: "An answer" },
          ],
          createdAt: "2026-08-25T01:00:00Z",
          updatedAt: "2026-08-25T02:00:00Z",
        },
      })
    );

    const result = await getConversationById(7);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.sessionId).toBe("session-abc");
      expect(result.data.turns).toEqual([
        { role: "user", content: "A question" },
        { role: "assistant", content: "An answer" },
      ]);
    }
  });

  it("encodes the id into the path", async () => {
    const fetchMock = mockFetch(jsonResponse(404, { error: "Not found." }));

    await getConversationById(42);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/user/conversations/42",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("reports another user's row as not_found", async () => {
    mockFetch(jsonResponse(404, { error: "Not found." }));

    const result = await getConversationById(42);

    // The API answers 404 rather than 403 for someone else's row; the client
    // keeps that shape so the panel can drop the stale entry and refetch.
    expect(result).toEqual(expect.objectContaining({ ok: false, reason: "not_found" }));
  });

  it("rejects a success body that is missing the row", async () => {
    mockFetch(jsonResponse(200, { data: null }));

    const result = await getConversationById(7);

    expect(result).toEqual(expect.objectContaining({ ok: false, reason: "unavailable" }));
  });
});

describe("normalizeTurns", () => {
  it("keeps well-formed turns", () => {
    expect(
      normalizeTurns([
        { role: "user", content: "Q" },
        { role: "assistant", content: "A" },
      ])
    ).toEqual([
      { role: "user", content: "Q" },
      { role: "assistant", content: "A" },
    ]);
  });

  it("drops entries with no string content", () => {
    // turns_json is a JSONB column, so a malformed row would otherwise put
    // undefined into React state and render an empty bubble.
    expect(
      normalizeTurns([
        { role: "user", content: 42 },
        null,
        "a bare string",
        { role: "user", content: "kept" },
      ])
    ).toEqual([{ role: "user", content: "kept" }]);
  });

  it("treats any non-assistant role as a user turn", () => {
    expect(normalizeTurns([{ role: "system", content: "?" }])).toEqual([
      { role: "user", content: "?" },
    ]);
  });

  it("returns nothing when the column is not an array", () => {
    expect(normalizeTurns("not an array")).toEqual([]);
    expect(normalizeTurns(null)).toEqual([]);
  });
});

describe("deleteConversation", () => {
  it("issues a DELETE with credentials", async () => {
    const fetchMock = mockFetch(jsonResponse(200, { data: { deleted: true } }));

    const result = await deleteConversation(7);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/user/conversations/7",
      expect.objectContaining({ method: "DELETE", credentials: "include" })
    );
    expect(result).toEqual({ ok: true, data: null });
  });

  it("reports an already-deleted row as not_found", async () => {
    mockFetch(jsonResponse(404, { error: "Not found." }));

    await expect(deleteConversation(7)).resolves.toEqual(
      expect.objectContaining({ ok: false, reason: "not_found" })
    );
  });
});

describe("saveConversation", () => {
  it("posts the session id and turns without a title", async () => {
    const fetchMock = mockFetch(jsonResponse(201, { data: { id: 9 } }));

    const result = await saveConversation("session-abc", [
      { role: "user", content: "A question" },
    ]);

    const body = JSON.parse(String(fetchMock.mock.calls[0][1]?.body));
    expect(body).toEqual({
      sessionId: "session-abc",
      turns: [{ role: "user", content: "A question" }],
    });
    // Omitted on purpose: the API derives one from the opening question.
    expect(body.title).toBeUndefined();
    expect(result).toEqual({ ok: true, data: { id: 9 } });
  });

  it("passes the server's own message through for a rejected transcript", async () => {
    mockFetch(
      jsonResponse(400, { error: "Conversation is too long. Limit is 200 turns." })
    );

    const result = await saveConversation("session-abc", []);

    expect(result).toEqual({
      ok: false,
      reason: "rejected",
      // A generic "could not save" would hide the one detail that tells the
      // user what to do about it.
      message: "Conversation is too long. Limit is 200 turns.",
    });
  });
});
