"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useEffect, useMemo, useState } from "react";

import { fetchAppJson } from "@/lib/api";
import { useAuth } from "@/hooks/useAuthPlaceholder";
import { AUTH_MESSAGES } from "@/lib/authMessages";
import { RC1_STANDARD_CAVEATS } from "@/lib/caveatMessages";
import { sourceAvailabilityConfig } from "@/lib/analyticsPresentation";
import { AdmissionSignalBadge } from "@/components/AdmissionSignalBadge";
import { PlanComparisonMatrix } from "@/components/PlanComparisonMatrix";
import {
  formatIelts,
  formatRank,
  formatScore,
} from "@/lib/format";

type PlanName = "balanced" | "conservative" | "aggressive";
type ScenarioKey =
  | "ielts_plus_0_5"
  | "toefl_plus_5"
  | "gpa_plus_0_2"
  | "target_rank_tighter_20";
type CurrentFocus = "plan" | "scenario" | "improvement";
type PersistedProfileDraft = {
  country?: string;
  ielts?: number | "";
  toefl?: number | "";
  gpa?: number | "";
  duolingo?: number | "";
  targetRank?: number | "";
};
type PersistedDecisionFlowState = {
  selectedPlan: PlanName | null;
  selectedScenarioKey: ScenarioKey | null;
  currentFocus: CurrentFocus | null;
  profileDraft: PersistedProfileDraft;
};

type ShortlistItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  slug: string;
};

type ComparisonItem = ShortlistItem & {
  ieltsMin?: number;
  matchingScore?: number;
};

type AdmissionResolvedField = {
  value: number | string | Record<string, string>;
  confidence: number;
  sourceCount: number;
  status: "accepted" | "needs_review" | "conflict" | "missing" | string;
};

type RecommendationItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  gpaRequirement?: number;
  ieltsMin: number;
  toeflRequirement?: number;
  duolingoRequirement?: number;
  matchingScore: number;
  recommendationConfidence: number;
  explanation: string;
  admissionComposite?: {
    admissionReadiness: "strong" | "moderate" | "weak" | "unknown";
    admissionRisk: "low" | "medium" | "high" | "unknown";
    topConcerns: string[];
    topConcernLabels?: string[];
    reason?: string;
  };
  decisionOutput?: {
    decisionAction:
      | "apply_early"
      | "apply"
      | "apply_with_caution"
      | "improve_profile_first"
      | "monitor"
      | "insufficient_data";
    decisionStrength: "strong" | "moderate" | "weak" | "unknown";
    decisionReason: string;
    recommendedNextSteps: string[];
  };
  decisionStrategy?: {
    primaryStrategy: string;
    supportingActions: string[];
    riskMitigation: string[];
    timelineHint: string;
    reason: string;
  };
  surfaceSignals?: Array<{
    type: "ielts" | "toefl" | "gpa" | "duolingo" | "deadline";
    message?: string;
    urgency?: "high" | "medium" | "low" | "unknown";
    priorityLevel?: number;
    priorityScore?: number;
    emphasized?: boolean;
  }>;
  admissionResolved?: Partial<
    Record<"ielts" | "toefl" | "gpa" | "duolingo" | "deadline", AdmissionResolvedField>
  >;
  admissionResolvedLines?: string[];
  toeflFitHighlight?: {
    requiredScore: number;
    userScore: number;
    margin: number;
    fitBand: "comfortably_above" | "meets_requirement" | "slightly_below" | "well_below" | "unknown";
    fitUrgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  gpaFitHighlight?: {
    requiredScore: number;
    userScore: number;
    margin: number;
    fitBand: "comfortably_above" | "meets_requirement" | "slightly_below" | "well_below" | "unknown";
    fitUrgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  duolingoFitHighlight?: {
    requiredScore: number;
    userScore: number;
    margin: number;
    fitBand: "comfortably_above" | "meets_requirement" | "slightly_below" | "well_below" | "unknown";
    fitUrgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  ieltsFitHighlight?: {
    requiredScore: number;
    userScore: number;
    margin: number;
    fitBand: "comfortably_above" | "meets_requirement" | "slightly_below" | "well_below" | "unknown";
    fitUrgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  deadlineHighlight?: {
    date: string;
    type: string;
    urgency: "high" | "medium" | "low" | "unknown";
    message: string;
    reason?: string;
  };
  recommendationExplain?: {
    fitScore: number;
    dimensions: {
      rankingFit: number;
      riskFit: number;
      languageFit: number;
      dataConfidence: number;
    };
    reasons: string[];
    warnings: string[];
  };
  subjectFit?: {
    subjectKey: string;
    subjectName: string;
    rankPosition?: number | null;
    rankDisplay?: string | null;
    score?: number | null;
    sourceCode?: string | null;
    signalScore: number;
    adjustment: number;
    hasData: boolean;
    reason: string;
  };
};

type RecommendationResponse = {
  success: boolean;
  applicationPlan?: {
    planName?: string;
    reach: Array<{
      universityName: string;
      decision?: string;
      strategy?: string;
      risk?: string;
      reason?: string;
    }>;
    target: Array<{
      universityName: string;
      decision?: string;
      strategy?: string;
      risk?: string;
      reason?: string;
    }>;
    safety: Array<{
      universityName: string;
      decision?: string;
      strategy?: string;
      risk?: string;
      reason?: string;
    }>;
    planSummary: string;
    riskDistribution: string;
    recommendedStrategy: string;
    primaryChoice?: {
      universityName: string;
      bucket: "reach" | "target" | "safety";
      reason: string;
    };
    planWarnings?: string[];
    planConfidence?: "high" | "medium" | "low";
    planConfidenceReason?: string;
  };
  applicationPlans?: Array<{
    planName: PlanName;
    reach: Array<{
      universityName: string;
      decision?: string;
      strategy?: string;
      risk?: string;
      reason?: string;
    }>;
    target: Array<{
      universityName: string;
      decision?: string;
      strategy?: string;
      risk?: string;
      reason?: string;
    }>;
    safety: Array<{
      universityName: string;
      decision?: string;
      strategy?: string;
      risk?: string;
      reason?: string;
    }>;
    planSummary: string;
    riskDistribution: string;
    recommendedStrategy: string;
    primaryChoice?: {
      universityName: string;
      bucket: "reach" | "target" | "safety";
      reason: string;
    };
    planWarnings?: string[];
    planConfidence?: "high" | "medium" | "low";
    planConfidenceReason?: string;
  }>;
  planComparison?: {
    recommendedPlan: PlanName;
    reason: string;
    tradeoffs: string[];
  };
  planDelta?: {
    recommendedPlan: PlanName;
    comparisonAgainstAlternatives: string[];
  };
  selectedPlanComparison?: {
    selectedPlan: PlanName;
    recommendedPlan: PlanName;
    summary: string;
    differences: string[];
  };
  scenarioSimulation?: {
    scenarioInput: {
      ielts_delta?: number;
      toefl_delta?: number;
      gpa_delta?: number;
      target_rank_delta?: number;
    };
    recommendedPlanBefore: PlanName;
    recommendedPlanAfter: PlanName;
    changeSummary: string;
    keyDifferences: string[];
  };
  scenarioComparison?: {
    baselineRecommendedPlan: PlanName;
    scenarios: Array<{
      scenarioKey: string;
      scenarioLabel: string;
      recommendedPlanAfter: PlanName;
      changeSummary: string;
      keyDifferences: string[];
    }>;
  };
  bestScenarioInsight?: {
    scenarioKey: string;
    scenarioLabel: string;
    reason: string;
  };
  improvementPriority?: {
    recommendedScenarioKey: string;
    recommendedScenarioLabel: string;
    priorityReason: string;
    effortLevel: "low" | "medium" | "high";
    impactLevel: "low" | "medium" | "high";
    priorityTier: "low" | "medium" | "high";
  };
  nextActionGuide?: {
    currentFocus: CurrentFocus;
    suggestedNextAction: string;
    actionType: "explore_scenario" | "focus_plan" | "improve_profile";
    reason: string;
    suggestedTarget: {
      type: "plan" | "scenario";
      key: string;
      label: string;
    };
  };
  decisionSummaryCompact?: {
    plan: string;
    confidence: string;
    risk: string;
    topReason: string;
    nextStep: string;
  };
  decisionSummary?: {
    generatedAt: string;
    profileSnapshot?: {
      country?: string;
      ielts?: number;
      toefl?: number;
      gpa?: number;
      duolingo?: number;
      targetRank?: number;
    };
    recommendedPlan?: {
      plan: PlanName;
      summary?: string;
      confidence?: string;
      confidenceReason?: string;
    };
    selectedPlan?: {
      plan: PlanName;
      summary?: string;
    };
    planComparison?: {
      summary?: string;
      differences?: string[];
    };
    topRecommendation?: {
      university?: string;
      decision?: string;
      reason?: string;
    };
    bestScenario?: {
      scenario: string;
      effect?: string;
    };
    improvementPriority?: {
      action?: string;
      impact?: string;
      effort?: string;
      reason?: string;
    };
    nextAction?: {
      type?: "plan" | "scenario" | "improvement";
      action?: string;
      reason?: string;
    };
  };
  data: {
    reach: RecommendationItem[];
    target: RecommendationItem[];
    safety: RecommendationItem[];
  };
  metadata?: {
    candidate_count?: number;
    counts?: {
      reach?: number;
      target?: number;
      safety?: number;
    };
  };
};

type NextActionTarget = {
  type: "plan" | "scenario";
  key: string;
  label: string;
};

const SHORTLIST_STORAGE_KEY = "crawlernest_shortlist";
const DECISION_FLOW_STORAGE_KEY = "crawlernest_recommendation_flow";
const DEFAULT_COUNTRY = "United Kingdom";
const DEFAULT_IELTS = 6.5;
const DEFAULT_TARGET_RANK = 100;
const SUBJECT_OPTIONS = [
  { subjectKey: "", subjectName: "Any subject" },
  { subjectKey: "computer-science", subjectName: "Computer Science" },
  { subjectKey: "electrical-engineering", subjectName: "Electrical Engineering" },
] as const;
const VALID_PLAN_NAMES: PlanName[] = ["balanced", "conservative", "aggressive"];
const VALID_SCENARIO_KEYS: ScenarioKey[] = [
  "ielts_plus_0_5",
  "toefl_plus_5",
  "gpa_plus_0_2",
  "target_rank_tighter_20",
];
type ScenarioTargetPayload = {
  ielts_delta?: number;
  toefl_delta?: number;
  gpa_delta?: number;
  target_rank_delta?: number;
};
const VALID_FOCUS_VALUES: CurrentFocus[] = ["plan", "scenario", "improvement"];
const SCENARIO_TARGETS: Record<ScenarioKey, ScenarioTargetPayload> = {
  ielts_plus_0_5: { ielts_delta: 0.5 },
  toefl_plus_5: { toefl_delta: 5 },
  gpa_plus_0_2: { gpa_delta: 0.2 },
  target_rank_tighter_20: { target_rank_delta: -20 },
};
const SCENARIO_LABEL_TO_KEY: Record<string, ScenarioKey> = {
  "IELTS +0.5": "ielts_plus_0_5",
  "TOEFL +5": "toefl_plus_5",
  "GPA +0.2": "gpa_plus_0_2",
  "Target rank -20": "target_rank_tighter_20",
};

function isPlanName(value: unknown): value is PlanName {
  return typeof value === "string" && VALID_PLAN_NAMES.includes(value as PlanName);
}

function isScenarioKey(value: unknown): value is ScenarioKey {
  return typeof value === "string" && VALID_SCENARIO_KEYS.includes(value as ScenarioKey);
}

function isCurrentFocus(value: unknown): value is CurrentFocus {
  return typeof value === "string" && VALID_FOCUS_VALUES.includes(value as CurrentFocus);
}

function parsePersistedNumber(
  value: unknown,
  {
    min,
    max,
  }: {
    min: number;
    max: number;
  }
) {
  if (value === "" || value === undefined || value === null) {
    return "";
  }

  if (typeof value !== "number" || !Number.isFinite(value)) {
    return undefined;
  }

  return Math.min(max, Math.max(min, value));
}

function sanitizePersistedDecisionFlowState(
  value: unknown
): PersistedDecisionFlowState | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const raw = value as {
    selectedPlan?: unknown;
    selectedScenarioKey?: unknown;
    currentFocus?: unknown;
    profileDraft?: Record<string, unknown>;
  };

  const profileDraft: PersistedProfileDraft = {};
  const rawProfileDraft =
    raw.profileDraft && typeof raw.profileDraft === "object" ? raw.profileDraft : null;

  if (rawProfileDraft) {
    if (typeof rawProfileDraft.country === "string" && rawProfileDraft.country.trim()) {
      profileDraft.country = rawProfileDraft.country.trim();
    }

    const ieltsValue = parsePersistedNumber(rawProfileDraft.ielts, { min: 0, max: 9 });
    if (ieltsValue !== undefined) {
      profileDraft.ielts = ieltsValue;
    }

    const toeflValue = parsePersistedNumber(rawProfileDraft.toefl, { min: 0, max: 120 });
    if (toeflValue !== undefined) {
      profileDraft.toefl = toeflValue;
    }

    const gpaValue = parsePersistedNumber(rawProfileDraft.gpa, { min: 0, max: 4.3 });
    if (gpaValue !== undefined) {
      profileDraft.gpa = gpaValue;
    }

    const duolingoValue = parsePersistedNumber(rawProfileDraft.duolingo, { min: 0, max: 160 });
    if (duolingoValue !== undefined) {
      profileDraft.duolingo = duolingoValue;
    }

    const targetRankValue = parsePersistedNumber(rawProfileDraft.targetRank, {
      min: 1,
      max: 5000,
    });
    if (targetRankValue !== undefined) {
      profileDraft.targetRank = targetRankValue;
    }
  }

  const selectedPlan = isPlanName(raw.selectedPlan) ? raw.selectedPlan : null;
  const selectedScenarioKey = isScenarioKey(raw.selectedScenarioKey) ? raw.selectedScenarioKey : null;
  const currentFocus = isCurrentFocus(raw.currentFocus) ? raw.currentFocus : null;
  const hasProfileDraft = Object.keys(profileDraft).length > 0;

  if (!selectedPlan && !selectedScenarioKey && !currentFocus && !hasProfileDraft) {
    return null;
  }

  return {
    selectedPlan,
    selectedScenarioKey,
    currentFocus,
    profileDraft,
  };
}

function hasPersistedDecisionFlowState(state: PersistedDecisionFlowState) {
  return Boolean(
    state.selectedPlan ||
      state.selectedScenarioKey ||
      state.currentFocus ||
      Object.keys(state.profileDraft).length > 0
  );
}

function buildPersistedProfileDraft(profileDraft: {
  country: string;
  ielts: number;
  toefl: number | "";
  gpa: number | "";
  duolingo: number | "";
  targetRank: number;
}): PersistedProfileDraft {
  const persistedDraft: PersistedProfileDraft = {};

  if (profileDraft.country !== DEFAULT_COUNTRY) {
    persistedDraft.country = profileDraft.country;
  }
  if (profileDraft.ielts !== DEFAULT_IELTS) {
    persistedDraft.ielts = profileDraft.ielts;
  }
  if (profileDraft.toefl !== "") {
    persistedDraft.toefl = profileDraft.toefl;
  }
  if (profileDraft.gpa !== "") {
    persistedDraft.gpa = profileDraft.gpa;
  }
  if (profileDraft.duolingo !== "") {
    persistedDraft.duolingo = profileDraft.duolingo;
  }
  if (profileDraft.targetRank !== DEFAULT_TARGET_RANK) {
    persistedDraft.targetRank = profileDraft.targetRank;
  }

  return persistedDraft;
}

function titleCaseWords(value: string) {
  return value
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatSummaryFieldLabel(key: string) {
  const labelMap: Record<string, string> = {
    country: "Country",
    ielts: "IELTS",
    toefl: "TOEFL",
    gpa: "GPA",
    duolingo: "Duolingo",
    targetRank: "Target Rank",
    plan: "Plan",
    confidence: "Confidence",
    decision: "Decision",
    scenario: "Scenario",
    effect: "Effect",
    action: "Action",
    impact: "Impact",
    effort: "Effort",
    reason: "Reason",
    university: "University",
    summary: "Summary",
  };
  return labelMap[key] ?? titleCaseWords(key);
}

function formatSummaryValue(key: string, value: number | string) {
  if (typeof value === "number") {
    return String(value);
  }

  if (key === "plan") {
    return titleCaseWords(value);
  }

  if (key === "confidence" || key === "impact" || key === "effort") {
    return titleCaseWords(value);
  }

  if (key === "decision") {
    const normalized = value.replaceAll("_", " ");
    return normalized.charAt(0).toUpperCase() + normalized.slice(1);
  }

  return value;
}

function pushSummarySection(
  sections: string[][],
  title: string,
  rows: Array<string | null | undefined>
) {
  const cleanRows = rows.filter((row): row is string => Boolean(row && row.trim()));
  if (cleanRows.length === 0) {
    return;
  }
  sections.push([title, ...cleanRows]);
}

function parseImportedSummaryNumber(
  value: unknown,
  { min, max }: { min: number; max: number }
) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return undefined;
  }
  return Math.min(max, Math.max(min, value));
}

function parseImportedDecisionSummary(
  rawText: string
): RecommendationResponse["decisionSummary"] | null {
  if (!rawText.trim()) {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawText);
  } catch {
    return null;
  }

  const candidate =
    parsed &&
    typeof parsed === "object" &&
    "decisionSummary" in (parsed as Record<string, unknown>) &&
    (parsed as { decisionSummary?: unknown }).decisionSummary &&
    typeof (parsed as { decisionSummary?: unknown }).decisionSummary === "object"
      ? (parsed as { decisionSummary?: RecommendationResponse["decisionSummary"] }).decisionSummary
      : parsed;

  if (!candidate || typeof candidate !== "object") {
    return null;
  }

  const raw = candidate as Record<string, unknown>;
  if (
    !raw.profileSnapshot &&
    !raw.recommendedPlan &&
    !raw.nextAction
  ) {
    return null;
  }

  const summary: NonNullable<RecommendationResponse["decisionSummary"]> = {
    generatedAt:
      typeof raw.generatedAt === "string" && raw.generatedAt ? raw.generatedAt : "",
    profileSnapshot: {},
    recommendedPlan: {
      plan: "balanced",
    },
  };

  const profileSnapshot =
    raw.profileSnapshot && typeof raw.profileSnapshot === "object"
      ? (raw.profileSnapshot as Record<string, unknown>)
      : null;
  if (profileSnapshot) {
    const normalizedProfile = summary.profileSnapshot ?? {};
    if (typeof profileSnapshot.country === "string" && profileSnapshot.country.trim()) {
      normalizedProfile.country = profileSnapshot.country.trim();
    }
    const ielts = parseImportedSummaryNumber(profileSnapshot.ielts, { min: 0, max: 9 });
    if (ielts !== undefined) {
      normalizedProfile.ielts = ielts;
    }
    const toefl = parseImportedSummaryNumber(profileSnapshot.toefl, { min: 0, max: 120 });
    if (toefl !== undefined) {
      normalizedProfile.toefl = toefl;
    }
    const gpa = parseImportedSummaryNumber(profileSnapshot.gpa, { min: 0, max: 4.3 });
    if (gpa !== undefined) {
      normalizedProfile.gpa = gpa;
    }
    const duolingo = parseImportedSummaryNumber(profileSnapshot.duolingo, { min: 0, max: 160 });
    if (duolingo !== undefined) {
      normalizedProfile.duolingo = duolingo;
    }
    const targetRank = parseImportedSummaryNumber(profileSnapshot.targetRank, {
      min: 1,
      max: 5000,
    });
    if (targetRank !== undefined) {
      normalizedProfile.targetRank = targetRank;
    }
    summary.profileSnapshot = normalizedProfile;
  }

  const recommendedPlan =
    raw.recommendedPlan && typeof raw.recommendedPlan === "object"
      ? (raw.recommendedPlan as Record<string, unknown>)
      : null;
  if (recommendedPlan && isPlanName(recommendedPlan.plan)) {
    summary.recommendedPlan = { plan: recommendedPlan.plan };
    if (typeof recommendedPlan.summary === "string" && recommendedPlan.summary) {
      summary.recommendedPlan.summary = recommendedPlan.summary;
    }
    if (typeof recommendedPlan.confidence === "string" && recommendedPlan.confidence) {
      summary.recommendedPlan.confidence = recommendedPlan.confidence;
    }
    if (
      typeof recommendedPlan.confidenceReason === "string" &&
      recommendedPlan.confidenceReason
    ) {
      summary.recommendedPlan.confidenceReason = recommendedPlan.confidenceReason;
    }
  } else if (raw.recommendedPlan) {
    delete summary.recommendedPlan;
  }

  const selectedPlan =
    raw.selectedPlan && typeof raw.selectedPlan === "object"
      ? (raw.selectedPlan as Record<string, unknown>)
      : null;
  if (selectedPlan && isPlanName(selectedPlan.plan)) {
    summary.selectedPlan = {
      plan: selectedPlan.plan,
      ...(typeof selectedPlan.summary === "string" && selectedPlan.summary
        ? { summary: selectedPlan.summary }
        : {}),
    };
  }

  const bestScenario =
    raw.bestScenario && typeof raw.bestScenario === "object"
      ? (raw.bestScenario as Record<string, unknown>)
      : null;
  if (bestScenario && typeof bestScenario.scenario === "string" && bestScenario.scenario) {
    summary.bestScenario = {
      scenario: bestScenario.scenario,
      ...(typeof bestScenario.effect === "string" && bestScenario.effect
        ? { effect: bestScenario.effect }
        : {}),
    };
  }

  const improvementPriority =
    raw.improvementPriority && typeof raw.improvementPriority === "object"
      ? (raw.improvementPriority as Record<string, unknown>)
      : null;
  if (improvementPriority) {
    const action =
      typeof improvementPriority.action === "string" && improvementPriority.action
        ? improvementPriority.action
        : undefined;
    const impact =
      typeof improvementPriority.impact === "string" && improvementPriority.impact
        ? improvementPriority.impact
        : undefined;
    const effort =
      typeof improvementPriority.effort === "string" && improvementPriority.effort
        ? improvementPriority.effort
        : undefined;
    const reason =
      typeof improvementPriority.reason === "string" && improvementPriority.reason
        ? improvementPriority.reason
        : undefined;
    if (action || impact || effort || reason) {
      summary.improvementPriority = {
        ...(action ? { action } : {}),
        ...(impact ? { impact } : {}),
        ...(effort ? { effort } : {}),
        ...(reason ? { reason } : {}),
      };
    }
  }

  const nextAction =
    raw.nextAction && typeof raw.nextAction === "object"
      ? (raw.nextAction as Record<string, unknown>)
      : null;
  if (nextAction) {
    const type =
      typeof nextAction.type === "string" &&
      ["plan", "scenario", "improvement"].includes(nextAction.type)
        ? (nextAction.type as "plan" | "scenario" | "improvement")
        : undefined;
    const action =
      typeof nextAction.action === "string" && nextAction.action ? nextAction.action : undefined;
    const reason =
      typeof nextAction.reason === "string" && nextAction.reason ? nextAction.reason : undefined;
    if (type || action || reason) {
      summary.nextAction = {
        ...(type ? { type } : {}),
        ...(action ? { action } : {}),
        ...(reason ? { reason } : {}),
      };
    }
  }

  if (
    !summary.profileSnapshot ||
    Object.keys(summary.profileSnapshot).length === 0
  ) {
    summary.profileSnapshot = {};
  }

  if (
    !summary.profileSnapshot ||
    Object.keys(summary.profileSnapshot).length === 0
  ) {
    delete summary.profileSnapshot;
  }
  if (!summary.recommendedPlan) {
    delete summary.recommendedPlan;
  }

  if (!summary.profileSnapshot && !summary.recommendedPlan && !summary.nextAction) {
    return null;
  }

  return summary;
}

function buildImportedSummaryPreview(
  decisionSummary: RecommendationResponse["decisionSummary"] | null | undefined
) {
  if (!decisionSummary) {
    return null;
  }

  const parts: string[] = [];
  const plan = decisionSummary.selectedPlan?.plan ?? decisionSummary.recommendedPlan?.plan;
  if (plan) {
    parts.push(`${titleCaseWords(plan)} plan`);
  }
  if (decisionSummary.profileSnapshot?.country) {
    parts.push(decisionSummary.profileSnapshot.country);
  }
  if (decisionSummary.profileSnapshot?.ielts !== undefined) {
    parts.push(`IELTS ${decisionSummary.profileSnapshot.ielts}`);
  }

  if (parts.length === 0) {
    return null;
  }

  return `Imported: ${parts.join(" / ")}`;
}

