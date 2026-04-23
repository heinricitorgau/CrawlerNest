type ApplicationPlan = {
  planName: "balanced" | "conservative" | "aggressive";
  primaryChoice?: {
    universityName: string;
  };
  planConfidence?: "high" | "medium" | "low";
  planConfidenceReason?: string;
  planWarnings?: string[];
  riskDistribution: string;
  recommendedStrategy: string;
};

type PlanComparison = {
  recommendedPlan: "balanced" | "conservative" | "aggressive";
  reason: string;
  tradeoffs: string[];
};

type PlanDelta = {
  recommendedPlan: "balanced" | "conservative" | "aggressive";
  comparisonAgainstAlternatives: string[];
};

type SelectedPlanComparison = {
  selectedPlan: "balanced" | "conservative" | "aggressive";
  recommendedPlan: "balanced" | "conservative" | "aggressive";
  summary: string;
  differences: string[];
};

type ScenarioSimulation = {
  scenarioInput: {
    ielts_delta?: number;
    toefl_delta?: number;
    gpa_delta?: number;
    target_rank_delta?: number;
  };
  recommendedPlanBefore: "balanced" | "conservative" | "aggressive";
  recommendedPlanAfter: "balanced" | "conservative" | "aggressive";
  changeSummary: string;
  keyDifferences: string[];
};

type ScenarioComparison = {
  baselineRecommendedPlan: "balanced" | "conservative" | "aggressive";
  scenarios: Array<{
    scenarioKey: string;
    scenarioLabel: string;
    recommendedPlanAfter: "balanced" | "conservative" | "aggressive";
    changeSummary: string;
    keyDifferences: string[];
  }>;
};

type BestScenarioInsight = {
  scenarioKey: string;
  scenarioLabel: string;
  reason: string;
};

type ImprovementPriority = {
  recommendedScenarioKey: string;
  recommendedScenarioLabel: string;
  priorityReason: string;
  effortLevel: "low" | "medium" | "high";
  impactLevel: "low" | "medium" | "high";
  priorityTier: "low" | "medium" | "high";
};

type NextActionGuide = {
  currentFocus: "plan" | "scenario" | "improvement";
  suggestedNextAction: string;
  actionType: "explore_scenario" | "focus_plan" | "improve_profile";
  reason: string;
  suggestedTarget: {
    type: "plan" | "scenario";
    key: string;
    label: string;
  };
};

