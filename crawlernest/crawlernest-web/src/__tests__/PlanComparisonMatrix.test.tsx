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

  it("renders deterministic delta lines when provided", () => {
    render(
      <PlanComparisonMatrix
        plans={plans}
        planComparison={{
          recommendedPlan: "balanced",
          reason: "Balanced is recommended because it keeps the strongest overall mix with stable confidence.",
          tradeoffs: [],
        }}
        planDelta={{
          recommendedPlan: "balanced",
          comparisonAgainstAlternatives: [
            "The balanced plan keeps safety coverage that the aggressive plan does not.",
            "The balanced plan carries fewer warning signals than the aggressive plan.",
          ],
        }}
      />
    );

    expect(screen.getByText("Why this plan stands out")).toBeInTheDocument();
    expect(
      screen.getByText("The balanced plan keeps safety coverage that the aggressive plan does not.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("The balanced plan carries fewer warning signals than the aggressive plan.")
    ).toBeInTheDocument();
  });

  it("omits the delta section when there are no lines", () => {
    render(
      <PlanComparisonMatrix
        plans={plans}
        planDelta={{
          recommendedPlan: "balanced",
          comparisonAgainstAlternatives: [],
        }}
      />
    );

    expect(screen.queryByText("Why this plan stands out")).not.toBeInTheDocument();
  });

  it("renders the selected-plan comparison section", () => {
    render(
      <PlanComparisonMatrix
        plans={plans}
        selectedPlanComparison={{
          selectedPlan: "aggressive",
          recommendedPlan: "balanced",
          summary: "This plan trades safety for more upside.",
          differences: [
            "The selected plan keeps less safety coverage than the recommended plan.",
            "The selected plan carries more warning signals than the recommended plan.",
          ],
        }}
      />
    );

    expect(screen.getByText("Compared with the recommended plan")).toBeInTheDocument();
    expect(screen.getByText("This plan trades safety for more upside.")).toBeInTheDocument();
    expect(
      screen.getByText("The selected plan keeps less safety coverage than the recommended plan.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("The selected plan carries more warning signals than the recommended plan.")
    ).toBeInTheDocument();
  });

  it("omits the selected-plan comparison section when it is absent", () => {
    render(<PlanComparisonMatrix plans={plans} />);

    expect(screen.queryByText("Compared with the recommended plan")).not.toBeInTheDocument();
  });

  it("renders the scenario simulation section", () => {
    render(
      <PlanComparisonMatrix
        plans={plans}
        scenarioSimulation={{
          scenarioInput: {
            ielts_delta: 0.5,
          },
          recommendedPlanBefore: "balanced",
          recommendedPlanAfter: "aggressive",
          changeSummary: "The recommended plan shifts from balanced to aggressive under this scenario.",
          keyDifferences: [
            "Overall plan confidence improves under this scenario.",
            "The plan mix becomes more aggressive.",
          ],
        }}
      />
    );

    expect(screen.getByText("What changes if your profile improves")).toBeInTheDocument();
    expect(
      screen.getByText("The recommended plan shifts from balanced to aggressive under this scenario.")
    ).toBeInTheDocument();
    expect(screen.getByText("Overall plan confidence improves under this scenario.")).toBeInTheDocument();
  });

  it("omits the scenario simulation section when it is absent", () => {
    render(<PlanComparisonMatrix plans={plans} />);

    expect(screen.queryByText("What changes if your profile improves")).not.toBeInTheDocument();
  });

  it("renders the multi-scenario comparison section", () => {
    render(
      <PlanComparisonMatrix
        plans={plans}
        scenarioComparison={{
          baselineRecommendedPlan: "balanced",
          scenarios: [
            {
              scenarioKey: "ielts_plus_0_5",
              scenarioLabel: "IELTS +0.5",
              recommendedPlanAfter: "balanced",
              changeSummary: "The recommended plan remains stable under this scenario.",
              keyDifferences: ["Overall plan confidence improves under this scenario."],
            },
          ],
        }}
        bestScenarioInsight={{
          scenarioKey: "ielts_plus_0_5",
          scenarioLabel: "IELTS +0.5",
          reason: "This scenario most improves plan confidence without increasing instability.",
        }}
      />
    );

    expect(screen.getByText("Which improvement helps most")).toBeInTheDocument();
    expect(screen.getAllByText("IELTS +0.5").length).toBeGreaterThan(0);
    expect(
      screen.getByText("This scenario most improves plan confidence without increasing instability.")
    ).toBeInTheDocument();
  });

  it("omits the multi-scenario comparison section when scenarios are absent", () => {
    render(<PlanComparisonMatrix plans={plans} />);

    expect(screen.queryByText("Which improvement helps most")).not.toBeInTheDocument();
  });
});
