import React from "react";
import { render, screen } from "@testing-library/react";

import { PlanComparisonMatrix } from "@/components/PlanComparisonMatrix";

const plans = [
  {
    planName: "balanced" as const,
    reach: [],
    target: [],
    safety: [],
    planSummary: "Balanced summary",
    riskDistribution: "Overall plan risk: moderate (high=0, medium=1, low=1).",
    recommendedStrategy:
      "This is a balanced plan. Prioritize target schools while keeping reach as upside.",
    primaryChoice: {
      universityName: "Target Option",
      bucket: "target" as const,
      reason: "Best balance of fit and manageable risk among target options.",
    },
    planWarnings: [],
    planConfidence: "high" as const,
    planConfidenceReason:
      "This plan has both target and safety coverage, and the strongest options look stable.",
  },
  {
    planName: "conservative" as const,
    reach: [],
    target: [],
    safety: [],
    planSummary: "Conservative summary",
    riskDistribution: "Overall plan risk: low (high=0, medium=0, low=2).",
    recommendedStrategy:
      "You can proceed confidently with this plan. Focus on execution and timeline.",
    primaryChoice: {
      universityName: "Safety Option",
      bucket: "safety" as const,
      reason: "Most stable option available in the current plan.",
    },
    planWarnings: [],
    planConfidence: "high" as const,
    planConfidenceReason: "This plan looks well supported by both structure and fit quality.",
  },
  {
    planName: "aggressive" as const,
    reach: [],
    target: [],
    safety: [],
    planSummary: "Aggressive summary",
    riskDistribution: "Overall plan risk: high (high=1, medium=1, low=0).",
    recommendedStrategy:
      "This plan leans risky. Consider adding 1–2 safer options while keeping upside in view.",
    primaryChoice: {
      universityName: "Reach Option",
      bucket: "reach" as const,
      reason: "Highest-upside option available, but the plan is currently risk-heavy.",
    },
    planWarnings: ["Plan leans high-risk"],
    planConfidence: "medium" as const,
    planConfidenceReason:
      "This plan has some stable structure, but at least one core bucket is weaker or less secure.",
  },
];

describe("PlanComparisonMatrix", () => {
  it("renders all three plans", () => {
    render(
      <PlanComparisonMatrix
        plans={plans}
        planComparison={{
          recommendedPlan: "balanced",
          reason: "Balanced is recommended because it keeps the strongest overall mix with stable confidence.",
          tradeoffs: [],
        }}
      />
    );

    expect(screen.getByTestId("plan-column-balanced")).toBeInTheDocument();
    expect(screen.getByTestId("plan-column-conservative")).toBeInTheDocument();
    expect(screen.getByTestId("plan-column-aggressive")).toBeInTheDocument();
  });

  it("highlights the recommended plan", () => {
    render(
      <PlanComparisonMatrix
        plans={plans}
        planComparison={{
          recommendedPlan: "balanced",
          reason: "Balanced is recommended because it keeps the strongest overall mix with stable confidence.",
          tradeoffs: [],
        }}
      />
    );

    expect(screen.getAllByText("Recommended").length).toBeGreaterThan(0);
  });

  it("shows warning fallback when warnings are empty", () => {
    render(
      <PlanComparisonMatrix
        plans={plans}
        planComparison={{
          recommendedPlan: "balanced",
          reason: "Balanced is recommended because it keeps the strongest overall mix with stable confidence.",
          tradeoffs: [],
        }}
      />
    );

    expect(screen.getAllByText("No major warning signals").length).toBeGreaterThan(0);
  });

  it("does not break when optional fields are missing", () => {
    render(
      <PlanComparisonMatrix
        plans={[
          {
            ...plans[0],
            primaryChoice: undefined,
            planConfidence: undefined,
            planConfidenceReason: undefined,
            planWarnings: undefined,
            recommendedStrategy: "",
          },
        ]}
      />
    );

    expect(screen.getByText("Plan Comparison")).toBeInTheDocument();
  });
});