export function buildDecisionSummaryText(
  decisionSummary: RecommendationResponse["decisionSummary"] | null | undefined,
  decisionSummaryCompact?: RecommendationResponse["decisionSummaryCompact"] | null
) {
  if (!decisionSummary) {
    return "";
  }

  const sections: string[][] = [];
  if (decisionSummaryCompact) {
    pushSummarySection(sections, "Decision Snapshot", [
      decisionSummaryCompact.plan ? `- Plan: ${decisionSummaryCompact.plan}` : null,
      decisionSummaryCompact.confidence ? `- Confidence: ${decisionSummaryCompact.confidence}` : null,
      decisionSummaryCompact.risk ? `- Risk: ${decisionSummaryCompact.risk}` : null,
      decisionSummaryCompact.nextStep ? `- Next Step: ${decisionSummaryCompact.nextStep}` : null,
    ]);
  }
  sections.push(["Decision Summary"]);
  const profileEntries = Object.entries(decisionSummary.profileSnapshot ?? {}).filter(
    ([, value]) => value !== undefined && value !== null && value !== ""
  );
  if (profileEntries.length > 0) {
    pushSummarySection(
      sections,
      "Profile",
      profileEntries.map(
        ([key, value]) =>
          `- ${formatSummaryFieldLabel(key)}: ${formatSummaryValue(
            key,
            value as number | string
          )}`
      )
    );
  }

  if (decisionSummary.recommendedPlan) {
    pushSummarySection(sections, "Recommended Plan", [
      `- Plan: ${formatSummaryValue("plan", decisionSummary.recommendedPlan.plan)}`,
      decisionSummary.recommendedPlan.confidence
        ? `- Confidence: ${formatSummaryValue(
            "confidence",
            decisionSummary.recommendedPlan.confidence
          )}`
        : null,
      decisionSummary.recommendedPlan.summary
        ? `- Summary: ${decisionSummary.recommendedPlan.summary}`
        : null,
      decisionSummary.recommendedPlan.confidenceReason
        ? `- Reason: ${decisionSummary.recommendedPlan.confidenceReason}`
        : null,
    ]);
  }

  if (decisionSummary.selectedPlan) {
    pushSummarySection(sections, "Selected Plan", [
      `- Plan: ${formatSummaryValue("plan", decisionSummary.selectedPlan.plan)}`,
      decisionSummary.selectedPlan.summary
        ? `- Summary: ${decisionSummary.selectedPlan.summary}`
        : null,
    ]);
  }

  if (decisionSummary.planComparison) {
    pushSummarySection(sections, "Plan Comparison", [
      decisionSummary.planComparison.summary
        ? `- Summary: ${decisionSummary.planComparison.summary}`
        : null,
      ...(decisionSummary.planComparison.differences ?? []).map(
        (difference) => `- ${difference}`
      ),
    ]);
  }

  if (decisionSummary.topRecommendation) {
    pushSummarySection(sections, "Top Recommendation", [
      decisionSummary.topRecommendation.university
        ? `- University: ${decisionSummary.topRecommendation.university}`
        : null,
      decisionSummary.topRecommendation.decision
        ? `- Decision: ${formatSummaryValue(
            "decision",
            decisionSummary.topRecommendation.decision
          )}`
        : null,
      decisionSummary.topRecommendation.reason
        ? `- Reason: ${decisionSummary.topRecommendation.reason}`
        : null,
    ]);
  }

  if (decisionSummary.bestScenario) {
    pushSummarySection(sections, "Most Helpful Scenario", [
      `- Scenario: ${decisionSummary.bestScenario.scenario}`,
      decisionSummary.bestScenario.effect
        ? `- Effect: ${decisionSummary.bestScenario.effect}`
        : null,
    ]);
  }

  if (decisionSummary.improvementPriority) {
    pushSummarySection(sections, "Most Worthwhile Improvement", [
      decisionSummary.improvementPriority.action
        ? `- Action: ${decisionSummary.improvementPriority.action}`
        : null,
      decisionSummary.improvementPriority.impact
        ? `- Impact: ${formatSummaryValue(
            "impact",
            decisionSummary.improvementPriority.impact
          )}`
        : null,
      decisionSummary.improvementPriority.effort
        ? `- Effort: ${formatSummaryValue(
            "effort",
            decisionSummary.improvementPriority.effort
          )}`
        : null,
      decisionSummary.improvementPriority.reason
        ? `- Reason: ${decisionSummary.improvementPriority.reason}`
        : null,
    ]);
  }

  if (decisionSummary.nextAction) {
    pushSummarySection(sections, "Next Step", [
      decisionSummary.nextAction.action
        ? `- Action: ${decisionSummary.nextAction.action}`
        : null,
      decisionSummary.nextAction.reason
        ? `- Reason: ${decisionSummary.nextAction.reason}`
        : null,
    ]);
  }

  return sections.map((section) => section.join("\n")).join("\n\n").trim();
}

function formatConfidence(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }

  if (value <= 1) {
    return `${Math.round(value * 100)}%`;
  }

  return `${Math.round(value)}%`;
}

