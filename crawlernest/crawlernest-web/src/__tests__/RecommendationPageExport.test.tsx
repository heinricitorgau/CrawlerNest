import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { RecommendationPageContent, buildDecisionSummaryText } from "@/app/recommendations/page";
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

function createResponseWithSummary(overrides?: Record<string, unknown>) {
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
        target: [
          {
            universityName: "University of Example",
            decision: "apply_early",
            reason: "Strong fit reason",
          },
        ],
        safety: [],
        planSummary: "Balanced summary",
        riskDistribution: "Balanced risk",
        recommendedStrategy: "Balanced strategy",
      },
    ],
    planComparison: {
      recommendedPlan: "balanced" as const,
      reason: "Balanced fits best right now.",
      tradeoffs: [],
    },
    decisionSummaryCompact: {
      plan: "Balanced",
      confidence: "High",
      risk: "Moderate",
      topReason: "Strong coverage with stable requirements",
      nextStep: "GPA +0.2",
    },
    decisionSummary: {
      generatedAt: "2026-04-24T00:00:00+00:00",
      profileSnapshot: {
        country: "United Kingdom",
        ielts: 6.5,
        targetRank: 100,
      },
      recommendedPlan: {
        plan: "balanced" as const,
        summary: "Balanced summary",
        confidence: "high",
        confidenceReason: "Stable confidence reason",
      },
      topRecommendation: {
        university: "University of Example",
        decision: "apply_early",
        reason: "Strong fit reason",
      },
      nextAction: {
        type: "improvement" as const,
        action: "Improve GPA by 0.2",
        reason: "This is the most practical improvement to strengthen your current plan.",
      },
      ...overrides,
    },
  };
}

