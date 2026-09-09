/**
 * @jest-environment node
 */
import { runEngineTask, shouldConsultEngine } from "@/lib/agentEngineTask";

/** Verbatim from crawlernest/agent/web_agent/policy/unsupported_year.py. */
const UNSUPPORTED_YEAR_WARNING =
  "UnsupportedYearWarning: Dataset is strictly locked to the 2026 snapshot. Year 2025 " +
  "is not available. This is not missing or incomplete data: the warehouse holds a " +
  "single-year 2026 snapshot and no rows for any other year, so any result shown here " +
  "describes 2026 rather than 2025.";

function engineResponse(
  body: unknown,
  status = 200
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const TASK_BODY = {
  success: true,
  data: {
    taskId: "t-1",
    status: "success",
    message: "Rankings query completed.",
    data: { type: "query", title: "Rankings query completed.", items: [] },
    traces: [],
    warnings: [UNSUPPORTED_YEAR_WARNING],
  },
};

describe("shouldConsultEngine", () => {
  it("consults for a data question", () => {
    expect(shouldConsultEngine("QS 2025 rankings")).toBe(true);
    expect(shouldConsultEngine("推薦幾所學校")).toBe(true);
    expect(shouldConsultEngine("compare NTU and NTHU")).toBe(true);
  });

  it("consults on a bare year, which carries no keyword at all", () => {
    // "what about 2025?" is exactly the turn that needs the disclosure and the
    // one a keyword gate would miss.
    expect(shouldConsultEngine("what about 2025?")).toBe(true);
  });

  it("skips small talk, so an ordinary turn costs nothing", () => {
    expect(shouldConsultEngine("hello")).toBe(false);
    expect(shouldConsultEngine("what can you do?")).toBe(false);
    expect(shouldConsultEngine("")).toBe(false);
  });

  it("is not tripped by the bare word 'the'", () => {
    // Python's shared intent list matches \bthe\b for Times Higher Education.
    // Copying that here would make the gate fire on every English sentence.
    expect(shouldConsultEngine("tell me about the platform")).toBe(false);
  });
});

describe("runEngineTask", () => {
  it("asks the engine for data without prose and without a dev handoff", async () => {
    const fetchImpl = jest.fn(async () => engineResponse(TASK_BODY));

    await runEngineTask("QS 2025 rankings", {
      baseUrl: "http://localhost:8090",
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8090/api/v1/agent/tasks");
    const sent = JSON.parse(String(init.body));
    expect(sent.kind).toBe("data_query");
    expect(sent.user_input).toBe("QS 2025 rankings");
    // Both constraints matter: the model call belongs to pass two, and a
    // phrasing accident must not route a chat turn into the dev agent.
    expect(sent.constraints).toEqual({ generation: "disabled", route: "web" });
  });

  it("returns the engine's warnings and formatter payload", async () => {
    const outcome = await runEngineTask("QS 2025 rankings", {
      fetchImpl: (async () => engineResponse(TASK_BODY)) as unknown as typeof fetch,
    });

    expect(outcome.consulted).toBe(true);
    expect(outcome.warnings).toEqual([UNSUPPORTED_YEAR_WARNING]);
    expect(outcome.data).toMatchObject({ type: "query" });
    expect(outcome.skippedReason).toBeNull();
  });

  it("keeps the disclosure from a failed engine response", async () => {
    // A warehouse outage answers 500 and still carries the request-level
    // disclosure, because the engine attaches it in the funnel every branch
    // passes through. The year it could not answer for is still not 2026.
    const outcome = await runEngineTask("QS 2025 rankings", {
      fetchImpl: (async () =>
        engineResponse(
          {
            success: false,
            data: { status: "error", warnings: [UNSUPPORTED_YEAR_WARNING], data: {} },
          },
          500
        )) as unknown as typeof fetch,
    });

    expect(outcome.warnings).toEqual([UNSUPPORTED_YEAR_WARNING]);
  });

  it("makes no call at all for small talk", async () => {
    const fetchImpl = jest.fn();

    const outcome = await runEngineTask("hello", {
      fetchImpl: fetchImpl as unknown as typeof fetch,
    });

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(outcome.consulted).toBe(false);
    expect(outcome.warnings).toEqual([]);
  });

  it("degrades quietly when the agent API is unreachable", async () => {
    // 8090 and the warehouse behind it are not dependencies chat had before.
    // Losing them costs the disclosure, not the answer.
    const outcome = await runEngineTask("QS 2025 rankings", {
      fetchImpl: (async () => {
        throw new Error("ECONNREFUSED");
      }) as unknown as typeof fetch,
    });

    expect(outcome.consulted).toBe(false);
    expect(outcome.warnings).toEqual([]);
    expect(outcome.skippedReason).toBe("agent engine unavailable");
  });

  it("survives a body that is not the shape it expects", async () => {
    for (const body of [null, {}, { data: {} }, { data: { warnings: "nope" } }]) {
      const outcome = await runEngineTask("QS 2025 rankings", {
        fetchImpl: (async () => engineResponse(body)) as unknown as typeof fetch,
      });

      expect(outcome.warnings).toEqual([]);
    }
  });
});
