/**
 * @jest-environment node
 *
 * The chat route's two passes, end to end from the request to the payload the
 * banner reads. The model provider is left on its default "mock" setting, so
 * pass two contacts nothing; only the engine call is stubbed.
 */
import { NextRequest } from "next/server";

import { POST } from "@/app/api/agent/chat/route";
import { UNSUPPORTED_YEAR_WARNING_CODE, selectDisclosureWarnings } from "@/lib/agentWarnings";

/** Verbatim from crawlernest/agent/web_agent/policy/unsupported_year.py. */
const UNSUPPORTED_YEAR_WARNING =
  "UnsupportedYearWarning: Dataset is strictly locked to the 2026 snapshot. Year 2025 " +
  "is not available. This is not missing or incomplete data: the warehouse holds a " +
  "single-year 2026 snapshot and no rows for any other year, so any result shown here " +
  "describes 2026 rather than 2025.";

const originalFetch = global.fetch;

function engineReturns(warnings: string[]) {
  return jest.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      success: true,
      data: {
        taskId: "t-1",
        status: "success",
        message: "Rankings query completed.",
        data: { type: "query", items: [] },
        traces: [],
        warnings,
      },
    }),
  })) as unknown as typeof fetch;
}

function chatRequest(body: unknown): NextRequest {
  return new NextRequest("http://localhost:3000/api/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

afterEach(() => {
  global.fetch = originalFetch;
  jest.restoreAllMocks();
});

describe("POST /api/agent/chat", () => {
  it("carries the engine's year disclosure into the payload the banner reads", async () => {
    global.fetch = engineReturns([UNSUPPORTED_YEAR_WARNING]);

    const response = await POST(chatRequest({ message: "QS 2025 排名" }));
    const body = await response.json();

    expect(body.data.warnings).toContain(UNSUPPORTED_YEAR_WARNING);
    // The banner's own selector, run over the real payload: this is the step
    // that decides whether the alert renders.
    const disclosures = selectDisclosureWarnings(body.data.warnings);
    expect(disclosures).toHaveLength(1);
    expect(disclosures[0].code).toBe(UNSUPPORTED_YEAR_WARNING_CODE);
    expect(disclosures[0].message).toContain("describes 2026 rather than 2025");
  });

  it("puts the disclosure ahead of the provider's own notes", async () => {
    global.fetch = engineReturns([UNSUPPORTED_YEAR_WARNING]);

    const response = await POST(chatRequest({ message: "QS 2025 rankings" }));
    const body = await response.json();

    expect(body.data.warnings[0]).toBe(UNSUPPORTED_YEAR_WARNING);
    // The mock provider's note is still there; it is just not first, and the
    // banner will not show it.
    expect(body.data.warnings.length).toBeGreaterThan(1);
    expect(selectDisclosureWarnings(body.data.warnings)).toHaveLength(1);
  });

  it("records that the engine was consulted", async () => {
    global.fetch = engineReturns([]);

    const response = await POST(chatRequest({ message: "top universities" }));
    const body = await response.json();

    expect(body.data.data.meta.engineConsulted).toBe(true);
    expect(body.data.data.meta.engineSkipped).toBeUndefined();
    // The engine pass calls ranking_tools, so the readonly disclosure block
    // has to stop saying no tools ran. It stays readonly and write-free.
    expect(body.data.data.meta.toolsExecuted).toBe(true);
    expect(body.data.data.meta.readonly).toBe(true);
    expect(body.data.data.meta.dbWrites).toBe(false);
  });

  it("forwards a caller-supplied year context to the engine", async () => {
    const fetchImpl = engineReturns([UNSUPPORTED_YEAR_WARNING]);
    global.fetch = fetchImpl;

    await POST(chatRequest({ message: "list rankings", context: { year: 2025 } }));

    const [, init] = (fetchImpl as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body)).context).toEqual({ year: 2025 });
  });

  it("answers normally when the engine is unreachable", async () => {
    // The whole degradation contract in one assertion: the reply still comes
    // back, only without the disclosure.
    global.fetch = jest.fn(async () => {
      throw new Error("ECONNREFUSED");
    }) as unknown as typeof fetch;

    const response = await POST(chatRequest({ message: "QS 2025 rankings" }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.data.data.explanation).toBeTruthy();
    expect(selectDisclosureWarnings(body.data.warnings)).toEqual([]);
    expect(body.data.data.meta.engineSkipped).toBe("agent engine unavailable");
  });

  it("does not call the engine for small talk", async () => {
    const fetchImpl = engineReturns([]);
    global.fetch = fetchImpl;

    const response = await POST(chatRequest({ message: "hello" }));
    const body = await response.json();

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(body.data.data.explanation).toBeTruthy();
    expect(body.data.data.meta.engineConsulted).toBe(false);
    expect(body.data.data.meta.toolsExecuted).toBe(false);
  });

  it("still rejects an invalid message before either pass runs", async () => {
    const fetchImpl = engineReturns([]);
    global.fetch = fetchImpl;

    const response = await POST(chatRequest({ message: "" }));

    expect(response.status).toBe(400);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
