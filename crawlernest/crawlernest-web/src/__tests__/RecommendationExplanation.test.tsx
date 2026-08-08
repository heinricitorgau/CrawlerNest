import { render, screen, waitFor } from "@testing-library/react";

import RecommendationExplanation from "@/components/RecommendationExplanation";

const ITEMS = [
  {
    universityName: "National Taiwan University",
    country: "Taiwan",
    category: "target",
    aggregatedRank: 68,
    matchingScore: 0.82,
  },
];

function mockFetchOnce(body: unknown, ok = true) {
  global.fetch = jest.fn().mockResolvedValue({
    ok,
    json: async () => body,
  }) as unknown as typeof fetch;
}

describe("RecommendationExplanation", () => {
  afterEach(() => {
    jest.resetAllMocks();
  });

  it("renders model-written prose when the model answered", async () => {
    mockFetchOnce({
      success: true,
      data: {
        source: "llm",
        modelName: "deepseek-v4-flash",
        paragraphs: ["NTU is a target-tier match at rank 68."],
      },
    });

    render(<RecommendationExplanation items={ITEMS} />);

    expect(
      await screen.findByText("NTU is a target-tier match at rank 68.")
    ).toBeInTheDocument();
    expect(screen.getByText(/deepseek-v4-flash/)).toBeInTheDocument();
    // The provenance disclaimer must always accompany the prose.
    expect(
      screen.getByText(/Ranks, scores, and confidence come from the ranking data/)
    ).toBeInTheDocument();
  });

  it("renders nothing when the deterministic fallback was used", async () => {
    // Deterministic text must never be presented as a model explanation.
    mockFetchOnce({
      success: true,
      data: {
        source: "fallback",
        modelName: null,
        paragraphs: ["Rule-based reply."],
      },
    });

    const { container } = render(<RecommendationExplanation items={ITEMS} />);

    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(screen.queryByText("Rule-based reply.")).not.toBeInTheDocument();
  });

  it("renders nothing when the agent is unreachable", async () => {
    global.fetch = jest
      .fn()
      .mockRejectedValue(new Error("network down")) as unknown as typeof fetch;

    const { container } = render(<RecommendationExplanation items={ITEMS} />);

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("does not call the agent when there are no items", () => {
    const fetchMock = jest.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    const { container } = render(<RecommendationExplanation items={[]} />);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it("uses the given title and task kind for a comparison", async () => {
    mockFetchOnce({
      success: true,
      data: { source: "llm", modelName: null, paragraphs: ["NTU ranks higher."] },
    });

    render(
      <RecommendationExplanation
        items={ITEMS}
        taskKind="comparison"
        title="How these compare"
      />
    );

    expect(await screen.findByText("NTU ranks higher.")).toBeInTheDocument();
    expect(screen.getByText("How these compare")).toBeInTheDocument();
  });

  it("explains a plan even though it carries no rows", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { source: "llm", paragraphs: ["Plan prose."] } }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    render(
      <RecommendationExplanation
        items={[]}
        taskKind="application_plan"
        plan={{ planName: "balanced", reach: [{ universityName: "A University" }] }}
      />
    );

    expect(await screen.findByText("Plan prose.")).toBeInTheDocument();
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.taskKind).toBe("application_plan");
    expect(body.plan.planName).toBe("balanced");
  });

  it("sends the displayed rows to the explain route", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { source: "llm", paragraphs: ["ok"] } }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    render(<RecommendationExplanation items={ITEMS} caveats={["Only QS."]} />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/agent/explain");
    const body = JSON.parse(options.body);
    expect(body.taskKind).toBe("recommendation");
    expect(body.items).toEqual(ITEMS);
    expect(body.caveats).toEqual(["Only QS."]);
  });
});
