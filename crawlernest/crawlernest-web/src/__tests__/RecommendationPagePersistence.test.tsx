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

describe("RecommendationPageContent persistence", () => {
  beforeEach(() => {
    localStorage.clear();
    mockedFetchAppJson.mockReset();
    mockedFetchAppJson.mockResolvedValue(createRecommendationResponse());
  });

  it("restores a persisted selected plan and refetches with that focus", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        selectedPlan: "conservative",
        selectedScenarioKey: null,
        currentFocus: "plan",
        profileDraft: {},
      })
    );

    render(<RecommendationPageContent />);

    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));
    expect(mockedFetchAppJson.mock.calls[0][0]).toContain("selectedPlan=conservative");
    expect(screen.getByTestId("restored-state-cue")).toBeInTheDocument();

    await waitFor(() => {
      expect(
        within(screen.getByTestId("plan-card-conservative")).getByText("Selected")
      ).toBeInTheDocument();
    });
  });

  it("restores a persisted scenario preset into the UI", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        selectedPlan: null,
        selectedScenarioKey: "ielts_plus_0_5",
        currentFocus: "scenario",
        profileDraft: {},
      })
    );

    render(<RecommendationPageContent />);

    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText("IELTS Delta")).toHaveValue(0.5);
    expect(decodeURIComponent(mockedFetchAppJson.mock.calls[0][0])).toContain(
      'scenario={"ielts_delta":0.5}'
    );
  });

  it("ignores invalid stored values safely", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        selectedPlan: "invalid-plan",
        selectedScenarioKey: "bad-scenario",
        currentFocus: "unknown-focus",
        profileDraft: {
          country: "",
          ielts: "bad",
          toefl: "wrong",
          gpa: "still-wrong",
          duolingo: "oops",
          targetRank: "not-a-number",
        },
      })
    );

    render(<RecommendationPageContent />);

    expect(mockedFetchAppJson).not.toHaveBeenCalled();
    expect(screen.queryByTestId("restored-state-cue")).not.toBeInTheDocument();
    expect(screen.getByLabelText("IELTS Score")).toHaveValue(6.5);
    expect(screen.getByLabelText("Target Rank")).toHaveValue(100);
    expect(screen.getByLabelText("TOEFL Score (optional)")).toHaveValue(null);
  });

  it("clears persisted exploration state when reset is clicked", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        selectedPlan: "balanced",
        selectedScenarioKey: "ielts_plus_0_5",
        currentFocus: "scenario",
        profileDraft: {
          gpa: 3.7,
        },
      })
    );

    render(<RecommendationPageContent />);

    await waitFor(() => expect(mockedFetchAppJson).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByText("Reset exploration"));

    await waitFor(() => {
      expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    });
    expect(screen.queryByTestId("restored-state-cue")).not.toBeInTheDocument();
    expect(screen.getByLabelText("IELTS Delta")).toHaveValue(null);
  });

  it("shows the restored-state cue only when valid state was restored", async () => {
    const firstRender = render(<RecommendationPageContent />);
    expect(screen.queryByTestId("restored-state-cue")).not.toBeInTheDocument();
    firstRender.unmount();

    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        selectedPlan: "balanced",
        selectedScenarioKey: null,
        currentFocus: "plan",
        profileDraft: {},
      })
    );

    render(<RecommendationPageContent />);

    await waitFor(() => {
      expect(screen.getByTestId("restored-state-cue")).toBeInTheDocument();
    });
  });
});