function formatPlanConfidenceLabel(value: ApplicationPlan["planConfidence"] | undefined) {
  if (!value) {
    return null;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function truncatePlanText(text: string | undefined, maxLength = 110) {
  if (!text) {
    return null;
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1).trimEnd()}...`;
}

function nextActionButtonLabel(actionType: NextActionGuide["actionType"] | undefined) {
  if (actionType === "focus_plan") {
    return "Focus this plan";
  }
  if (actionType === "explore_scenario") {
    return "Explore this scenario";
  }
  if (actionType === "improve_profile") {
    return "Prioritize this improvement";
  }
  return "Apply this step";
}

function nextActionFocusLabel(currentFocus: NextActionGuide["currentFocus"] | undefined) {
  if (currentFocus === "plan") {
    return "Current focus: plan choice";
  }
  if (currentFocus === "scenario") {
    return "Current focus: scenario exploration";
  }
  if (currentFocus === "improvement") {
    return "Current focus: improvement planning";
  }
  return null;
}

function nextActionBadgeLabel(actionType: NextActionGuide["actionType"] | undefined) {
  if (actionType === "focus_plan") {
    return "Plan action";
  }
  if (actionType === "explore_scenario") {
    return "Scenario action";
  }
  if (actionType === "improve_profile") {
    return "Improvement action";
  }
  return null;
}

function nextActionHelperText(actionType: NextActionGuide["actionType"] | undefined) {
  if (actionType === "focus_plan") {
    return "This will switch the comparison focus to the suggested plan.";
  }
  if (actionType === "explore_scenario") {
    return "This will apply the suggested scenario to the current comparison.";
  }
  if (actionType === "improve_profile") {
    return "This will load the most worthwhile improvement into the current scenario view.";
  }
  return "This will apply the suggested next step in the current view.";
}

export function PlanComparisonMatrix({
  plans,
  planComparison,
  planDelta,
  selectedPlanComparison,
  scenarioSimulation,
  scenarioComparison,
  bestScenarioInsight,
  improvementPriority,
  nextActionGuide,
  onActivateTarget,
}: {
  plans: ApplicationPlan[];
  planComparison?: PlanComparison;
  planDelta?: PlanDelta;
  selectedPlanComparison?: SelectedPlanComparison;
  scenarioSimulation?: ScenarioSimulation;
  scenarioComparison?: ScenarioComparison;
  bestScenarioInsight?: BestScenarioInsight;
  improvementPriority?: ImprovementPriority;
  nextActionGuide?: NextActionGuide;
  onActivateTarget?: (target: NextActionGuide["suggestedTarget"]) => void;
}) {
  const orderedPlanNames: Array<"balanced" | "conservative" | "aggressive"> = [
    "balanced",
    "conservative",
    "aggressive",
  ];
  const planMap = new Map<"balanced" | "conservative" | "aggressive", ApplicationPlan>(
    (plans ?? []).map((plan) => [plan.planName, plan])
  );
  const orderedPlans = orderedPlanNames
    .map((name) => planMap.get(name))
    .filter((plan): plan is ApplicationPlan => Boolean(plan));
  const highlightedActionType = nextActionGuide?.actionType;
  const focusLabel = nextActionFocusLabel(nextActionGuide?.currentFocus);
  const actionBadge = nextActionBadgeLabel(nextActionGuide?.actionType);
  const buttonLabel = nextActionButtonLabel(nextActionGuide?.actionType);
  const helperText = nextActionHelperText(nextActionGuide?.actionType);

  if (orderedPlans.length === 0) {
    return null;
  }

  return (
    <div className="mt-5 rounded-2xl border border-[#e0ddd8] bg-[#fcfbf8] p-4">
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
        Plan Comparison
      </div>
      {planComparison ? (
        <div className="mt-2 text-sm leading-6 text-[#6b7068]">
          <span className="font-semibold text-[#1a1a1a]">Recommended plan:</span>{" "}
          <span className="capitalize">{planComparison.recommendedPlan}</span>
          {planComparison.reason ? (
            <>
              {" "}
              <span className="font-semibold text-[#1a1a1a]">Reason:</span> {planComparison.reason}
            </>
          ) : null}
          <div className="mt-1 text-sm text-[#6b7068]">
            This is the plan the system currently prefers.
          </div>
        </div>
      ) : null}
      {planDelta && planDelta.comparisonAgainstAlternatives.length > 0 ? (
        <div className="mt-4 rounded-xl bg-[#f5f3ee] p-4">
          <div className="text-sm font-semibold text-[#1a3d2e]">
            Why this plan stands out
          </div>
          <div className="mt-1 text-sm leading-6 text-[#6b7068]">
            How the recommended plan differs from the alternatives.
          </div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[#6b7068]">
            {planDelta.comparisonAgainstAlternatives.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {selectedPlanComparison ? (
        <div className="mt-4 rounded-xl border border-[#e0ddd8] bg-white p-4">
          <div className="text-sm font-semibold text-[#1a3d2e]">
            Compared with the recommended plan
          </div>
          <div className="mt-1 text-sm leading-6 text-[#6b7068]">
            Tradeoffs of the plan you selected instead of the recommended one.
          </div>
          <div className="mt-2 text-sm leading-6 text-[#6b7068]">
            {selectedPlanComparison.summary}
          </div>
          {selectedPlanComparison.differences.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[#6b7068]">
              {selectedPlanComparison.differences.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {scenarioSimulation ? (
        <div
          data-testid="scenario-simulation-section"
          className={`mt-4 rounded-xl border p-4 ${
            highlightedActionType === "explore_scenario"
              ? "border-[#9db8a7] bg-[#eef7f1]"
              : "border-[#d8e6dd] bg-[#f6fbf7]"
          }`}
        >
          <div className="text-sm font-semibold text-[#1a3d2e]">
            What changes if your profile improves
          </div>
          <div className="mt-2 text-sm leading-6 text-[#6b7068]">
            {scenarioSimulation.changeSummary}
          </div>
          {scenarioSimulation.keyDifferences.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-[#6b7068]">
              {scenarioSimulation.keyDifferences.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {scenarioComparison && bestScenarioInsight ? (
        <div
          data-testid="scenario-comparison-section"
          className={`mt-4 rounded-xl border p-4 ${
            highlightedActionType === "explore_scenario"
              ? "border-[#9db8a7] bg-[#f6fbf7]"
              : "border-[#e0ddd8] bg-white"
          }`}
        >
          <div className="text-sm font-semibold text-[#1a3d2e]">
            Which improvement helps most
          </div>
          <div className="mt-1 text-sm leading-6 text-[#6b7068]">
            Among the tested scenarios, this one changes the outcome the most.
          </div>
          <div className="mt-2 text-sm leading-6 text-[#6b7068]">
            <span className="font-semibold text-[#1a1a1a]">{bestScenarioInsight.scenarioLabel}</span>{" "}
            {bestScenarioInsight.reason}
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead className="bg-[#f5f3ee] text-left text-[#6b7068]">
                <tr>
                  <th className="px-3 py-2 font-semibold">Scenario</th>
                  <th className="px-3 py-2 font-semibold">Result</th>
                  <th className="px-3 py-2 font-semibold">Key change</th>
                </tr>
              </thead>
              <tbody>
                {scenarioComparison.scenarios.map((scenario) => (
                  <tr key={scenario.scenarioKey} className="border-t border-[#e0ddd8]">
                    <td className="px-3 py-3 font-medium text-[#1a1a1a]">{scenario.scenarioLabel}</td>
                    <td className="px-3 py-3 text-[#6b7068]">{scenario.changeSummary}</td>
                    <td className="px-3 py-3 text-[#6b7068]">
                      {scenario.keyDifferences.slice(0, 2).join(" ") || "No major change."}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      {improvementPriority ? (
        <div
          data-testid="improvement-priority-section"
          className={`mt-4 rounded-xl border p-4 ${
            highlightedActionType === "improve_profile"
              ? "border-[#9db8a7] bg-[#eef7f1]"
              : "border-[#d8e6dd] bg-[#f6fbf7]"
          }`}
        >
          <div className="text-sm font-semibold text-[#1a3d2e]">
            Most worthwhile improvement
          </div>
          <div className="mt-1 text-sm leading-6 text-[#6b7068]">
            Best next improvement after balancing likely impact and effort.
          </div>
          <div className="mt-2 text-sm leading-6 text-[#6b7068]">
            <span className="font-semibold text-[#1a1a1a]">{improvementPriority.recommendedScenarioLabel}</span>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-white px-3 py-2 text-sm text-[#6b7068]">
              <span className="font-semibold text-[#1a1a1a]">Impact:</span> {improvementPriority.impactLevel}
            </div>
            <div className="rounded-lg bg-white px-3 py-2 text-sm text-[#6b7068]">
              <span className="font-semibold text-[#1a1a1a]">Effort:</span> {improvementPriority.effortLevel}
            </div>
            <div className="rounded-lg bg-white px-3 py-2 text-sm text-[#6b7068]">
              <span className="font-semibold text-[#1a1a1a]">Priority:</span> {improvementPriority.priorityTier}
            </div>
          </div>
          <div className="mt-3 text-sm leading-6 text-[#6b7068]">
            {improvementPriority.priorityReason}
          </div>
        </div>
      ) : null}
      {nextActionGuide ? (
        <div className="mt-4 rounded-xl border border-[#e0ddd8] bg-white p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-[#1a3d2e]">
              Suggested next step
            </div>
            {actionBadge ? (
              <div className="rounded-full bg-[#f5f3ee] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#315343]">
                {actionBadge}
              </div>
            ) : null}
          </div>
          {focusLabel ? (
            <div className="mt-1 text-sm leading-6 text-[#6b7068]">
              {focusLabel}
            </div>
          ) : null}
          <div className="mt-2 text-sm font-semibold leading-6 text-[#1a1a1a]">
            {nextActionGuide.suggestedNextAction}
          </div>
          <div className="mt-1 text-sm leading-6 text-[#6b7068]">
            {nextActionGuide.reason}
          </div>
          {onActivateTarget ? (
            <button
              type="button"
              onClick={() => onActivateTarget(nextActionGuide.suggestedTarget)}
              data-testid="next-action-button"
              className="mt-3 rounded-full border border-[#d2d9d4] bg-[#f6fbf7] px-4 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#315343] transition hover:border-[#1a3d2e] hover:text-[#1a3d2e]"
            >
              {buttonLabel}
            </button>
          ) : null}
          <div className="mt-2 text-sm leading-6 text-[#6b7068]">
            {helperText}
          </div>
        </div>
      ) : null}
      <div className="mt-4 overflow-x-auto">
        <div className="min-w-[760px]">
          <div className="grid grid-cols-[180px_repeat(3,minmax(0,1fr))] gap-px rounded-xl bg-[#e0ddd8]">
            <div className="bg-[#f5f3ee] px-4 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]" />
            {orderedPlans.map((plan) => {
              const recommended = planComparison?.recommendedPlan === plan.planName;
              return (
                <div
                  key={`header-${plan.planName}`}
                  data-testid={`plan-column-${plan.planName}`}
                  className={`px-4 py-3 text-sm font-semibold capitalize ${recommended ? "bg-[#f6fbf7] text-[#1a3d2e]" : "bg-white text-[#1a1a1a]"}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span>{plan.planName}</span>
                    {recommended ? (
                      <span className="rounded-full bg-[#dceee2] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[#315343]">
                        Recommended
                      </span>
                    ) : null}
                  </div>
                </div>
              );
            })}
            <MatrixRow
              label="Primary Choice"
              plans={orderedPlans}
              renderValue={(plan) => plan.primaryChoice?.universityName ?? ""}
            />
            <MatrixRow
              label="Plan Confidence"
              plans={orderedPlans}
              renderValue={(plan) => formatPlanConfidenceLabel(plan.planConfidence) ?? ""}
            />
            <MatrixRow
              label="Confidence Reason"
              plans={orderedPlans}
              renderValue={(plan) => plan.planConfidenceReason ?? ""}
              titleValue={(plan) => plan.planConfidenceReason ?? ""}
            />
            <MatrixRow
              label="Warnings"
              plans={orderedPlans}
              renderValue={(plan) =>
                plan.planWarnings && plan.planWarnings.length > 0
                  ? plan.planWarnings.join(" | ")
                  : "No major warning signals"
              }
              titleValue={(plan) =>
                plan.planWarnings && plan.planWarnings.length > 0
                  ? plan.planWarnings.join("\n")
                  : "No major warning signals"
              }
            />
            <MatrixRow
              label="Risk Distribution"
              plans={orderedPlans}
              renderValue={(plan) => plan.riskDistribution}
              titleValue={(plan) => plan.riskDistribution}
            />
            <MatrixRow
              label="Strategy Summary"
              plans={orderedPlans}
              renderValue={(plan) => truncatePlanText(plan.recommendedStrategy, 90) ?? ""}
              titleValue={(plan) => plan.recommendedStrategy}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function MatrixRow({
  label,
  plans,
  renderValue,
  titleValue,
}: {
  label: string;
  plans: ApplicationPlan[];
  renderValue: (plan: ApplicationPlan) => string;
  titleValue?: (plan: ApplicationPlan) => string;
}) {
  return (
    <>
      <div className="bg-[#f5f3ee] px-4 py-3 text-sm font-semibold text-[#1a3d2e]">{label}</div>
      {plans.map((plan) => {
        const value = renderValue(plan);
        const title = titleValue ? titleValue(plan) : value;
        return (
          <div
            key={`${label}-${plan.planName}`}
            className="bg-white px-4 py-3 text-sm leading-6 text-[#6b7068]"
            title={title || undefined}
          >
            {value || ""}
          </div>
        );
      })}
    </>
  );
}
