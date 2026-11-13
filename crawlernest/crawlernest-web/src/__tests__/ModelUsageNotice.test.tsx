import { render, screen, waitFor } from "@testing-library/react";
import { ModelUsageNotice } from "@/app/desk/ModelUsageNotice";
import { toModelUsage } from "@/lib/deskApi";

const originalFetch = global.fetch;

function respond(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

const USAGE = {
  last24Hours: { modelCalls: 12, unreachableCalls: 0, promptTokens: 9120, completionTokens: 1404, callsWithoutUsage: 0 },
  budget: { enforced: true, modelCallsPerDay: 300, modelCallsLeft: 288, reservedPerRequest: {} },
  notes: [],
};

afterEach(() => {
  global.fetch = originalFetch;
});

describe("toModelUsage", () => {
  it("reads the API shape", () => {
    expect(toModelUsage(USAGE)).toEqual({
      modelCalls: 12, unreachableCalls: 0, promptTokens: 9120, completionTokens: 1404, callsWithoutUsage: 0,
      perDay: 300, left: 288,
    });
  });

  it("has no budget figures when none is enforced", () => {
    expect(toModelUsage({ ...USAGE, budget: { enforced: false } })).toMatchObject({ perDay: null, left: null });
  });

  it("refuses an enforced budget without its figures, rather than showing a made-up N of M", () => {
    expect(toModelUsage({ ...USAGE, budget: { enforced: true } })).toBeNull();
    expect(toModelUsage({ budget: USAGE.budget })).toBeNull();
    expect(toModelUsage(null)).toBeNull();
  });
});

describe("ModelUsageNotice", () => {
  it("shows what is left of the day's budget, from the desk usage endpoint", async () => {
    const fetchMock = jest.fn().mockResolvedValue(respond(200, { success: true, data: USAGE }));
    global.fetch = fetchMock;
    render(<ModelUsageNotice />);
    const line = await screen.findByTestId("model-usage");
    expect(line).toHaveTextContent("Model calls left today: 288 / 300");
    expect(line).toHaveTextContent("10,524 tokens used.");
    expect(line).not.toHaveTextContent("At least");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/user/desk/usage");
  });

  it("says a token total is a lower bound when some calls reported none, and turns amber when low", async () => {
    global.fetch = jest.fn().mockResolvedValue(respond(200, { success: true, data: {
      ...USAGE,
      last24Hours: { ...USAGE.last24Hours, callsWithoutUsage: 2, unreachableCalls: 1 },
      budget: { enforced: true, modelCallsPerDay: 300, modelCallsLeft: 0 },
    } }));
    render(<ModelUsageNotice />);
    const line = await screen.findByTestId("model-usage");
    expect(line).toHaveTextContent("0 / 300");
    expect(line).toHaveTextContent("will be refused");
    expect(line).toHaveTextContent("At least 10,524 tokens used.");
    expect(line).toHaveTextContent("1 call could not reach the model and did not count.");
    expect(line.className).toContain("amber");
  });

  it("says when no limit is set", async () => {
    global.fetch = jest.fn().mockResolvedValue(respond(200, { success: true, data: { ...USAGE, budget: { enforced: false } } }));
    render(<ModelUsageNotice />);
    expect(await screen.findByTestId("model-usage")).toHaveTextContent("Model calls in the last 24 hours: 12 (no limit set).");
  });

  it("shows nothing when signed out or when the usage cannot be read", async () => {
    const fetchMock = jest.fn().mockResolvedValue(respond(401, { success: false }));
    global.fetch = fetchMock;
    const { container, unmount } = render(<ModelUsageNotice />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    unmount();

    global.fetch = jest.fn().mockResolvedValue(respond(503, { success: false, error: "down" }));
    const second = render(<ModelUsageNotice />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(second.container).toBeEmptyDOMElement();
  });
});
