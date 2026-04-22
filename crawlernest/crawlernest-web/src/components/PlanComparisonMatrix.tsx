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

export function PlanComparisonMatrix({
  plans,
  planComparison,
}: {
  plans: ApplicationPlan[];
  planComparison?: PlanComparison;
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