describe("RecommendationPageContent export summary", () => {
  beforeEach(() => {
    localStorage.clear();
    mockedFetchAppJson.mockReset();
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("copies the decision summary as pretty JSON", async () => {
    mockedFetchAppJson.mockResolvedValue(createResponseWithSummary());

    render(<RecommendationPageContent />);
    fireEvent.click(screen.getByText("Generate Recommendations"));

    await waitFor(() => {
      expect(screen.getByText("Export your decision summary")).toBeInTheDocument();
    });
    expect(
      screen.getByText("Copy your current decision state so you can save or share it.")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("copy-summary-json"));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        JSON.stringify(createResponseWithSummary().decisionSummary, null, 2)
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId("copy-summary-status")).toHaveTextContent(
        "Copied JSON summary."
      );
    });
  });

  it("copies the decision summary as polished deterministic text", async () => {
    mockedFetchAppJson.mockResolvedValue(
      createResponseWithSummary({
        bestScenario: {
          scenario: "IELTS +0.5",
          effect: "The recommended plan remains stable under this scenario.",
        },
        improvementPriority: {
          action: "GPA +0.2",
          impact: "medium",
          effort: "medium",
          reason: "This scenario may help, but the expected gain and effort are more balanced.",
        },
      })
    );

    render(<RecommendationPageContent />);
    fireEvent.click(screen.getByText("Generate Recommendations"));

    await waitFor(() => {
      expect(screen.getByTestId("copy-summary-text")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("copy-summary-text"));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        expect.stringContaining(
          "Decision Snapshot\n- Plan: Balanced\n- Confidence: High\n- Risk: Moderate\n- Next Step: GPA +0.2"
        )
      );
    });
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining(
        "Decision Summary\n\nProfile\n- Country: United Kingdom\n- IELTS: 6.5\n- Target Rank: 100"
      )
    );
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining(
        "Recommended Plan\n- Plan: Balanced\n- Confidence: High\n- Summary: Balanced summary\n- Reason: Stable confidence reason"
      )
    );
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining(
        "Top Recommendation\n- University: University of Example\n- Decision: Apply early\n- Reason: Strong fit reason"
      )
    );
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining("Most Helpful Scenario\n- Scenario: IELTS +0.5")
    );
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining(
        "Most Worthwhile Improvement\n- Action: GPA +0.2\n- Impact: Medium\n- Effort: Medium"
      )
    );
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining(
        "Next Step\n- Action: Improve GPA by 0.2\n- Reason: This is the most practical improvement to strengthen your current plan."
      )
    );
    await waitFor(() => {
      expect(screen.getByTestId("copy-summary-status")).toHaveTextContent(
        "Copied text summary."
      );
    });
  });

  it("renders the compact decision banner", async () => {
    mockedFetchAppJson.mockResolvedValue(createResponseWithSummary());

    render(<RecommendationPageContent />);
    fireEvent.click(screen.getByText("Generate Recommendations"));

    await waitFor(() => {
      expect(screen.getByText("Balanced Plan")).toBeInTheDocument();
    });
    expect(screen.getByText("High Confidence")).toBeInTheDocument();
    expect(screen.getByText("Next: GPA +0.2")).toBeInTheDocument();
    expect(screen.getByText("Strong coverage with stable requirements")).toBeInTheDocument();
  });

  it("can build text export without compact snapshot for backward compatibility", () => {
    const text = buildDecisionSummaryText(createResponseWithSummary().decisionSummary);

    expect(text).toContain(
      "Decision Summary\n\nProfile\n- Country: United Kingdom\n- IELTS: 6.5\n- Target Rank: 100"
    );
    expect(text).not.toContain("Decision Snapshot");
  });

  it("adds compact snapshot to text export helper", () => {
    const response = createResponseWithSummary();
    const text = buildDecisionSummaryText(response.decisionSummary, response.decisionSummaryCompact);

    expect(text).toContain(
      "Decision Snapshot\n- Plan: Balanced\n- Confidence: High\n- Risk: Moderate\n- Next Step: GPA +0.2"
    );
    expect(text).toContain(
      "Decision Summary\n\nProfile\n- Country: United Kingdom\n- IELTS: 6.5\n- Target Rank: 100"
    );
  });

  it("skips missing optional sections in text export without broken output", async () => {
    mockedFetchAppJson.mockResolvedValue(
      createResponseWithSummary({
        selectedPlan: undefined,
        planComparison: undefined,
        bestScenario: undefined,
        improvementPriority: undefined,
      })
    );

    render(<RecommendationPageContent />);
    fireEvent.click(screen.getByText("Generate Recommendations"));

    await waitFor(() => {
      expect(screen.getByTestId("copy-summary-text")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("copy-summary-text"));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalled();
    });
    const copiedText = (navigator.clipboard.writeText as jest.Mock).mock.calls[0][0];
    expect(copiedText).not.toContain("Selected Plan");
    expect(copiedText).not.toContain("Plan Comparison");
    expect(copiedText).not.toContain("Most Helpful Scenario");
    expect(copiedText).toContain("Recommended Plan");
    expect(copiedText).toContain("Top Recommendation");
    expect(copiedText).toContain("Decision Summary");
  });

  it("uses safe copy failure feedback", async () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockRejectedValue(new Error("copy failed")),
      },
    });
    mockedFetchAppJson.mockResolvedValue(createResponseWithSummary());

    render(<RecommendationPageContent />);
    fireEvent.click(screen.getByText("Generate Recommendations"));

    await waitFor(() => {
      expect(screen.getByTestId("copy-summary-text")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("copy-summary-text"));

    await waitFor(() => {
      expect(screen.getByTestId("copy-summary-status")).toHaveTextContent(
        "Could not copy summary."
      );
    });
  });

  it("formats normalized readable values in the text export helper", () => {
    const text = buildDecisionSummaryText(
      createResponseWithSummary({
        selectedPlan: {
          plan: "aggressive",
          summary: "Aggressive summary",
        },
      }).decisionSummary
    );

    expect(text).toContain("Decision Summary");
    expect(text).toContain("Recommended Plan");
    expect(text).toContain("- Plan: Balanced");
    expect(text).toContain("- Confidence: High");
    expect(text).toContain("- Decision: Apply early");
    expect(text).toContain("Selected Plan\n- Plan: Aggressive");
  });
});
