import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { RecommendationPageContent } from "@/app/recommendations/page";
import { fetchAppJson } from "@/lib/api";

jest.mock("next/link", () => {
  return function MockLink({
    children,
    href,
    ...props
  }: {
    children: ReactNode;
    href: string;
  }) {
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  };
});

jest.mock("@/lib/api", () => ({
  fetchAppJson: jest.fn(),
}));

const mockedFetchAppJson = fetchAppJson as jest.MockedFunction<typeof fetchAppJson>;
const STORAGE_KEY = "crawlernest_recommendation_flow";

function createRecommendationResponse() {
  return {
    success: true,
    data: {
      reach: [],
      target: [],
      safety: [],
    },
    applicationPlans: [
      {
        planName: "balanced" as const,
        reach: [],
        target: [],
        safety: [],
        planSummary: "Balanced summary",
        riskDistribution: "Balanced risk",
        recommendedStrategy: "Balanced strategy",
      },
      {
        planName: "conservative" as const,
        reach: [],
        target: [],
        safety: [],
        planSummary: "Conservative summary",
        riskDistribution: "Conservative risk",
        recommendedStrategy: "Conservative strategy",
      },
      {
        planName: "aggressive" as const,
        reach: [],
        target: [],
        safety: [],
        planSummary: "Aggressive summary",
        riskDistribution: "Aggressive risk",
        recommendedStrategy: "Aggressive strategy",
      },
    ],
    planComparison: {
      recommendedPlan: "balanced" as const,
      reason: "Balanced fits best right now.",
      tradeoffs: [],
    },
  };
}

describe("RecommendationPageContent import summary", () => {
  beforeEach(() => {
    localStorage.clear();
    mockedFetchAppJson.mockReset();
    mockedFetchAppJson.mockResolvedValue(createRecommendationResponse());
  });

  it("restores profile fields and selected plan from valid imported JSON", async () => {
    render(<RecommendationPageContent />);

    fireEvent.change(screen.getByTestId("import-summary-textarea"), {
      target: {
        value: JSON.stringify({
          profileSnapshot: {
            country: "Canada",
            ielts: 7,
            gpa: 3.8,
            targetRank: 80,
          },
          recommendedPlan: {
            plan: "balanced",
          },
          selectedPlan: {
            plan: "conservative",
            summary: "Conservative summary",
          },
        }),
      },
    });

    fireEvent.click(screen.getByTestId("restore-summary-button"));

    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));
    const requestPath = decodeURIComponent(mockedFetchAppJson.mock.calls[0][0]);
    expect(requestPath).toContain("country=Canada");
    expect(requestPath).toContain("ieltsScore=7");
    expect(requestPath).toContain("gpaScore=3.8");
    expect(requestPath).toContain("targetRank=80");
    expect(requestPath).toContain("selectedPlan=conservative");
    expect(screen.getByTestId("import-summary-status")).toHaveTextContent(
      "Restored decision summary."
    );
    expect(screen.getByLabelText("Country")).toHaveValue("Canada");
    expect(screen.getByLabelText("IELTS Score")).toHaveValue(7);
    await waitFor(() => {
      expect(
        within(screen.getByTestId("plan-card-conservative")).getByText("Selected")
      ).toBeInTheDocument();
    });
  });

  it("restores a known scenario label into the scenario preset controls", async () => {
    render(<RecommendationPageContent />);

    fireEvent.change(screen.getByTestId("import-summary-textarea"), {
      target: {
        value: JSON.stringify({
          profileSnapshot: {
            country: "United Kingdom",
            ielts: 6.5,
            targetRank: 100,
          },
          recommendedPlan: {
            plan: "balanced",
          },
          bestScenario: {
            scenario: "IELTS +0.5",
          },
        }),
      },
    });

    fireEvent.click(screen.getByTestId("restore-summary-button"));

    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText("IELTS Delta")).toHaveValue(0.5);
    expect(decodeURIComponent(mockedFetchAppJson.mock.calls[0][0])).toContain(
      'scenario={"ielts_delta":0.5}'
    );
  });

  it("shows safe failure for malformed JSON and changes nothing", async () => {
    render(<RecommendationPageContent />);

    fireEvent.change(screen.getByTestId("import-summary-textarea"), {
      target: {
        value: "{not valid json",
      },
    });

    fireEvent.click(screen.getByTestId("restore-summary-button"));

    expect(mockedFetchAppJson).not.toHaveBeenCalled();
    expect(screen.getByTestId("import-summary-status")).toHaveTextContent(
      "Could not restore summary."
    );
    expect(screen.getByLabelText("Country")).toHaveValue("United Kingdom");
    expect(screen.getByLabelText("IELTS Score")).toHaveValue(6.5);
  });

  it("ignores invalid fields in valid JSON without crashing", async () => {
    render(<RecommendationPageContent />);

    fireEvent.change(screen.getByTestId("import-summary-textarea"), {
      target: {
        value: JSON.stringify({
          profileSnapshot: {
            country: "Australia",
            ielts: "bad",
            toefl: Number.POSITIVE_INFINITY,
            targetRank: 120,
          },
          recommendedPlan: {
            plan: "balanced",
          },
          selectedPlan: {
            plan: "invalid-plan",
          },
          bestScenario: {
            scenario: "Unknown scenario",
          },
        }),
      },
    });

    fireEvent.click(screen.getByTestId("restore-summary-button"));

    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));
    const requestPath = decodeURIComponent(mockedFetchAppJson.mock.calls[0][0]);
    expect(requestPath).toContain("country=Australia");
    expect(requestPath).toContain("targetRank=120");
    expect(requestPath).not.toContain("selectedPlan=");
    expect(requestPath).not.toContain("scenario=");
    expect(screen.getByLabelText("Country")).toHaveValue("Australia");
    expect(screen.getByLabelText("IELTS Score")).toHaveValue(6.5);
  });

  it("updates local persistence after successful import", async () => {
    render(<RecommendationPageContent />);

    fireEvent.change(screen.getByTestId("import-summary-textarea"), {
      target: {
        value: JSON.stringify({
          profileSnapshot: {
            country: "Canada",
            ielts: 7,
            targetRank: 90,
          },
          recommendedPlan: {
            plan: "balanced",
          },
          selectedPlan: {
            plan: "conservative",
          },
          bestScenario: {
            scenario: "IELTS +0.5",
          },
          nextAction: {
            type: "improvement",
          },
        }),
      },
    });

    fireEvent.click(screen.getByTestId("restore-summary-button"));

    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
      expect(stored.selectedPlan).toBe("conservative");
      expect(stored.selectedScenarioKey).toBe("ielts_plus_0_5");
      expect(stored.currentFocus).toBe("plan");
      expect(stored.profileDraft.country).toBe("Canada");
    });
  });

  it("reset exploration clears restored imported state", async () => {
    render(<RecommendationPageContent />);

    fireEvent.change(screen.getByTestId("import-summary-textarea"), {
      target: {
        value: JSON.stringify({
          profileSnapshot: {
            country: "Canada",
            ielts: 7,
            targetRank: 90,
          },
          recommendedPlan: {
            plan: "balanced",
          },
          selectedPlan: {
            plan: "conservative",
          },
        }),
      },
    });

    fireEvent.click(screen.getByTestId("restore-summary-button"));

    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByText("Reset exploration"));

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    });
    expect(screen.getByLabelText("Country")).toHaveValue("United Kingdom");
    expect(screen.getByLabelText("IELTS Score")).toHaveValue(6.5);
  });
});