function resolvedFieldLabel(field: string) {
  const labels: Record<string, string> = {
    ielts: "IELTS",
    toefl: "TOEFL",
    gpa: "GPA",
    duolingo: "Duolingo",
    deadline: "Deadline",
  };
  return labels[field] ?? titleCaseWords(field);
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

export function RecommendationPageContent() {
  const [country, setCountry] = useState(DEFAULT_COUNTRY);
  const [ielts, setIelts] = useState(DEFAULT_IELTS);
  const [toefl, setToefl] = useState<number | "">("");
  const [gpa, setGpa] = useState<number | "">("");
  const [duolingo, setDuolingo] = useState<number | "">("");
  const [targetRank, setTargetRank] = useState(DEFAULT_TARGET_RANK);
  const [riskProfile, setRiskProfile] = useState("balanced");
  const [selectedSubject, setSelectedSubject] = useState("");
  const [scenarioIeltsDelta, setScenarioIeltsDelta] = useState<number | "">("");
  const [scenarioToeflDelta, setScenarioToeflDelta] = useState<number | "">("");
  const [scenarioGpaDelta, setScenarioGpaDelta] = useState<number | "">("");
  const [scenarioTargetRankDelta, setScenarioTargetRankDelta] = useState<number | "">("");

  const [data, setData] = useState<RecommendationResponse["data"] | null>(null);
  const [metadata, setMetadata] = useState<RecommendationResponse["metadata"] | null>(null);
  const [applicationPlan, setApplicationPlan] = useState<RecommendationResponse["applicationPlan"] | null>(null);
  const [applicationPlans, setApplicationPlans] = useState<RecommendationResponse["applicationPlans"] | null>(null);
  const [planComparison, setPlanComparison] = useState<RecommendationResponse["planComparison"] | null>(null);
  const [planDelta, setPlanDelta] = useState<RecommendationResponse["planDelta"] | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PlanName | null>(null);
  const [selectedScenarioKey, setSelectedScenarioKey] = useState<ScenarioKey | null>(null);
  const [currentFocus, setCurrentFocus] = useState<CurrentFocus | null>(null);
  const [selectedPlanComparison, setSelectedPlanComparison] = useState<RecommendationResponse["selectedPlanComparison"] | null>(null);
  const [scenarioSimulation, setScenarioSimulation] = useState<RecommendationResponse["scenarioSimulation"] | null>(null);
  const [scenarioComparison, setScenarioComparison] = useState<RecommendationResponse["scenarioComparison"] | null>(null);
  const [bestScenarioInsight, setBestScenarioInsight] = useState<RecommendationResponse["bestScenarioInsight"] | null>(null);
  const [improvementPriority, setImprovementPriority] = useState<RecommendationResponse["improvementPriority"] | null>(null);
  const [nextActionGuide, setNextActionGuide] = useState<RecommendationResponse["nextActionGuide"] | null>(null);
  const [decisionSummaryCompact, setDecisionSummaryCompact] = useState<RecommendationResponse["decisionSummaryCompact"] | null>(null);
  const [decisionSummary, setDecisionSummary] = useState<RecommendationResponse["decisionSummary"] | null>(null);
  const [persistenceReady, setPersistenceReady] = useState(false);
  const [showRestoredStateCue, setShowRestoredStateCue] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const [importSummaryText, setImportSummaryText] = useState("");
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [importExpanded, setImportExpanded] = useState(false);
  const [showImportedSummaryCue, setShowImportedSummaryCue] = useState(false);
  const [importedSummaryPreview, setImportedSummaryPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { authenticated, refresh: refreshAuth } = useAuth();
  const [lastResponse, setLastResponse] = useState<RecommendationResponse | null>(null);
  const [saveTitle, setSaveTitle] = useState("");
  const [savePhase, setSavePhase] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveErrorMsg, setSaveErrorMsg] = useState<string | null>(null);
  const [shortlistContext, setShortlistContext] = useState<ShortlistItem[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      const storedValue = window.localStorage.getItem(SHORTLIST_STORAGE_KEY);
      if (!storedValue) {
        setShortlistContext([]);
        return;
      }

      const parsedValue = JSON.parse(storedValue);
      if (!Array.isArray(parsedValue)) {
        setShortlistContext([]);
        return;
      }

      const shortlist = parsedValue.filter((item): item is ShortlistItem => {
        return (
          typeof item?.canonicalUniversityId === "number" &&
          typeof item?.universityName === "string" &&
          typeof item?.country === "string" &&
          typeof item?.aggregatedRank === "number" &&
          typeof item?.slug === "string"
        );
      });

      setShortlistContext(shortlist);
    } catch {
      setShortlistContext([]);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    let restoredState: PersistedDecisionFlowState | null = null;

    try {
      const storedValue = window.localStorage.getItem(DECISION_FLOW_STORAGE_KEY);
      restoredState = storedValue
        ? sanitizePersistedDecisionFlowState(JSON.parse(storedValue))
        : null;
    } catch {
      restoredState = null;
    }

    if (!restoredState) {
      setPersistenceReady(true);
      return;
    }

    if (restoredState.profileDraft.country) {
      setCountry(restoredState.profileDraft.country);
    }
    if (restoredState.profileDraft.ielts !== undefined && restoredState.profileDraft.ielts !== "") {
      setIelts(restoredState.profileDraft.ielts);
    }
    if (restoredState.profileDraft.toefl !== undefined) {
      setToefl(restoredState.profileDraft.toefl);
    }
    if (restoredState.profileDraft.gpa !== undefined) {
      setGpa(restoredState.profileDraft.gpa);
    }
    if (restoredState.profileDraft.duolingo !== undefined) {
      setDuolingo(restoredState.profileDraft.duolingo);
    }
    if (
      restoredState.profileDraft.targetRank !== undefined &&
      restoredState.profileDraft.targetRank !== ""
    ) {
      setTargetRank(restoredState.profileDraft.targetRank);
    }
    if (restoredState.selectedPlan) {
      setSelectedPlan(restoredState.selectedPlan);
    }
    if (restoredState.selectedScenarioKey) {
      setSelectedScenarioKey(restoredState.selectedScenarioKey);
      const payload = SCENARIO_TARGETS[restoredState.selectedScenarioKey];
      setScenarioIeltsDelta(payload.ielts_delta ?? "");
      setScenarioToeflDelta(payload.toefl_delta ?? "");
      setScenarioGpaDelta(payload.gpa_delta ?? "");
      setScenarioTargetRankDelta(payload.target_rank_delta ?? "");
    }
    if (restoredState.currentFocus) {
      setCurrentFocus(restoredState.currentFocus);
    }

    setShowRestoredStateCue(true);
    setPersistenceReady(true);
    void fetchRecommendations(
      restoredState.selectedPlan ?? null,
      restoredState.selectedScenarioKey
        ? SCENARIO_TARGETS[restoredState.selectedScenarioKey]
        : null,
      restoredState.profileDraft
    );
  }, []);

  useEffect(() => {
    if (!persistenceReady || typeof window === "undefined") {
      return;
    }

    const stateToPersist: PersistedDecisionFlowState = {
      selectedPlan,
      selectedScenarioKey,
      currentFocus,
      profileDraft: buildPersistedProfileDraft({
        country,
        ielts,
        toefl,
        gpa,
        duolingo,
        targetRank,
      }),
    };

    try {
      if (hasPersistedDecisionFlowState(stateToPersist)) {
        window.localStorage.setItem(
          DECISION_FLOW_STORAGE_KEY,
          JSON.stringify(stateToPersist)
        );
      } else {
        window.localStorage.removeItem(DECISION_FLOW_STORAGE_KEY);
      }
    } catch {
      // Ignore storage write failures so the page stays usable.
    }
  }, [
    country,
    currentFocus,
    duolingo,
    gpa,
    ielts,
    persistenceReady,
    selectedPlan,
    selectedScenarioKey,
    targetRank,
    toefl,
  ]);

  const totalCount = useMemo(() => {
    if (metadata?.candidate_count !== undefined) {
      return metadata.candidate_count;
    }

    if (!data) {
      return 0;
    }

    return data.reach.length + data.target.length + data.safety.length;
  }, [data, metadata]);

  const recommendationLookup = useMemo(() => {
    const lookup = new Map<number, RecommendationItem>();
    if (!data) {
      return lookup;
    }

    [...data.reach, ...data.target, ...data.safety].forEach((item) => {
      if (!lookup.has(item.canonicalUniversityId)) {
        lookup.set(item.canonicalUniversityId, item);
      }
    });

    return lookup;
  }, [data]);

  const comparisonItems = useMemo<ComparisonItem[]>(() => {
    return shortlistContext.map((item) => {
      const recommendation = recommendationLookup.get(item.canonicalUniversityId);
      return {
        ...item,
        ieltsMin: recommendation?.ieltsMin,
        matchingScore: recommendation?.matchingScore,
      };
    });
  }, [recommendationLookup, shortlistContext]);

  const bestRank = useMemo(() => {
    if (comparisonItems.length === 0) {
      return null;
    }
    return Math.min(...comparisonItems.map((item) => item.aggregatedRank));
  }, [comparisonItems]);

  const bestIelts = useMemo(() => {
    const values = comparisonItems
      .map((item) => item.ieltsMin)
      .filter((value): value is number => value !== undefined);

    if (values.length === 0) {
      return null;
    }

    return Math.min(...values);
  }, [comparisonItems]);

  const bestMatchScore = useMemo(() => {
    const values = comparisonItems
      .map((item) => item.matchingScore)
      .filter((value): value is number => value !== undefined);

    if (values.length === 0) {
      return null;
    }

    return Math.max(...values);
  }, [comparisonItems]);

  const comparisonExplanations = useMemo(() => {
    if (comparisonItems.length < 2) {
      return [] as string[];
    }

    const sortedByRank = [...comparisonItems].sort(
      (a, b) => a.aggregatedRank - b.aggregatedRank
    );
    const bestRanked = sortedByRank[0];
    const secondBestRanked = sortedByRank[1];

    const explanations: string[] = [];

    if (bestRanked && secondBestRanked) {
      explanations.push(
        `${bestRanked.universityName} has the strongest global rank in your shortlist, ahead of ${secondBestRanked.universityName}.`
      );
    }

    const ieltsComparable = comparisonItems.filter(
      (item): item is ComparisonItem & { ieltsMin: number } =>
        item.ieltsMin !== undefined
    );
    if (ieltsComparable.length >= 2) {
      const sortedByIelts = [...ieltsComparable].sort(
        (a, b) => a.ieltsMin - b.ieltsMin
      );
      explanations.push(
        `${sortedByIelts[0].universityName} has the lowest IELTS requirement in this comparison, which may offer a more accessible language threshold.`
      );
    }

    const matchComparable = comparisonItems.filter(
      (item): item is ComparisonItem & { matchingScore: number } =>
        item.matchingScore !== undefined
    );
    if (matchComparable.length >= 2) {
      const sortedByMatch = [...matchComparable].sort(
        (a, b) => b.matchingScore - a.matchingScore
      );
      explanations.push(
        `${sortedByMatch[0].universityName} currently shows the strongest recommendation fit based on match score.`
      );
    }

    return explanations;
  }, [comparisonItems]);

  const scenarioPayload = useMemo(() => {
    const payload: {
      ielts_delta?: number;
      toefl_delta?: number;
      gpa_delta?: number;
      target_rank_delta?: number;
    } = {};

    if (scenarioIeltsDelta !== "" && scenarioIeltsDelta !== 0) {
      payload.ielts_delta = scenarioIeltsDelta;
    }
    if (scenarioToeflDelta !== "" && scenarioToeflDelta !== 0) {
      payload.toefl_delta = scenarioToeflDelta;
    }
    if (scenarioGpaDelta !== "" && scenarioGpaDelta !== 0) {
      payload.gpa_delta = scenarioGpaDelta;
    }
    if (scenarioTargetRankDelta !== "" && scenarioTargetRankDelta !== 0) {
      payload.target_rank_delta = scenarioTargetRankDelta;
    }

    return Object.keys(payload).length > 0 ? payload : null;
  }, [scenarioGpaDelta, scenarioIeltsDelta, scenarioTargetRankDelta, scenarioToeflDelta]);

  async function fetchRecommendations(
    selectedPlanOverride: PlanName | null = selectedPlan,
    scenarioPayloadOverride: {
      ielts_delta?: number;
      toefl_delta?: number;
      gpa_delta?: number;
      target_rank_delta?: number;
    } | null = scenarioPayload,
    profileDraftOverride?: PersistedProfileDraft
  ) {
    setLoading(true);
    setError(null);

    try {
      const effectiveCountry = profileDraftOverride?.country ?? country;
      const effectiveIelts =
        profileDraftOverride?.ielts !== undefined && profileDraftOverride.ielts !== ""
          ? profileDraftOverride.ielts
          : ielts;
      const effectiveToefl =
        profileDraftOverride?.toefl !== undefined ? profileDraftOverride.toefl : toefl;
      const effectiveGpa =
        profileDraftOverride?.gpa !== undefined ? profileDraftOverride.gpa : gpa;
      const effectiveDuolingo =
        profileDraftOverride?.duolingo !== undefined
          ? profileDraftOverride.duolingo
          : duolingo;
      const effectiveTargetRank =
        profileDraftOverride?.targetRank !== undefined &&
        profileDraftOverride.targetRank !== ""
          ? profileDraftOverride.targetRank
          : targetRank;
      const params = new URLSearchParams({
        targetRank: String(effectiveTargetRank),
        ieltsScore: String(effectiveIelts),
        country: effectiveCountry,
        riskProfile,
        countryPolicy: "hard_filter",
        limit: "5",
        version: "v3",
      });
      if (selectedPlanOverride) {
        params.set("selectedPlan", selectedPlanOverride);
      }
      if (scenarioPayloadOverride) {
        params.set("scenario", JSON.stringify(scenarioPayloadOverride));
      }
      if (effectiveToefl !== "") {
        params.set("toeflScore", String(effectiveToefl));
      }
      if (effectiveGpa !== "") {
        params.set("gpaScore", String(effectiveGpa));
      }
      if (effectiveDuolingo !== "") {
        params.set("duolingoScore", String(effectiveDuolingo));
      }
      if (selectedSubject) {
        params.set("subject", selectedSubject);
      }

      const json = await fetchAppJson<RecommendationResponse>(
        `/api/recommendations?${params.toString()}`
      );

      if (!json.success) {
        throw new Error("Recommendation request did not succeed.");
      }

      setLastResponse(json);
      setSavePhase("idle");
      setSaveTitle("");
      setData(json.data);
      setMetadata(json.metadata ?? null);
      setApplicationPlan(json.applicationPlan ?? null);
      setApplicationPlans(json.applicationPlans ?? null);
      setPlanComparison(json.planComparison ?? null);
      setPlanDelta(json.planDelta ?? null);
      setSelectedPlanComparison(json.selectedPlanComparison ?? null);
      setScenarioSimulation(json.scenarioSimulation ?? null);
      setScenarioComparison(json.scenarioComparison ?? null);
      setBestScenarioInsight(json.bestScenarioInsight ?? null);
      setImprovementPriority(json.improvementPriority ?? null);
      setNextActionGuide(json.nextActionGuide ?? null);
      setDecisionSummaryCompact(json.decisionSummaryCompact ?? null);
      setDecisionSummary(json.decisionSummary ?? null);
      setCurrentFocus(json.nextActionGuide?.currentFocus ?? currentFocus);
    } catch {
      setError("Unable to load recommendations. Please confirm the API server is running.");
      setData(null);
      setMetadata(null);
      setApplicationPlan(null);
      setApplicationPlans(null);
      setPlanComparison(null);
      setPlanDelta(null);
      setSelectedPlanComparison(null);
      setScenarioSimulation(null);
      setScenarioComparison(null);
      setBestScenarioInsight(null);
      setImprovementPriority(null);
      setNextActionGuide(null);
      setDecisionSummaryCompact(null);
      setDecisionSummary(null);
    } finally {
      setLoading(false);
    }
  }

  function clearImportedSummaryFeedback() {
    setShowImportedSummaryCue(false);
    setImportedSummaryPreview(null);
    setImportStatus((current) =>
      current === "Restored decision summary." ? null : current
    );
  }

  async function handleGenerateRecommendations() {
    clearImportedSummaryFeedback();
    await fetchRecommendations();
  }

  async function handlePlanSelection(planName: PlanName) {
    clearImportedSummaryFeedback();
    setSelectedPlan(planName);
    setCurrentFocus("plan");
    await fetchRecommendations(planName);
  }

  async function handleActivateTarget(target: NextActionTarget) {
    if (!target) {
      return;
    }
    clearImportedSummaryFeedback();
    if (target.type === "plan" && isPlanName(target.key)) {
      setSelectedPlan(target.key);
      setCurrentFocus("plan");
      await fetchRecommendations(target.key);
      return;
    }
    if (target.type === "scenario") {
      const scenarioKey = target.key as keyof typeof SCENARIO_TARGETS;
      const payload = SCENARIO_TARGETS[scenarioKey];
      if (!payload) {
        return;
      }
      setSelectedScenarioKey(scenarioKey);
      setScenarioIeltsDelta(payload.ielts_delta ?? "");
      setScenarioToeflDelta(payload.toefl_delta ?? "");
      setScenarioGpaDelta(payload.gpa_delta ?? "");
      setScenarioTargetRankDelta(payload.target_rank_delta ?? "");
      setCurrentFocus(
        nextActionGuide?.actionType === "improve_profile" ? "improvement" : "scenario"
      );
      await fetchRecommendations(selectedPlan, payload);
    }
  }

  async function handleResetExploration() {
    clearImportedSummaryFeedback();
    setCountry(DEFAULT_COUNTRY);
    setIelts(DEFAULT_IELTS);
    setToefl("");
    setGpa("");
    setDuolingo("");
    setTargetRank(DEFAULT_TARGET_RANK);
    setSelectedSubject("");
    setSelectedPlan(null);
    setSelectedScenarioKey(null);
    setCurrentFocus(null);
    setScenarioIeltsDelta("");
    setScenarioToeflDelta("");
    setScenarioGpaDelta("");
    setScenarioTargetRankDelta("");
    setImportSummaryText("");
    setImportExpanded(false);
    setImportStatus(null);
    setShowRestoredStateCue(false);

    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(DECISION_FLOW_STORAGE_KEY);
      } catch {
        // Ignore storage failures during reset.
      }
    }

    if (data || applicationPlans || planComparison) {
      await fetchRecommendations(null, null, {
        country: DEFAULT_COUNTRY,
        ielts: DEFAULT_IELTS,
        toefl: "",
        gpa: "",
        duolingo: "",
        targetRank: DEFAULT_TARGET_RANK,
      });
    }
  }

  async function handleCopyDecisionSummaryJson() {
    if (!decisionSummary || !navigator?.clipboard?.writeText) {
      setExportStatus("Could not copy summary.");
      return;
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(decisionSummary, null, 2));
      setExportStatus("Copied JSON summary.");
    } catch {
      setExportStatus("Could not copy summary.");
    }
  }

  async function handleCopyDecisionSummaryText() {
    if (!decisionSummary || !navigator?.clipboard?.writeText) {
      setExportStatus("Could not copy summary.");
      return;
    }
    try {
      await navigator.clipboard.writeText(buildDecisionSummaryText(decisionSummary, decisionSummaryCompact));
      setExportStatus("Copied text summary.");
    } catch {
      setExportStatus("Could not copy summary.");
    }
  }

  async function handleRestoreFromSummary() {
    setImportStatus(null);
    const importedSummary = parseImportedDecisionSummary(importSummaryText);
    if (!importedSummary) {
      setImportExpanded(true);
      setImportStatus("Could not restore summary.");
      return;
    }

    const importedProfile = importedSummary.profileSnapshot ?? {};
    const restoredCountry =
      typeof importedProfile.country === "string" && importedProfile.country
        ? importedProfile.country
        : country;
    const restoredIelts =
      typeof importedProfile.ielts === "number" ? importedProfile.ielts : ielts;
    const restoredToefl =
      typeof importedProfile.toefl === "number" ? importedProfile.toefl : "";
    const restoredGpa =
      typeof importedProfile.gpa === "number" ? importedProfile.gpa : "";
    const restoredDuolingo =
      typeof importedProfile.duolingo === "number" ? importedProfile.duolingo : "";
    const restoredTargetRank =
      typeof importedProfile.targetRank === "number"
        ? importedProfile.targetRank
        : targetRank;

    const restoredSelectedPlan = importedSummary.selectedPlan?.plan;
    const restoredScenarioKey =
      importedSummary.bestScenario?.scenario &&
      SCENARIO_LABEL_TO_KEY[importedSummary.bestScenario.scenario]
        ? SCENARIO_LABEL_TO_KEY[importedSummary.bestScenario.scenario]
        : null;

    let restoredFocus: CurrentFocus = "plan";
    if (restoredSelectedPlan && isPlanName(restoredSelectedPlan)) {
      restoredFocus = "plan";
    } else if (restoredScenarioKey) {
      restoredFocus = "scenario";
    } else if (
      importedSummary.improvementPriority ||
      importedSummary.nextAction?.type === "improvement"
    ) {
      restoredFocus = "improvement";
    }

    setCountry(restoredCountry);
    setIelts(restoredIelts);
    setToefl(restoredToefl);
    setGpa(restoredGpa);
    setDuolingo(restoredDuolingo);
    setTargetRank(restoredTargetRank);

    if (restoredSelectedPlan && isPlanName(restoredSelectedPlan)) {
      setSelectedPlan(restoredSelectedPlan);
    } else {
      setSelectedPlan(null);
    }

    if (restoredScenarioKey) {
      const payload = SCENARIO_TARGETS[restoredScenarioKey];
      setSelectedScenarioKey(restoredScenarioKey);
      setScenarioIeltsDelta(payload.ielts_delta ?? "");
      setScenarioToeflDelta(payload.toefl_delta ?? "");
      setScenarioGpaDelta(payload.gpa_delta ?? "");
      setScenarioTargetRankDelta(payload.target_rank_delta ?? "");
    } else {
      setSelectedScenarioKey(null);
      setScenarioIeltsDelta("");
      setScenarioToeflDelta("");
      setScenarioGpaDelta("");
      setScenarioTargetRankDelta("");
    }

    setCurrentFocus(restoredFocus);
    setShowRestoredStateCue(false);
    setImportStatus("Restored decision summary.");
    setShowImportedSummaryCue(true);
    setImportedSummaryPreview(buildImportedSummaryPreview(importedSummary));
    setImportSummaryText("");
    setImportExpanded(false);

    await fetchRecommendations(
      restoredSelectedPlan && isPlanName(restoredSelectedPlan) ? restoredSelectedPlan : null,
      restoredScenarioKey ? SCENARIO_TARGETS[restoredScenarioKey] : null,
      {
        country: restoredCountry,
        ielts: restoredIelts,
        toefl: restoredToefl,
        gpa: restoredGpa,
        duolingo: restoredDuolingo,
        targetRank: restoredTargetRank,
      }
    );
    setCurrentFocus(restoredFocus);
  }

  const autoTitle = useMemo(() => {
    const parts: string[] = [country, `IELTS ${ielts}`, `Rank #${targetRank}`];
    if (riskProfile && riskProfile !== "balanced") {
      parts.push(titleCaseWords(riskProfile));
    }
    return parts.join(", ");
  }, [country, ielts, targetRank, riskProfile]);

  async function handleSavePlan() {
    if (!lastResponse) return;
    setSavePhase("saving");
    setSaveErrorMsg(null);
    const effectiveTitle = saveTitle.trim() || autoTitle;
    try {
      const requestPayload = {
        country,
        ielts,
        toefl: toefl !== "" ? toefl : null,
        gpa: gpa !== "" ? gpa : null,
        duolingo: duolingo !== "" ? duolingo : null,
        targetRank,
        riskProfile,
        subject: selectedSubject || null,
        selectedPlan: selectedPlan || null,
      };
      const res = await fetch("/api/user/saved-recommendations", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: effectiveTitle,
          request: requestPayload,
          result: lastResponse,
        }),
      });
      if (res.ok) {
        setSavePhase("saved");
      } else if (res.status === 401) {
        setSaveErrorMsg("Your session has expired. Please sign in again.");
        setSavePhase("error");
        void refreshAuth();
      } else {
        setSaveErrorMsg("Could not save. Please try again.");
        setSavePhase("error");
      }
    } catch {
      setSaveErrorMsg("Could not connect. Please check your connection.");
      setSavePhase("error");
    }
  }

  return (
    <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-[#6b7068]">
              Decision Support
            </p>
            <h1 className="mt-2 text-4xl font-bold tracking-tight text-[#1a3d2e]">
              Recommendation Engine
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#6b7068]">
              Generate a shortlist using ranking targets, English requirements,
              and risk profile.
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex items-center rounded-full border border-[#e0ddd8] bg-white px-4 py-2 text-sm font-medium text-[#1a3d2e] shadow-sm transition hover:border-[#3d7a5a] hover:bg-[#e8f2ec]"
          >
            Back to rankings
          </Link>
        </div>

        {shortlistContext.length > 0 ? (
          <section className="mb-6 rounded-3xl border border-[#e0ddd8] bg-[#e8f2ec] p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-[#1a3d2e]">
              Using your shortlist ({shortlistContext.length})
            </h2>
            <p className="mt-2 text-sm text-[#6b7068]">
              These shortlisted universities are carried into your recommendation workflow.
            </p>
            <ul className="mt-4 space-y-2">
              {shortlistContext.map((item, index) => (
                <li
                  key={`${item.canonicalUniversityId}-${item.slug}-${index}`}
                  className="rounded-2xl border border-[#3d7a5a] bg-white px-4 py-3 text-sm font-medium text-[#1a3d2e]"
                >
                  {item.universityName}
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <section className="mb-6 rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-[#1a3d2e]">
              No shortlist detected. Start from rankings.
            </h2>
            <p className="mt-2 text-sm text-[#6b7068]">
              Add universities to your shortlist on the rankings page, then return here to continue.
            </p>
            <Link
              href="/"
              className="mt-4 inline-flex items-center justify-center rounded-full bg-[#1a3d2e] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
            >
              Back to rankings
            </Link>
          </section>
        )}

        {comparisonItems.length >= 2 ? (
          <section
            id="comparison"
            className="mb-6 rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm"
          >
            <h2 className="text-xl font-semibold text-[#1a3d2e]">Comparison</h2>
            <p className="mt-2 text-sm text-[#6b7068]">
              Compare shortlisted universities side by side before generating a final recommendation.
            </p>

            <div className="mt-5 overflow-x-auto">
              <table className="w-full border-collapse">
                <thead className="bg-[#f5f3ee] text-sm text-[#6b7068]">
                  <tr>
                    <th className="px-4 py-3 text-left">University</th>
                    <th className="px-4 py-3 text-left">Country</th>
                    <th className="px-4 py-3 text-left">Rank</th>
                    <th className="px-4 py-3 text-left">IELTS Min</th>
                    <th className="px-4 py-3 text-left">Matching Score</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonItems.map((item, index) => (
                    <tr
                      key={`${item.canonicalUniversityId}-${item.slug}-${index}`}
                      className="border-t border-[#e0ddd8]"
                    >
                      <td className="px-4 py-4 font-semibold text-[#1a1a1a]">
                        {item.universityName}
                      </td>
                      <td className="px-4 py-4 text-[#6b7068]">{item.country}</td>
                      <td
                        className={`px-4 py-4 ${
                          bestRank !== null && item.aggregatedRank === bestRank
                            ? "font-semibold text-[#1a3d2e]"
                            : "text-[#6b7068]"
                        }`}
                      >
                        #{formatRank(item.aggregatedRank)}
                      </td>
                      <td
                        className={`px-4 py-4 ${
                          bestIelts !== null && item.ieltsMin === bestIelts
                            ? "font-semibold text-[#1a3d2e]"
                            : "text-[#6b7068]"
                        }`}
                      >
                        {item.ieltsMin !== undefined
                          ? formatIelts(item.ieltsMin)
                          : "Not available"}
                      </td>
                      <td
                        className={`px-4 py-4 ${
                          bestMatchScore !== null &&
                          item.matchingScore === bestMatchScore
                            ? "font-semibold text-[#1a3d2e]"
                            : "text-[#6b7068]"
                        }`}
                      >
                        {item.matchingScore !== undefined
                          ? formatScore(item.matchingScore)
                          : "Not available"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {comparisonExplanations.length > 0 ? (
              <div className="mt-6 rounded-2xl bg-[#f5f3ee] p-5">
                <h3 className="text-base font-semibold text-[#1a3d2e]">
                  Explanation
                </h3>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-[#6b7068]">
                  {comparisonExplanations.map((explanation) => (
                    <li key={explanation}>{explanation}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Country</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="Country"
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">IELTS Score</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                step="0.5"
                value={ielts}
                onChange={(e) => setIelts(Number(e.target.value))}
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Target Rank</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                value={targetRank}
                onChange={(e) => setTargetRank(Number(e.target.value))}
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Risk Profile</span>
              <select
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                value={riskProfile}
                onChange={(e) => setRiskProfile(e.target.value)}
              >
                <option value="conservative">conservative</option>
                <option value="balanced">balanced</option>
                <option value="aggressive">aggressive</option>
              </select>
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Subject Focus (optional)</span>
              <select
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                value={selectedSubject}
                onChange={(e) => setSelectedSubject(e.target.value)}
              >
                {SUBJECT_OPTIONS.map((item) => (
                  <option key={item.subjectKey || "any"} value={item.subjectKey}>
                    {item.subjectName}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">TOEFL Score (optional)</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                value={toefl}
                onChange={(e) => setToefl(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 100"
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">GPA (optional)</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                step="0.1"
                value={gpa}
                onChange={(e) => setGpa(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 3.5"
              />
            </label>

            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium text-[#1a3d2e]">Duolingo Score (optional)</span>
              <input
                className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                type="number"
                value={duolingo}
                onChange={(e) => setDuolingo(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 120"
              />
            </label>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              onClick={() => void handleGenerateRecommendations()}
              className="inline-flex items-center justify-center rounded-full bg-[#1a3d2e] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42] disabled:cursor-not-allowed disabled:bg-[#c0bdb8]"
              disabled={loading}
            >
              {loading ? "Generating..." : "Generate Recommendations"}
            </button>
            <span className="text-sm text-[#6b7068]">
              Results are fetched through the frontend recommendation service.
            </span>
            <button
              type="button"
              onClick={() => void handleResetExploration()}
              className="inline-flex items-center justify-center rounded-full border border-[#d2d9d4] bg-white px-4 py-3 text-sm font-semibold text-[#315343] transition hover:border-[#1a3d2e] hover:text-[#1a3d2e]"
            >
              Reset exploration
            </button>
          </div>
          <div className="mt-2 text-sm text-[#6b7068]">
            Clears restored/imported exploration state from this browser.
          </div>
          {showRestoredStateCue ? (
            <div
              data-testid="restored-state-cue"
              className="mt-3 rounded-2xl border border-[#d8e6dd] bg-[#f6fbf7] px-4 py-3 text-sm text-[#315343]"
            >
              Restored your last comparison state.
            </div>
          ) : null}

          <div className="mt-6 rounded-2xl border border-[#e0ddd8] bg-[#fcfbf8] p-4">
            <div className="text-sm font-semibold text-[#1a3d2e]">
              Scenario Simulation
            </div>
            <p className="mt-2 text-sm text-[#6b7068]">
              Re-run the same pipeline with a small profile change to see what shifts.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <label className="flex flex-col gap-2">
                <span className="text-sm font-medium text-[#1a3d2e]">IELTS Delta</span>
                <input
                  className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                  type="number"
                  step="0.5"
                  value={scenarioIeltsDelta}
                  onChange={(e) => {
                    clearImportedSummaryFeedback();
                    setSelectedScenarioKey(null);
                    setCurrentFocus("scenario");
                    setScenarioIeltsDelta(e.target.value === "" ? "" : Number(e.target.value));
                  }}
                  placeholder="+0.5"
                />
              </label>
              <label className="flex flex-col gap-2">
                <span className="text-sm font-medium text-[#1a3d2e]">TOEFL Delta</span>
                <input
                  className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                  type="number"
                  value={scenarioToeflDelta}
                  onChange={(e) => {
                    clearImportedSummaryFeedback();
                    setSelectedScenarioKey(null);
                    setCurrentFocus("scenario");
                    setScenarioToeflDelta(e.target.value === "" ? "" : Number(e.target.value));
                  }}
                  placeholder="+5"
                />
              </label>
              <label className="flex flex-col gap-2">
                <span className="text-sm font-medium text-[#1a3d2e]">GPA Delta</span>
                <input
                  className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                  type="number"
                  step="0.1"
                  value={scenarioGpaDelta}
                  onChange={(e) => {
                    clearImportedSummaryFeedback();
                    setSelectedScenarioKey(null);
                    setCurrentFocus("scenario");
                    setScenarioGpaDelta(e.target.value === "" ? "" : Number(e.target.value));
                  }}
                  placeholder="+0.2"
                />
              </label>
              <label className="flex flex-col gap-2">
                <span className="text-sm font-medium text-[#1a3d2e]">Target Rank Delta</span>
                <input
                  className="rounded-xl border border-[#e0ddd8] px-4 py-3 outline-none transition focus:border-[#1a3d2e]"
                  type="number"
                  value={scenarioTargetRankDelta}
                  onChange={(e) => {
                    clearImportedSummaryFeedback();
                    setSelectedScenarioKey(null);
                    setCurrentFocus("scenario");
                    setScenarioTargetRankDelta(e.target.value === "" ? "" : Number(e.target.value));
                  }}
                  placeholder="-20"
                />
              </label>
            </div>
          </div>
        </section>

        <section className="mt-6 rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
          <button
            type="button"
            data-testid="import-summary-toggle"
            onClick={() => setImportExpanded((current) => !current)}
            className="flex w-full items-center justify-between gap-3 text-left"
          >
            <h2 className="text-xl font-semibold text-[#1a3d2e]">
              Import a decision summary
            </h2>
            <span className="text-sm font-medium text-[#6b7068]">
              {importExpanded || importSummaryText ? "Hide" : "Show"}
            </span>
          </button>
          <p className="mt-2 text-sm text-[#6b7068]">
            Paste a previously exported JSON summary to restore the same decision context.
          </p>
          <div className="mt-2 text-sm text-[#6b7068]">
            JSON summaries only. Text summaries are not supported.
          </div>
          {showImportedSummaryCue ? (
            <div
              data-testid="imported-summary-active-cue"
              className="mt-3 rounded-2xl border border-[#d8e6dd] bg-[#f6fbf7] px-4 py-3 text-sm text-[#315343]"
            >
              Imported summary is now active.
            </div>
          ) : null}
          {importedSummaryPreview ? (
            <div
              data-testid="imported-summary-preview"
              className="mt-2 text-sm text-[#6b7068]"
            >
              {importedSummaryPreview}
            </div>
          ) : null}
          {importExpanded || importSummaryText ? (
            <>
              <textarea
                data-testid="import-summary-textarea"
                className="mt-4 min-h-[180px] w-full rounded-2xl border border-[#e0ddd8] px-4 py-3 font-mono text-sm outline-none transition focus:border-[#1a3d2e]"
                value={importSummaryText}
                onChange={(e) => {
                  setImportExpanded(true);
                  setImportSummaryText(e.target.value);
                }}
                placeholder="Paste exported decision summary JSON here..."
              />
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  data-testid="restore-summary-button"
                  onClick={() => void handleRestoreFromSummary()}
                  className="inline-flex items-center justify-center rounded-full bg-[#1a3d2e] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
                >
                  Restore from summary
                </button>
                <button
                  type="button"
                  data-testid="clear-imported-summary-button"
                  onClick={() => {
                    setImportSummaryText("");
                    setImportStatus(null);
                    setImportExpanded(false);
                  }}
                  className="inline-flex items-center justify-center rounded-full border border-[#d2d9d4] bg-white px-4 py-3 text-sm font-semibold text-[#315343] transition hover:border-[#1a3d2e] hover:text-[#1a3d2e]"
                >
                  Clear imported text
                </button>
              </div>
            </>
          ) : null}
          {importStatus ? (
            <div
              data-testid="import-summary-status"
              className="mt-3 text-sm text-[#6b7068]"
            >
              {importStatus}
            </div>
          ) : null}
        </section>

        {error ? (
          <div className="mt-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
            {error}
          </div>
        ) : null}

        {data ? (
          <div className="mt-8 space-y-8">
            {decisionSummary ? (
              <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold text-[#1a3d2e]">
                  Export your decision summary
                </h2>
                <p className="mt-2 text-sm text-[#6b7068]">
                  Copy your current decision state so you can save or share it.
                </p>
                <div className="mt-5 flex flex-wrap gap-3">
                  <button
                    type="button"
                    data-testid="copy-summary-json"
                    onClick={() => void handleCopyDecisionSummaryJson()}
                    className="inline-flex items-center justify-center rounded-full bg-[#1a3d2e] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
                  >
                    Copy summary (JSON)
                  </button>
                  <button
                    type="button"
                    data-testid="copy-summary-text"
                    onClick={() => void handleCopyDecisionSummaryText()}
                    className="inline-flex items-center justify-center rounded-full border border-[#d2d9d4] bg-white px-4 py-3 text-sm font-semibold text-[#315343] transition hover:border-[#1a3d2e] hover:text-[#1a3d2e]"
                  >
                    Copy summary (text)
                  </button>
                </div>
                {exportStatus ? (
                  <div
                    data-testid="copy-summary-status"
                    className="mt-3 text-sm text-[#6b7068]"
                  >
                    {exportStatus}
                  </div>
                ) : null}
              </section>
            ) : null}
            <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-[#1a3d2e]">Summary</h2>
              <p className="mt-2 text-sm text-[#6b7068]">
                A compact view of the assumptions and the current recommendation spread.
              </p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <SummaryItem label="Country" value={country} />
                <SummaryItem label="IELTS Score" value={formatIelts(ielts)} />
                <SummaryItem label="Target Rank" value={`#${formatRank(targetRank)}`} />
                <SummaryItem label="Risk Profile" value={riskProfile} />
                <SummaryItem
                  label="Subject Focus"
                  value={
                    SUBJECT_OPTIONS.find((item) => item.subjectKey === selectedSubject)
                      ?.subjectName ?? "Any subject"
                  }
                />
                <SummaryItem label="Candidates" value={String(totalCount)} />
                <SummaryItem
                  label="Reach"
                  value={String(metadata?.counts?.reach ?? data.reach.length)}
                />
                <SummaryItem
                  label="Target"
                  value={String(metadata?.counts?.target ?? data.target.length)}
                />
                <SummaryItem
                  label="Safety"
                  value={String(metadata?.counts?.safety ?? data.safety.length)}
                />
              </div>
            </section>

            <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-[#1a3d2e]">Save This Plan</h2>
              <p className="mt-2 text-sm text-[#6b7068]">
                Save a snapshot of this recommendation result to your account.
              </p>
              <div className="mt-5">
                {!authenticated ? (
                  <p className="text-sm text-[#6b7068]">
                    <Link
                      href="/signin"
                      className="font-medium text-[#3d7a5a] underline-offset-4 hover:underline"
                    >
                      Sign in
                    </Link>
                    {" "}to save plans across sessions.
                  </p>
                ) : savePhase === "saved" ? (
                  <div className="flex flex-wrap items-center gap-4">
                    <span className="text-sm font-semibold text-[#1a3d2e]">Saved ✓</span>
                    <Link
                      href="/saved-recommendations"
                      className="text-sm font-medium text-[#3d7a5a] underline-offset-4 hover:underline"
                    >
                      View saved plans →
                    </Link>
                    <button
                      type="button"
                      onClick={() => setSavePhase("idle")}
                      className="text-xs text-[#6b7068] underline-offset-4 hover:underline"
                    >
                      Save again
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="flex-1 min-w-[220px]">
                      <label className="block text-sm font-medium text-[#1a3d2e] mb-1.5">
                        Plan title
                      </label>
                      <input
                        type="text"
                        value={saveTitle}
                        onChange={(e) => setSaveTitle(e.target.value)}
                        placeholder={autoTitle}
                        disabled={savePhase === "saving"}
                        className="w-full rounded-xl border border-[#e0ddd8] px-4 py-2.5 text-sm text-[#1a1a1a] placeholder-[#aaa] outline-none transition focus:border-[#1a3d2e] disabled:opacity-50"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleSavePlan()}
                      disabled={savePhase === "saving"}
                      className="rounded-full bg-[#1a3d2e] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#2a5a42] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {savePhase === "saving" ? AUTH_MESSAGES.saving : "Save plan"}
                    </button>
                    {savePhase === "error" && saveErrorMsg && (
                      <p className="w-full text-xs text-red-600">
                        {saveErrorMsg}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </section>

            {applicationPlans && applicationPlans.length > 0 ? (
              <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold text-[#1a3d2e]">Application Plans</h2>
                <p className="mt-2 text-sm text-[#6b7068]">
                  Three deterministic plan variants so we can compare balance, safety, and upside from the same recommendation set.
                </p>
                {decisionSummaryCompact ? (
                  <div className="mt-5 rounded-2xl border border-[#d8e6dd] bg-[#f6fbf7] p-4">
                    <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-[#1a3d2e]">
                      <span>{decisionSummaryCompact.plan} Plan</span>
                      <span className="text-[#9aa59d]">|</span>
                      <span>{decisionSummaryCompact.confidence} Confidence</span>
                      <span className="text-[#9aa59d]">|</span>
                      <span>Next: {decisionSummaryCompact.nextStep}</span>
                    </div>
                    <div className="mt-2 text-sm text-[#4b5b53]">
                      {decisionSummaryCompact.topReason}
                    </div>
                  </div>
                ) : null}
                {planComparison ? (
                  <div className="mt-5 rounded-2xl border border-[#d8e6dd] bg-[#f6fbf7] p-4 text-sm leading-6 text-[#315343]">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
                      Recommended Plan
                    </div>
                    <div className="mt-2 font-semibold capitalize text-[#1a1a1a]">
                      {planComparison.recommendedPlan}
                    </div>
                    <div className="mt-1 text-sm text-[#4b5b53]">
                      Best current plan based on your present profile.
                    </div>
                    <div className="mt-2">{planComparison.reason}</div>
                    {planComparison.tradeoffs.length > 0 ? (
                      <div className="mt-3 space-y-1 text-[#4b5b53]">
                        {planComparison.tradeoffs.slice(0, 2).map((tradeoff) => (
                          <div key={tradeoff}>{tradeoff}</div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <PlanComparisonMatrix
                  plans={applicationPlans}
                  planComparison={planComparison ?? undefined}
                  planDelta={planDelta ?? undefined}
                  selectedPlanComparison={selectedPlanComparison ?? undefined}
                  scenarioSimulation={scenarioSimulation ?? undefined}
                  scenarioComparison={scenarioComparison ?? undefined}
                  bestScenarioInsight={bestScenarioInsight ?? undefined}
                  improvementPriority={improvementPriority ?? undefined}
                  nextActionGuide={nextActionGuide ?? undefined}
                  onActivateTarget={handleActivateTarget}
                />
                <div className="mt-5 grid gap-4 xl:grid-cols-3">
                  {applicationPlans.map((plan) => (
                    <div
                      key={plan.planName}
                      data-testid={`plan-card-${plan.planName}`}
                      className={`rounded-2xl border p-5 transition ${
                        nextActionGuide?.actionType === "focus_plan" &&
                        nextActionGuide?.suggestedTarget?.type === "plan" &&
                        nextActionGuide?.suggestedTarget?.key === plan.planName
                          ? "border-[#1a3d2e] bg-[#eef7f1]"
                          : selectedPlan === plan.planName
                            ? "border-[#1a3d2e] bg-[#f2f7f4]"
                            : planComparison?.recommendedPlan === plan.planName
                              ? "border-[#9db8a7] bg-[#f6fbf7]"
                              : "border-[#e0ddd8] bg-[#fcfbf8]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#6b7068]">
                            Plan
                          </div>
                          <div className="mt-1 text-lg font-semibold capitalize text-[#1a3d2e]">
                            {plan.planName}
                          </div>
                        </div>
                        {planComparison?.recommendedPlan === plan.planName ? (
                          <div className="rounded-full bg-[#dceee2] px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-[#315343]">
                            Recommended
                          </div>
                        ) : null}
                      </div>
                      <div className="mt-4 flex items-center justify-between gap-3">
                        {selectedPlan === plan.planName ? (
                          <div className="rounded-full bg-[#1a3d2e] px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-white">
                            Selected
                          </div>
                        ) : (
                          <div className="text-xs font-medium uppercase tracking-[0.12em] text-[#6b7068]">
                            Select a plan to compare
                          </div>
                        )}
                        <button
                          type="button"
                          onClick={() => void handlePlanSelection(plan.planName)}
                          className="rounded-full border border-[#d2d9d4] bg-white px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-[#315343] transition hover:border-[#1a3d2e] hover:text-[#1a3d2e]"
                        >
                          {selectedPlan === plan.planName ? "Refresh focus" : "Focus this plan"}
                        </button>
                      </div>
                      <div className="mt-4 grid gap-3">
                        <ApplicationPlanGroup title="Reach" icon="🔥" items={plan.reach} compact />
                        <ApplicationPlanGroup title="Target" icon="🎯" items={plan.target} compact />
                        <ApplicationPlanGroup title="Safety" icon="🛡" items={plan.safety} compact />
                      </div>
                      <div className="mt-4 rounded-xl bg-white/70 p-4 text-sm leading-6 text-[#6b7068]">
                        <div>{plan.planSummary}</div>
                        <div className="mt-2">{plan.riskDistribution}</div>
                        <div className="mt-2" title={plan.recommendedStrategy}>
                          {truncatePlanText(plan.recommendedStrategy, 120)}
                        </div>
                        {plan.primaryChoice ? (
                          <div className="mt-3">
                            <span className="font-semibold text-[#1a1a1a]">Primary choice:</span>{" "}
                            {plan.primaryChoice.universityName}
                          </div>
                        ) : null}
                        {plan.planConfidence ? (
                          <div className="mt-2">
                            <span className="font-semibold text-[#1a1a1a]">Plan confidence:</span>{" "}
                            <span>{plan.planConfidence.charAt(0).toUpperCase() + plan.planConfidence.slice(1)}</span>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : applicationPlan ? (
              <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
                <h2 className="text-xl font-semibold text-[#1a3d2e]">Application Plan</h2>
                <p className="mt-2 text-sm text-[#6b7068]">
                  A structured view of reach, target, and safety options for execution planning.
                </p>
                <div className="mt-5 grid gap-4 lg:grid-cols-3">
                  <ApplicationPlanGroup title="Reach" icon="🔥" items={applicationPlan.reach} />
                  <ApplicationPlanGroup title="Target" icon="🎯" items={applicationPlan.target} />
                  <ApplicationPlanGroup title="Safety" icon="🛡" items={applicationPlan.safety} />
                </div>
                <div className="mt-5 grid gap-4 lg:grid-cols-2">
                  <div className="rounded-xl bg-[#f5f3ee] p-4 text-sm leading-6 text-[#6b7068]">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
                      Summary
                    </div>
                    <div className="mt-2">{applicationPlan.planSummary}</div>
                    <div className="mt-2">{applicationPlan.riskDistribution}</div>
                  </div>
                  <div className="rounded-xl bg-[#fcfbf8] p-4 text-sm leading-6 text-[#6b7068]">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
                      Strategy
                    </div>
                    <div className="mt-2">{applicationPlan.recommendedStrategy}</div>
                  </div>
                </div>
                {applicationPlan.primaryChoice || applicationPlan.planConfidence || (applicationPlan.planWarnings && applicationPlan.planWarnings.length > 0) ? (
                  <div className="mt-5 grid gap-4 lg:grid-cols-3">
                    {applicationPlan.primaryChoice ? (
                      <div className="rounded-xl bg-[#fcfbf8] p-4 text-sm leading-6 text-[#6b7068]">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
                          Primary Choice
                        </div>
                        <div className="mt-2 font-semibold text-[#1a1a1a]">
                          {applicationPlan.primaryChoice.universityName}
                        </div>
                        <div className="mt-1 capitalize">{applicationPlan.primaryChoice.bucket}</div>
                        <div className="mt-2">{applicationPlan.primaryChoice.reason}</div>
                      </div>
                    ) : null}
                    {applicationPlan.planConfidence ? (
                      <div className="rounded-xl bg-[#f5f3ee] p-4 text-sm leading-6 text-[#6b7068]">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
                          Plan Confidence
                        </div>
                        <div className="mt-2 font-semibold capitalize text-[#1a1a1a]">
                          {applicationPlan.planConfidence}
                        </div>
                        {applicationPlan.planConfidenceReason ? (
                          <div className="mt-2">{applicationPlan.planConfidenceReason}</div>
                        ) : null}
                      </div>
                    ) : null}
                    {applicationPlan.planWarnings ? (
                      <div className="rounded-xl bg-[#fff7ef] p-4 text-sm leading-6 text-[#6b7068]">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#8a6116]">
                          Warnings
                        </div>
                        {applicationPlan.planWarnings.length > 0 ? (
                          <div className="mt-2 space-y-1">
                            {applicationPlan.planWarnings.map((warning) => (
                              <div key={warning}>- {warning}</div>
                            ))}
                          </div>
                        ) : (
                          <div className="mt-2">No major warning signals in the current plan.</div>
                        )}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </section>
            ) : null}

            <Section
              title="Reach"
              description="Ambitious options with stronger ranking upside relative to your target."
              items={data.reach}
            />
            <Section
              title="Target"
              description="Balanced options with realistic fit and solid positioning."
              items={data.target}
            />
            <Section
              title="Safety"
              description="Lower-risk options that may be more accessible for your profile."
              items={data.safety}
            />
          </div>
        ) : null}
      </div>
    </main>
  );
}

function fitLevel(score: number | null | undefined) {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return "low";
  }
  if (score >= 80) {
    return "high";
  }
  if (score >= 60) {
    return "medium";
  }
  return "low";
}

export default function RecommendationPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
          <div className="mx-auto max-w-5xl px-6 py-10">
            <div className="rounded-2xl border border-[#e0ddd8] bg-white p-6 text-[#6b7068]">
              Loading recommendation context...
            </div>
          </div>
        </main>
      }
    >
      <RecommendationPageContent />
    </Suspense>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-[#f5f3ee] px-4 py-3">
      <div className="text-sm text-[#6b7068]">{label}</div>
      <div className="mt-1 font-medium text-[#1a1a1a]">{value}</div>
    </div>
  );
}

type ExplainState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; caveats: string[]; sourceCoverage: Record<string, boolean>; confidenceReason: string }
  | { status: "error" };

function ExplainPanel({ item }: { item: RecommendationItem }) {
  const [open, setOpen] = useState(false);
  const [explainState, setExplainState] = useState<ExplainState>({ status: "idle" });

  function toggle() {
    if (!open && explainState.status === "idle") {
      setExplainState({ status: "loading" });
      const url = `/api/recommendations/explain?canonicalUniversityId=${item.canonicalUniversityId}`;
      fetch(url, { cache: "no-store" })
        .then(async (res) => {
          const json = (await res.json()) as {
            success?: boolean;
            data?: {
              source_coverage?: {
                qs_available?: boolean;
                the_available?: boolean;
                arwu_available?: boolean;
              };
              confidence_evidence?: { confidence_reason?: string };
              caveats?: string[];
            };
          };
          if (res.ok && json.data) {
            const sc = json.data.source_coverage ?? {};
            setExplainState({
              status: "ok",
              sourceCoverage: {
                QS: sc.qs_available ?? false,
                THE: sc.the_available ?? false,
                ARWU: sc.arwu_available ?? false,
              },
              confidenceReason: json.data.confidence_evidence?.confidence_reason ?? "",
              caveats: json.data.caveats ?? RC1_STANDARD_CAVEATS,
            });
          } else {
            setExplainState({ status: "error" });
          }
        })
        .catch(() => setExplainState({ status: "error" }));
    }
    setOpen((prev) => !prev);
  }

  const explain = item.recommendationExplain;

  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center justify-between rounded-xl border border-[#d8e6dd] bg-[#f6fbf7] px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e] transition hover:bg-[#edf6f0]"
      >
        <span>Why this recommendation?</span>
        <span className="text-[#6b7068]">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="mt-1 rounded-xl border border-[#e0ddd8] bg-white p-4">
          {explain ? (
            <>
              {explain.reasons.length > 0 && (
                <>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                    Evidence Chain
                  </div>
                  <div className="space-y-1.5 text-sm text-[#415046]">
                    {explain.reasons.map((r) => (
                      <div key={r}>✓ {r}</div>
                    ))}
                  </div>
                </>
              )}

              {explain.warnings.length > 0 && (
                <div className="mt-3 space-y-1.5 text-sm text-[#6b554f]">
                  {explain.warnings.map((w) => (
                    <div key={w}>⚠ {w}</div>
                  ))}
                </div>
              )}

              <div className="mt-4 border-t border-[#e8e4de] pt-4 grid gap-3 sm:grid-cols-4">
                <SummaryItem label="Ranking Fit" value={formatScore(explain.dimensions.rankingFit)} />
                <SummaryItem label="Risk Fit" value={formatScore(explain.dimensions.riskFit)} />
                <SummaryItem label="Language Fit" value={formatScore(explain.dimensions.languageFit)} />
                <SummaryItem label="Data Confidence" value={formatScore(explain.dimensions.dataConfidence)} />
              </div>

              <div className="mt-4 border-t border-[#e8e4de] pt-4">
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className="font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                    Data Confidence
                  </span>
                  <span className="font-semibold tabular-nums text-[#415046]">
                    {Math.round(explain.dimensions.dataConfidence)}%
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[#f5f3ee]">
                  <div
                    className="h-2 rounded-full bg-[#1a3d2e]"
                    style={{
                      width: `${Math.min(100, Math.max(0, explain.dimensions.dataConfidence))}%`,
                    }}
                  />
                </div>
                <p className="mt-1.5 text-xs text-[#6b7068]">
                  Derived from source coverage and data completeness.{" "}
                  <span className="font-medium text-[#415046]">Not AI-generated.</span>
                </p>
              </div>
            </>
          ) : null}

          {/* Source evidence — loaded from explain endpoint */}
          {explainState.status === "loading" && (
            <div className="mt-4 h-10 animate-pulse rounded bg-slate-100" />
          )}
          {explainState.status === "ok" && (
            <>
              <div className="mt-4 border-t border-[#e8e4de] pt-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                  Source Coverage
                </div>
                <div className="flex flex-wrap gap-2">
                  {(["QS", "THE", "ARWU"] as const).map((src) => {
                    const cfg = sourceAvailabilityConfig(explainState.sourceCoverage[src]);
                    return (
                      <span
                        key={src}
                        className={`rounded border px-2 py-0.5 text-xs font-semibold ${cfg.badgeCls}`}
                      >
                        {src} {cfg.icon} {cfg.statusLabel}
                      </span>
                    );
                  })}
                </div>
                {explainState.confidenceReason && (
                  <p className="mt-2 text-xs text-[#6b7068]">{explainState.confidenceReason}</p>
                )}
              </div>

              <div className="mt-4">
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#8b3a2b]">
                  Data Caveats
                </div>
                <ul className="space-y-1">
                  {explainState.caveats.map((c, i) => (
                    <li key={i} className="text-xs text-[#6b554f]">
                      · {c}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
          {explainState.status === "error" && (
            <div className="mt-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-[#8b3a2b]">
                Data Caveats
              </div>
              <ul className="space-y-1">
                {RC1_STANDARD_CAVEATS.map((c, i) => (
                  <li key={i} className="text-xs text-[#6b554f]">
                    · {c}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ApplicationPlanGroup({
  title,
  icon,
  items,
  compact = false,
}: {
  title: string;
  icon: string;
  items: Array<{
    universityName: string;
    decision?: string;
    strategy?: string;
    risk?: string;
    reason?: string;
  }>;
  compact?: boolean;
}) {
  return (
    <div className={`rounded-2xl border border-[#e0ddd8] ${compact ? "bg-white/80 p-3" : "bg-[#fcfbf8] p-4"}`}>
      <div className="text-sm font-semibold text-[#1a3d2e]">
        {icon} {title}
      </div>
      {items.length === 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">No options in this group.</div>
      ) : (
        <div className={`mt-3 ${compact ? "space-y-2" : "space-y-3"}`}>
          {items.map((item) => (
            <div key={`${title}-${item.universityName}`} className={`rounded-xl bg-white ${compact ? "p-2.5" : "p-3"}`}>
              <div className="font-semibold text-[#1a1a1a]">{item.universityName}</div>
              {item.decision ? (
                <div className="mt-1 text-sm capitalize text-[#6b7068]">
                  Decision: {item.decision.replace(/_/g, " ")}
                </div>
              ) : null}
              {item.strategy ? (
                <div className="mt-1 text-sm text-[#6b7068]">{item.strategy}</div>
              ) : null}
              {item.risk ? (
                <div className="mt-1 text-sm capitalize text-[#6b7068]">Risk: {item.risk}</div>
              ) : null}
              {item.reason ? (
                <div className="mt-2 text-sm leading-6 text-[#6b7068]">{item.reason}</div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AdmissionCompositeCard({
  composite,
}: {
  composite?: RecommendationItem["admissionComposite"];
}) {
  if (!composite) {
    return null;
  }

  const readinessTone =
    composite.admissionReadiness === "strong"
      ? "text-[#1a3d2e]"
      : composite.admissionReadiness === "moderate"
        ? "text-[#8a6116]"
        : composite.admissionReadiness === "weak"
          ? "text-[#8b3a2b]"
          : "text-[#6b7068]";

  const riskTone =
    composite.admissionRisk === "low"
      ? "text-[#1a3d2e]"
      : composite.admissionRisk === "medium"
        ? "text-[#8a6116]"
        : composite.admissionRisk === "high"
          ? "text-[#8b3a2b]"
          : "text-[#6b7068]";

  return (
    <div
      className="rounded-xl border border-[#e0ddd8] bg-[#fcfbf8] p-4"
      title={composite.reason || ""}
    >
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
        Admission Readiness
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <div className="text-xs text-[#6b7068]">Readiness</div>
          <div className={`mt-1 font-semibold capitalize ${readinessTone}`}>
            {composite.admissionReadiness}
          </div>
        </div>
        <div>
          <div className="text-xs text-[#6b7068]">Risk</div>
          <div className={`mt-1 font-semibold capitalize ${riskTone}`}>
            {composite.admissionRisk}
          </div>
        </div>
      </div>
      {(composite.topConcernLabels?.length || composite.topConcerns.length) > 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">
          Top concerns: {(composite.topConcernLabels && composite.topConcernLabels.length > 0
            ? composite.topConcernLabels
            : composite.topConcerns
          ).join(", ")}
        </div>
      ) : null}
    </div>
  );
}

function DecisionOutputCard({
  decision,
}: {
  decision?: RecommendationItem["decisionOutput"];
}) {
  if (!decision) {
    return null;
  }

  const strengthTone =
    decision.decisionStrength === "strong"
      ? "text-[#1a3d2e]"
      : decision.decisionStrength === "moderate"
        ? "text-[#8a6116]"
        : decision.decisionStrength === "weak"
          ? "text-[#8b3a2b]"
          : "text-[#6b7068]";

  const actionLabel = decision.decisionAction.replace(/_/g, " ");

  return (
    <div className="rounded-xl border border-[#e0ddd8] bg-[#fffdf8] p-4">
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
        Suggested Action
      </div>
      <div className="mt-3 text-sm text-[#6b7068]">Action</div>
      <div className="mt-1 font-semibold capitalize text-[#1a1a1a]">{actionLabel}</div>
      <div className="mt-3 text-sm text-[#6b7068]">Confidence</div>
      <div className={`mt-1 font-semibold capitalize ${strengthTone}`}>
        {decision.decisionStrength}
      </div>
      <div className="mt-3 text-sm leading-6 text-[#6b7068]">{decision.decisionReason}</div>
      {decision.recommendedNextSteps.length > 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">
          {decision.recommendedNextSteps.slice(0, 3).map((step) => (
            <div key={step}>- {step}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function DecisionStrategyCard({
  strategy,
}: {
  strategy?: RecommendationItem["decisionStrategy"];
}) {
  if (!strategy) {
    return null;
  }

  return (
    <div
      className="rounded-xl border border-[#e0ddd8] bg-[#fcfbf8] p-4"
      title={strategy.reason}
    >
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
        Application Strategy
      </div>
      <div className="mt-3 text-sm text-[#6b7068]">Primary</div>
      <div className="mt-1 font-semibold text-[#1a1a1a]">{strategy.primaryStrategy}</div>
      {strategy.supportingActions.length > 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">
          <div className="mb-1">Actions</div>
          {strategy.supportingActions.slice(0, 3).map((step) => (
            <div key={step}>• {step}</div>
          ))}
        </div>
      ) : null}
      {strategy.riskMitigation.length > 0 ? (
        <div className="mt-3 text-sm text-[#6b7068]">
          <div className="mb-1">Risk Mitigation</div>
          {strategy.riskMitigation.slice(0, 3).map((step) => (
            <div key={step}>• {step}</div>
          ))}
        </div>
      ) : null}
      <div className="mt-3 text-sm text-[#6b7068]">Timeline</div>
      <div className="mt-1 text-sm leading-6 text-[#6b7068]">{strategy.timelineHint}</div>
    </div>
  );
}

function DeadlineBadge({
  highlight,
  className,
}: {
  highlight?: RecommendationItem["deadlineHighlight"];
  className?: string;
}) {
  if (!highlight) {
    return null;
  }

  const urgencyStyle =
    highlight.urgency === "high"
      ? {
          icon: "🔴",
          tone: "border-[#f1c5bc] bg-[#fbefeb] text-[#8b3a2b]",
        }
      : highlight.urgency === "medium"
        ? {
            icon: "🟡",
            tone: "border-[#ead9a7] bg-[#fbf5e4] text-[#8a6116]",
          }
        : highlight.urgency === "low"
          ? {
              icon: "🟢",
              tone: "border-[#cfe5d7] bg-[#edf7f1] text-[#1a3d2e]",
            }
          : {
              icon: "⚪",
              tone: "border-[#d7d5d0] bg-[#f5f3ee] text-[#6b7068]",
            };

  const typeLabel =
    highlight.type && highlight.type !== "unknown"
      ? `${highlight.type.charAt(0).toUpperCase()}${highlight.type.slice(1)} Deadline`
      : "Deadline";

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${urgencyStyle.tone} ${className ?? ""}`}
      title={highlight.reason || highlight.message}
    >
      <span aria-hidden="true">{urgencyStyle.icon}</span>
      <span>{typeLabel}</span>
      <span className="text-current/70">·</span>
      <span>{highlight.date}</span>
    </div>
  );
}

function IeltsFitBadge({
  highlight,
  className,
}: {
  highlight?: RecommendationItem["ieltsFitHighlight"];
  className?: string;
}) {
  return <RequirementFitBadge highlight={highlight} className={className} />;
}

function RequirementFitBadge({
  highlight,
  className,
}: {
  highlight?:
    | RecommendationItem["ieltsFitHighlight"]
    | RecommendationItem["toeflFitHighlight"]
    | RecommendationItem["gpaFitHighlight"]
    | RecommendationItem["duolingoFitHighlight"];
  className?: string;
}) {
  if (!highlight) {
    return null;
  }

  const urgencyStyle =
    highlight.fitUrgency === "high"
      ? {
          icon: "🔴",
          tone: "border-[#f1c5bc] bg-[#fbefeb] text-[#8b3a2b]",
        }
      : highlight.fitUrgency === "medium"
        ? {
            icon: "🟡",
            tone: "border-[#ead9a7] bg-[#fbf5e4] text-[#8a6116]",
          }
        : highlight.fitUrgency === "low"
          ? {
              icon: "🟢",
              tone: "border-[#cfe5d7] bg-[#edf7f1] text-[#1a3d2e]",
            }
          : {
              icon: "⚪",
              tone: "border-[#d7d5d0] bg-[#f5f3ee] text-[#6b7068]",
            };

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${urgencyStyle.tone} ${className ?? ""}`}
      title={highlight.reason || highlight.message}
    >
      <span aria-hidden="true">{urgencyStyle.icon}</span>
      <span>{highlight.message}</span>
    </div>
  );
}

function Section({
  title,
  description,
  items,
}: {
  title: string;
  description: string;
  items: RecommendationItem[];
}) {
  return (
    <section className="rounded-3xl border border-[#e0ddd8] bg-white p-6 shadow-sm">
      <h2 className="text-2xl font-semibold text-[#1a3d2e]">{title}</h2>
      <p className="mt-2 text-sm text-[#6b7068]">{description}</p>

      {items.length === 0 ? (
        <div className="mt-5 rounded-xl bg-[#f5f3ee] p-4 text-[#6b7068]">
          No universities available in this bucket.
        </div>
      ) : (
        <div className="mt-5 grid gap-4">
          {items.map((item, index) => (
            <div
              key={`${title.toLowerCase()}-${item.canonicalUniversityId}-${index}`}
              className="rounded-2xl border border-[#e0ddd8] p-5"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="text-xl font-semibold text-[#1a1a1a]">
                    {item.universityName}
                  </div>
                  <div className="mt-1 text-sm text-[#6b7068]">{item.country}</div>
                </div>
                <div className="rounded-xl bg-[#f5f3ee] px-4 py-3 text-right">
                  <div className="text-xs uppercase tracking-[0.18em] text-[#6b7068]">
                    Fit Score
                  </div>
                  <div className="mt-1 flex items-center justify-end gap-2">
                    <div className="text-xl font-semibold text-[#1a3d2e]">
                      {formatScore(item.recommendationExplain?.fitScore ?? item.matchingScore)}
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] ${
                        fitLevel(item.recommendationExplain?.fitScore ?? item.matchingScore) === "high"
                          ? "bg-[#e8f2ec] text-[#1a3d2e]"
                          : fitLevel(item.recommendationExplain?.fitScore ?? item.matchingScore) === "medium"
                            ? "bg-[#f3ecd6] text-[#8a6116]"
                            : "bg-[#f3e7e4] text-[#8b3a2b]"
                      }`}
                    >
                      {fitLevel(item.recommendationExplain?.fitScore ?? item.matchingScore)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <SummaryItem
                  label="Aggregated Rank"
                  value={`#${formatRank(item.aggregatedRank)}`}
                />
                <SummaryItem label="IELTS Min" value={formatIelts(item.ieltsMin)} />
                <SummaryItem
                  label="Recommendation Confidence"
                  value={formatConfidence(item.recommendationConfidence)}
                />
              </div>

              {item.subjectFit ? (
                <div className="mt-4 rounded-xl border border-[#d8e6dd] bg-[#f6fbf7] p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#1a3d2e]">
                    Subject Signal
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-4">
                    <SummaryItem label="Subject" value={item.subjectFit.subjectName} />
                    <SummaryItem
                      label="Subject Rank"
                      value={
                        item.subjectFit.hasData
                          ? item.subjectFit.rankDisplay ||
                            `#${formatRank(item.subjectFit.rankPosition ?? null)}`
                          : "Neutral"
                      }
                    />
                    <SummaryItem
                      label="Subject Score"
                      value={
                        typeof item.subjectFit.score === "number"
                          ? formatScore(item.subjectFit.score)
                          : "—"
                      }
                    />
                    <SummaryItem
                      label="Fit Adjustment"
                      value={`${item.subjectFit.adjustment >= 0 ? "+" : ""}${item.subjectFit.adjustment.toFixed(1)}`}
                    />
                  </div>
                  <p className="mt-3 text-sm text-[#415046]">{item.subjectFit.reason}</p>
                </div>
              ) : null}

              {item.ieltsFitHighlight || item.toeflFitHighlight || item.gpaFitHighlight || item.duolingoFitHighlight || item.deadlineHighlight ? (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {(item.surfaceSignals && item.surfaceSignals.length > 0
                    ? item.surfaceSignals
                    : [
                        { type: "ielts", emphasized: true },
                        { type: "toefl", emphasized: true },
                        { type: "gpa", emphasized: true },
                        { type: "duolingo", emphasized: true },
                        { type: "deadline", emphasized: true },
                      ]
                  ).map((signal) => {
                    const isPrimary = signal.emphasized !== false;
                    const badgeClass = isPrimary ? "" : "opacity-65";
                    const key = `${item.canonicalUniversityId}-${signal.type}`;

                    if (signal.type === "ielts" && item.ieltsFitHighlight) {
                      return <IeltsFitBadge key={key} highlight={item.ieltsFitHighlight} className={badgeClass} />;
                    }
                    if (signal.type === "toefl" && item.toeflFitHighlight) {
                      return <RequirementFitBadge key={key} highlight={item.toeflFitHighlight} className={badgeClass} />;
                    }
                    if (signal.type === "gpa" && item.gpaFitHighlight) {
                      return <RequirementFitBadge key={key} highlight={item.gpaFitHighlight} className={badgeClass} />;
                    }
                    if (signal.type === "duolingo" && item.duolingoFitHighlight) {
                      return <RequirementFitBadge key={key} highlight={item.duolingoFitHighlight} className={badgeClass} />;
                    }
                    if (signal.type === "deadline" && item.deadlineHighlight) {
                      return <DeadlineBadge key={key} highlight={item.deadlineHighlight} className={badgeClass} />;
                    }
                    return null;
                  })}
                </div>
              ) : null}

              {item.admissionComposite ? (
                <div className="mt-4">
                  <AdmissionCompositeCard composite={item.admissionComposite} />
                </div>
              ) : null}

              {item.decisionOutput ? (
                <div className="mt-4">
                  <DecisionOutputCard decision={item.decisionOutput} />
                </div>
              ) : null}

              {item.admissionResolved && Object.keys(item.admissionResolved).length > 0 ? (
                <div className="mt-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.12em] text-[#6b7068]">
                    Admission Signals
                  </div>
                  <div className="mt-2 grid gap-2">
                    {(["ielts", "toefl", "gpa", "deadline"] as const).map((field) => {
                      const resolved = item.admissionResolved?.[field];
                      if (!resolved) {
                        return null;
                      }
                      return (
                        <AdmissionSignalBadge
                          key={`${item.canonicalUniversityId}-resolved-${field}`}
                          label={resolvedFieldLabel(field)}
                          value={resolved.value}
                          confidence={resolved.confidence}
                          sourceCount={resolved.sourceCount}
                          status={resolved.status}
                        />
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {item.decisionStrategy ? (
                <div className="mt-4">
                  <DecisionStrategyCard strategy={item.decisionStrategy} />
                </div>
              ) : null}

              <div className="mt-4 rounded-xl bg-[#f5f3ee] p-4 text-sm leading-6 text-[#6b7068]">
                {item.explanation}
              </div>

              <ExplainPanel item={item} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
