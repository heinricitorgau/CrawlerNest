"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useHydrated } from "@/hooks/useHydrated";
import { useSearchParams } from "next/navigation";

import {
  AGENT_CAPABILITIES,
  AGENT_LIMITATIONS,
  AGENT_SUGGESTED_PROMPTS,
} from "@/lib/agentSystemPrompt";
import { AGENT_DEMO_RUBRIC } from "@/lib/agentResponseRubric";
import { AUTH_MESSAGES } from "@/lib/authMessages";
import { buildConversationTurns, runEntriesFromTurns } from "@/lib/conversationTurns";
import { saveConversation, type ConversationDetail } from "@/lib/conversationsApi";
import AgentWarningBanner from "@/components/AgentWarningBanner";
import { ConversationHistoryPanel } from "@/components/ConversationHistoryPanel";
import { useAuth } from "@/hooks/useAuthPlaceholder";

/** Blank line between paragraphs, matching how the chat route splits a reply. */
const SPLIT_PARAGRAPHS = /\n{2,}/;

type AgentMode = "web" | "dev";
type TaskKind =
  | "data_query"
  | "ranking_explain"
  | "university_lookup"
  | "recommendation"
  | "dev_refinement";

// ─── Memory debug types ───────────────────────────────────────────────────────
// Only present in the response payload when debug=true is set.

type MemoryTurnDebug = {
  role: string;
  content_preview: string;
  task_kind: string;
  selected_by: string[];
  score_breakdown: {
    entity_overlap: number;
    kind_match: number;
    followup_boost: number;
    carryover_entity_match: number;
    total: number;
  };
  rejected_reason: string | null;
};

type MemoryDebugData = {
  current_input_preview: string;
  current_task_kind: string;
  entity_tokens: string[];
  followup_detected: boolean;
  recent_entity_hint: string | null;
  char_budget_max: number;
  char_budget_used: number;
  turn_budget_max_pairs: number;
  selected_message_count: number;
  memory_summary: {
    selection_mode: string;
    primary_signals: string[];
    selected_count: number;
    rejected_count: number;
    ambiguity_level: "low" | "medium" | "high";
    summary_text: string;
  };
  selected_turns: MemoryTurnDebug[];
  rejected_turns: MemoryTurnDebug[];
};

type ReferenceDebugData = {
  original_input: string;
  rewrite_applied: boolean;
  rewritten_query: string | null;
  rewrite_reason: string;
  resolved_reference: {
    detected: boolean;
    input_type: "explicit_entity" | "pronoun_followup" | "compare_followup" | "none";
    resolved_entities: string[];
    confidence: "low" | "medium" | "high";
    reason: string;
  };
};

type GroundingDebugData = {
  answer_preview: string;
  grounding_sources: {
    retrieval: {
      used: boolean;
      matched_items: string[];
      match_score: number;
      reason?: string | null;
    };
    memory: {
      used: boolean;
      matched_items: string[];
      match_score: number;
      reason?: string | null;
    };
    generation: {
      used: boolean;
      matched_items: string[];
      match_score: number;
      reason?: string | null;
    };
  };
  grounding_score: {
    overall: number;
    breakdown: {
      retrieval_weight: number;
      memory_weight: number;
    };
  };
  hallucination_risk: {
    level: "low" | "medium" | "high";
    reason: string;
  };
  explanation: {
    summary: string;
    detail: string;
  };
};

type PolicyDebugData = {
  mode: "deterministic" | "hybrid" | "llm";
  reason: string;
  signals: {
    has_retrieval: boolean;
    retrieval_confidence: number;
    has_memory: boolean;
    ambiguity_level: "low" | "medium" | "high";
    query_type: "fact" | "comparison" | "recommendation" | "open_ended";
  };
};

type OrchestrationDebugData = {
  route: "web" | "dev" | "web_to_dev";
  reason: string;
  signals: {
    is_dev_intent: boolean;
    has_code_keywords: boolean;
    explicit_dev_kind: boolean;
  };
  dev_call: {
    invoked: boolean;
    latency_ms: number | null;
    returned: {
      has_patch: boolean;
    };
  };
};

type LongTermMemoryDebugData = {
  retrieved: Array<{
    content: string;
    type: string;
    used: boolean;
    confidence: number;
    importance: number;
    decayScore: number;
  }>;
};

type SelfImprovementDebugData = {
  performance: {
    task_kind: string;
    sample_size: number;
    avg_score: number;
    failure_rate: number;
    success_rate: number;
    common_failure_step: string | null;
  };
  new_strategy_generated: boolean;
  strategy_applied: boolean;
  strategy_source?: "stored" | "newly_generated" | "none";
  reason: string;
  applied_strategies?: string[];
  anti_patterns?: string[];
  strategy_lineage?: Array<{
    patch_status?: string;
    patch_record_id?: string;
    strategy_id?: string;
    strategy_type?: string;
    version?: string;
    source?: string;
  }>;
  last_experience?: {
    status?: string;
    final_score?: number;
  };
};

type MetaDebugData = {
  strategy_applied: boolean;
  strategy_type: string | null;
  confidence: number | null;
  source: string | null;
  applied?: Array<{
    id?: string;
    strategy_type?: string;
    confidence?: number;
    source?: string;
    version?: string;
    target?: string | null;
  }>;
  generated?: Array<{
    id?: string;
    strategy_type?: string;
    confidence?: number;
    source?: string;
    version?: string;
  }>;
  rolled_back?: Array<{
    id?: string;
    strategy_type?: string;
    reason?: string;
  }>;
};

type RewriteDebugData = {
  patch_generated: boolean;
  patch_valid: boolean;
  applied_in_sandbox: boolean;
  improved: boolean;
  score_delta: number;
  status?: string;
};

type AgentResponse = {
  success: boolean;
  error?: string;
  data?: {
    taskId: string;
    status: string;
    message: string;
    data: {
      type?: string;
      title?: string;
      explanation?: string;
      explanationParagraphs?: string[];
      sessionId?: string;
      memoryDebug?: MemoryDebugData;
      referenceDebug?: ReferenceDebugData;
      groundingDebug?: GroundingDebugData;
      policyDebug?: PolicyDebugData;
      orchestrationDebug?: OrchestrationDebugData;
      longTermMemoryDebug?: LongTermMemoryDebugData;
      selfImprovementDebug?: SelfImprovementDebugData;
      metaDebug?: MetaDebugData;
      rewriteDebug?: RewriteDebugData;
      items?: Array<{
        label: string;
        kind?: string;
        description?: string | null;
        data?: Record<string, unknown>;
      }>;
      meta?: Record<string, unknown>;
    };
    traces: Array<Record<string, unknown>>;
    warnings: string[];
  };
};

type RunEntry = {
  id: string;
  mode: AgentMode;
  kind: TaskKind;
  prompt: string;
  response: AgentResponse | null;
  error: string | null;
};

type AgentHealthResponse = {
  success: boolean;
  status?: string;
  error?: string;
  generation?: {
    configured: boolean;
    providerLabel: string | null;
    modelName: string | null;
    baseUrl: string | null;
    reason: string | null;
  };
};

const TASK_OPTIONS: Array<{ value: TaskKind; label: string }> = [
  { value: "data_query", label: "Data Query" },
  { value: "ranking_explain", label: "Ranking Explain" },
  { value: "university_lookup", label: "University Lookup" },
  { value: "recommendation", label: "Recommendation" },
  { value: "dev_refinement", label: "Dev Refinement" },
];

const QUICK_TASKS: Array<{
  label: string;
  mode: AgentMode;
  kind: TaskKind;
  prompt: string;
  context: string;
}> = [
  {
    label: "Explain Oxford",
    mode: "web",
    kind: "ranking_explain",
    prompt: "Explain why Oxford ranks highly",
    context: JSON.stringify(
      { year: 2026, scope: "global", page: 1, page_size: 5, search: "Oxford" },
      null,
      2
    ),
  },
  {
    label: "Lookup MIT",
    mode: "web",
    kind: "university_lookup",
    prompt: "Show the MIT university preview",
    context: JSON.stringify({ canonical_university_id: 1 }, null, 2),
  },
  {
    label: "Rankings Page 1",
    mode: "web",
    kind: "data_query",
    prompt: "Load the first page of global rankings",
    context: JSON.stringify(
      { year: 2026, scope: "global", page: 1, page_size: 20 },
      null,
      2
    ),
  },
  {
    label: "Recommend UK 6.5",
    mode: "web",
    kind: "recommendation",
    prompt: "Recommend UK universities for IELTS 6.5 and target rank 100",
    context: JSON.stringify(
      { country: "United Kingdom", ielts: 6.5, targetRank: 100, riskProfile: "balanced", limit: 5 },
      null,
      2
    ),
  },
  {
    label: "Recommend Singapore",
    mode: "web",
    kind: "recommendation",
    prompt: "Recommend Singapore universities for IELTS 7.0 with a conservative profile",
    context: JSON.stringify(
      { country: "Singapore", ielts: 7.0, riskProfile: "conservative", limit: 5 },
      null,
      2
    ),
  },
];

const PROMPT_HINTS: Record<TaskKind, string> = {
  data_query: "Ask for a rankings page, a filtered list, or a university data query...",
  ranking_explain: "Ask why a university ranks highly, where it is, or what a ranking result means...",
  university_lookup: "Ask to look up a university preview, aliases, or admission details...",
  recommendation: "Describe your target country, rank range, language score, or preferences...",
  dev_refinement: "Describe the extractor, parser, or implementation issue you want the dev agent to refine...",
};

function formatResponse(response: AgentResponse | null) {
  return JSON.stringify(response, null, 2);
}

function getFriendlyError(error: string | null) {
  if (!error) {
    return null;
  }

  if (
    error.includes("Failed to reach /api/agent/chat") ||
    error.includes("Failed to reach agent API")
  ) {
    return "Agent chat route is unavailable. Check the Next.js server, then try again.";
  }

  return error;
}

function stripPromptBoundContext(rawContextJson: string) {
  if (!rawContextJson.trim()) {
    return rawContextJson;
  }

  try {
    const parsed = JSON.parse(rawContextJson) as Record<string, unknown>;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      return rawContextJson;
    }

    delete parsed.search;
    delete parsed.university_name;
    delete parsed.canonical_university_id;
    delete parsed.country;
    delete parsed.countryPolicy;
    delete parsed.country_policy;
    delete parsed.ielts;
    delete parsed.ielts_score;
    delete parsed.ieltsScore;
    delete parsed.toefl;
    delete parsed.targetRank;
    delete parsed.target_rank;
    delete parsed.riskProfile;
    delete parsed.risk_profile;
    delete parsed.preferredRankingSource;
    delete parsed.preferred_ranking_source;
    delete parsed.limit;
    delete parsed.preferenceWeights;
    delete parsed.preference_weights;

    return JSON.stringify(parsed, null, 2);
  } catch {
    return rawContextJson;
  }
}

// ─── Dev mode helpers ────────────────────────────────────────────────────────

/** Convert snake_case or camelCase identifiers to readable Title Case labels. */
function toTitleCase(raw: string): string {
  return raw
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Recursively render an unknown value as human-readable JSX.
 * Used exclusively in the dev render branch — never called for web responses.
 *
 * Rules:
 *   primitive          → coloured inline span
 *   string[]|number[]  → pill row
 *   plain object (≤2)  → labelled key-value rows
 *   deep/complex       → compact JSON pre block (fallback)
 */
function renderStructuredValue(value: unknown, depth = 0): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-(--color-muted) italic">null</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span className={value ? "font-mono text-(--color-ink-2)" : "font-mono text-(--color-error)"}>
        {String(value)}
      </span>
    );
  }
  if (typeof value === "number") {
    return <span className="font-mono text-(--color-ink)">{String(value)}</span>;
  }
  if (typeof value === "string") {
    return <span className="text-(--color-ink)">{value}</span>;
  }
  if (Array.isArray(value)) {
    const isSimple = value.every((v) => typeof v === "string" || typeof v === "number");
    if (isSimple) {
      return (
        <div className="flex flex-wrap gap-1.5">
          {value.map((item, i) => (
            <span
              key={i}
              className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-xs text-(--color-ink)"
            >
              {String(item)}
            </span>
          ))}
        </div>
      );
    }
    return (
      <pre className="overflow-x-auto rounded-xl bg-(--color-paper-2) px-3 py-2 text-xs leading-5 text-(--color-ink)">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  if (typeof value === "object") {
    if (depth >= 2) {
      return (
        <pre className="overflow-x-auto rounded-xl bg-(--color-paper-2) px-3 py-2 text-xs leading-5 text-(--color-ink)">
          {JSON.stringify(value, null, 2)}
        </pre>
      );
    }
    return (
      <div className="space-y-3">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k}>
            <div className="mb-1 text-[10px] text-(--color-muted)">
              {toTitleCase(k)}
            </div>
            {renderStructuredValue(v, depth + 1)}
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-(--color-muted)">{String(value)}</span>;
}

/**
 * Fields that already have dedicated sections in the dev branch UI (execution
 * plan, warnings bar, card header status).  Skipping them here prevents
 * duplication without hiding any data — they remain visible in the debug panel.
 */
const DEV_SKIP_FIELDS = new Set(["traces", "warnings", "status"]);

/**
 * Render a single top-level field from a dev-mode payload with semantic clarity.
 * Returns null for fields that are already rendered elsewhere.
 * Falls back to the generic renderStructuredValue for unknown shapes.
 *
 * Only ever called from the dev render branch — never for web responses.
 */
function renderDevField(key: string, value: unknown): React.ReactNode | null {
  if (DEV_SKIP_FIELDS.has(key)) return null;

  // ── task: full-width text block, reads like a description ──────────────────
  if (key === "task") {
    return (
      <div className="rounded-xl bg-(--color-paper) px-4 py-3 text-sm leading-6 text-(--color-ink)">
        {typeof value === "string" ? value : JSON.stringify(value)}
      </div>
    );
  }

  // ── loop: numbered stage list with terminal stage highlighted ────────────
  if (key === "loop" && Array.isArray(value)) {
    const stages = value as unknown[];
    return (
      <ol className="space-y-2">
        {stages.map((step, i) => (
          <li key={i} className="flex items-center gap-2.5">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center border border-(--color-rule) bg-(--color-paper) font-mono text-[10px] text-(--color-muted)">
              {i + 1}
            </span>
            <span
              className={`rounded-lg border px-3 py-1 text-xs ${
                i === stages.length - 1
                  ? "border-(--color-rule) bg-(--color-paper) text-(--color-ink)"
                  : "border-(--color-rule) bg-white text-(--color-ink)"
              }`}
            >
              {toTitleCase(String(step))}
            </span>
          </li>
        ))}
      </ol>
    );
  }

  // ── score: large coloured number with tier colouring ─────────────────────
  if (key === "score" && typeof value === "number") {
    const isNorm = value >= 0 && value <= 1;
    const pct = isNorm ? value * 100 : value;
    const tier =
      pct >= 70
        ? { text: "text-(--color-ink-2)", bg: "bg-(--color-paper)", border: "border-(--color-rule)" }
        : pct >= 40
          ? { text: "text-(--color-warn)", bg: "bg-(--color-plate)", border: "border-(--color-warn-soft)" }
          : { text: "text-(--color-error)", bg: "bg-(--color-plate)", border: "border-(--color-error-soft)" };
    return (
      <div
        className={`inline-flex items-baseline gap-1.5 rounded-xl border px-4 py-2 ${tier.bg} ${tier.border}`}
      >
        <span className={`text-2xl font-bold leading-none ${tier.text}`}>
          {isNorm ? value.toFixed(2) : value}
        </span>
        {isNorm ? (
          <span className={`text-xs ${tier.text} opacity-60`}>/ 1.0</span>
        ) : null}
      </div>
    );
  }

  // ── result: bordered output block — more distinct than generic text ───────
  if (key === "result") {
    if (typeof value === "string") {
      return (
        <div className="rounded-xl border border-(--color-rule) bg-(--color-paper) px-4 py-3 text-sm leading-6 text-(--color-ink)">
          {value}
        </div>
      );
    }
  }

  // ── file_patch: dark monospaced block — visually distinct from prose ──────
  if (key === "file_patch") {
    return (
      <pre className="overflow-x-auto rounded-xl bg-(--color-ink) px-4 py-3 text-xs leading-5 text-(--color-rule)">
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    );
  }

  // ── validation-like: status card with pass/fail colouring ─────────────────
  if (
    (key === "validation" ||
      key === "code_validation" ||
      key === "smoke_test" ||
      key === "regression_test") &&
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  ) {
    const obj = value as Record<string, unknown>;
    const passed =
      obj.passed === true ||
      obj.status === "pass" ||
      obj.status === "passed" ||
      obj.status === "ok";
    const failed =
      obj.passed === false ||
      obj.status === "fail" ||
      obj.status === "failed" ||
      obj.status === "error";
    const style = passed
      ? {
          border: "border-(--color-rule)",
          bg: "bg-(--color-paper)",
          label: "text-(--color-ink-2)",
          dot: "bg-(--color-ink-2)",
          text: "Passed",
        }
      : failed
        ? {
            border: "border-(--color-error-soft)",
            bg: "bg-(--color-plate)",
            label: "text-(--color-error)",
            dot: "bg-(--color-error)",
            text: "Failed",
          }
        : {
            border: "border-(--color-rule)",
            bg: "bg-(--color-paper)",
            label: "text-(--color-muted)",
            dot: "bg-(--color-muted)",
            text: "Unknown",
          };
    const extraEntries = Object.entries(obj).filter(
      ([k]) => k !== "passed" && k !== "status"
    );
    return (
      <div className={`rounded-xl border ${style.border} ${style.bg} px-4 py-3`}>
        <div className={`mb-2 flex items-center gap-1.5 text-xs font-semibold ${style.label}`}>
          <span className={`h-1.5 w-1.5 ${style.dot}`} />
          {style.text}
        </div>
        {extraEntries.length > 0 ? (
          <div className="space-y-1.5">
            {extraEntries.map(([k, v]) => (
              <div key={k} className="flex items-start gap-3 text-xs">
                <span className="w-28 shrink-0 text-(--color-muted)">{toTitleCase(k)}</span>
                <span className="text-(--color-ink)">
                  {typeof v === "object" && v !== null
                    ? JSON.stringify(v)
                    : String(v ?? "")}
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  // ── generic fallback: recursive structured renderer ───────────────────────
  return renderStructuredValue(value);
}

// ─── Validation summary helpers ──────────────────────────────────────────────

type ValidationCheckResult = {
  key: string;
  label: string;
  passed: boolean;
  failed: boolean;
};

type ValidationSummary = {
  total: number;
  passedCount: number;
  failedCount: number;
  status: "healthy" | "warning" | "failed";
  items: ValidationCheckResult[];
};

/** Keys whose values may carry per-check validation signals. */
const VALIDATION_KEYS = new Set([
  "validation",
  "code_validation",
  "smoke_test",
  "regression_test",
]);

/**
 * Infer pass / fail outcome from a single validation object.
 * Deliberately broad: accepts many common field conventions without hardcoding
 * a single canonical shape.
 */
function inferCheckOutcome(obj: Record<string, unknown>): {
  passed: boolean;
  failed: boolean;
} {
  // Boolean pass signals
  const passBool =
    obj.passed === true ||
    obj.success === true ||
    obj.valid === true ||
    obj.ok === true;
  // Boolean fail signals
  const failBool =
    obj.passed === false ||
    obj.success === false ||
    obj.valid === false ||
    obj.failed === true;
  // String status signals
  const statusStr =
    typeof obj.status === "string" ? obj.status.toLowerCase() : null;
  const statusPass =
    statusStr !== null &&
    ["pass", "passed", "ok", "success"].includes(statusStr);
  const statusFail =
    statusStr !== null && ["fail", "failed", "error"].includes(statusStr);
  // Non-empty error / issue arrays are a fail signal
  const hasIssues =
    (Array.isArray(obj.errors) && obj.errors.length > 0) ||
    (Array.isArray(obj.issues) && obj.issues.length > 0) ||
    (Array.isArray(obj.failures) && obj.failures.length > 0);

  return {
    passed: !hasIssues && (passBool || statusPass),
    failed: failBool || statusFail || hasIssues,
  };
}

/**
 * Scan the top-level keys of a dev payload, collect validation objects, and
 * compute an aggregate summary.  Returns null when no validation keys are found
 * so the caller can skip rendering entirely.
 */
function extractValidationSummary(
  data: Record<string, unknown>
): ValidationSummary | null {
  const items: ValidationCheckResult[] = [];

  for (const [key, value] of Object.entries(data)) {
    if (!VALIDATION_KEYS.has(key)) continue;
    if (typeof value !== "object" || value === null || Array.isArray(value))
      continue;
    const { passed, failed } = inferCheckOutcome(
      value as Record<string, unknown>
    );
    items.push({ key, label: toTitleCase(key), passed, failed });
  }

  if (items.length === 0) return null;

  const passedCount = items.filter((i) => i.passed).length;
  const failedCount = items.filter((i) => i.failed).length;

  const status: ValidationSummary["status"] =
    failedCount > 0
      ? "failed"
      : passedCount === items.length
        ? "healthy"
        : "warning";

  return { total: items.length, passedCount, failedCount, status, items };
}

/**
 * Render the compact validation summary card.
 * Only called when extractValidationSummary returns a non-null value.
 * Never called for web responses.
 */
function renderValidationSummary(summary: ValidationSummary): React.ReactNode {
  const cfg =
    summary.status === "healthy"
      ? {
          border: "border-(--color-rule)",
          bg: "bg-(--color-paper)",
          label: "text-(--color-ink-2)",
          dot: "bg-(--color-ink-2)",
          text: "Healthy",
        }
      : summary.status === "failed"
        ? {
            border: "border-(--color-error-soft)",
            bg: "bg-(--color-plate)",
            label: "text-(--color-error)",
            dot: "bg-(--color-error)",
            text: "Failed",
          }
        : {
            border: "border-(--color-warn-soft)",
            bg: "bg-(--color-plate)",
            label: "text-(--color-warn)",
            dot: "bg-(--color-warn)",
            text: "Warning",
          };

  return (
    <div
      className={` border ${cfg.border} ${cfg.bg} px-5 py-4`}
    >
      <div className="mb-3 text-xs text-(--color-muted)">
        Validation Summary
      </div>

      {/* Overall status + counts */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 ${cfg.dot}`} />
          <span className={`text-sm font-semibold ${cfg.label}`}>
            {cfg.text}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-(--color-muted)">
          <span>
            <span className="font-semibold text-(--color-ink-2)">
              {summary.passedCount}
            </span>{" "}
            passed
          </span>
          {summary.failedCount > 0 ? (
            <span>
              <span className="font-semibold text-(--color-error)">
                {summary.failedCount}
              </span>{" "}
              failed
            </span>
          ) : null}
          <span>
            <span className="font-semibold text-(--color-ink)">
              {summary.total}
            </span>{" "}
            total
          </span>
        </div>
      </div>

      {/* Per-check pills */}
      {summary.items.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {summary.items.map((item) => (
            <span
              key={item.key}
              className={` border px-2.5 py-0.5 text-xs ${
                item.passed
                  ? "border-(--color-rule) bg-white text-(--color-ink-2)"
                  : item.failed
                    ? "border-(--color-error-soft) bg-white text-(--color-error)"
                    : "border-(--color-rule) bg-white text-(--color-muted)"
              }`}
            >
              {item.passed ? "✓ " : item.failed ? "✗ " : "· "}
              {item.label}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ─── Memory debug renderer ────────────────────────────────────────────────────

/** Signal pill colour map. */
const SIGNAL_STYLES: Record<string, { border: string; text: string; bg: string }> = {
  always_recent:  { border: "border-(--color-rule)", bg: "bg-(--color-paper)", text: "text-(--color-ink-2)" },
  entity_overlap: { border: "border-(--color-paper-2)", bg: "bg-(--color-paper)", text: "text-(--color-ink-2)" },
  kind_match:     { border: "border-(--color-paper-2)", bg: "bg-(--color-paper)", text: "text-(--color-ink-2)" },
  followup_boost: { border: "border-(--color-warn-soft)", bg: "bg-(--color-plate)", text: "text-(--color-warn)" },
  carryover_entity_match: { border: "border-(--color-paper-2)", bg: "bg-(--color-paper)", text: "text-(--color-ink-2)" },
};

const AMBIGUITY_STYLES: Record<"low" | "medium" | "high", { border: string; bg: string; text: string }> = {
  low: { border: "border-(--color-rule)", bg: "bg-(--color-paper)", text: "text-(--color-ink-2)" },
  medium: { border: "border-(--color-warn-soft)", bg: "bg-(--color-plate)", text: "text-(--color-warn)" },
  high: { border: "border-(--color-error-soft)", bg: "bg-(--color-plate)", text: "text-(--color-error)" },
};

function renderMemoryDebugTurnRow(
  turn: MemoryTurnDebug,
  isSelected: boolean,
): React.ReactNode {
  const signals = turn.selected_by;
  const bd = turn.score_breakdown;

  return (
    <div
      key={`${turn.role}-${turn.content_preview}`}
      className={`rounded-xl border px-3 py-2.5 text-xs ${
        isSelected
          ? "border-(--color-rule) bg-(--color-paper)"
          : "border-(--color-rule) bg-white"
      }`}
    >
      {/* Role + task_kind + score */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span
          className={` border px-2 py-0.5 font-mono text-[10px] ${
            turn.role === "user"
              ? "border-(--color-rule) bg-(--color-paper) text-(--color-muted)"
              : "border-(--color-paper-2) bg-(--color-paper) text-(--color-ink-2)"
          }`}
        >
          {turn.role}
        </span>
        {turn.task_kind ? (
          <span className="border border-(--color-rule) bg-white px-2 py-0.5 text-[10px] text-(--color-muted)">
            {turn.task_kind.replace(/_/g, " ")}
          </span>
        ) : null}
        {/* Score badge */}
        <span
          className={`ml-auto border px-2 py-0.5 font-mono text-[10px] font-semibold ${
            bd.total > 0
              ? "border-(--color-rule) bg-(--color-paper) text-(--color-ink-2)"
              : "border-(--color-rule) bg-white text-(--color-muted)"
          }`}
        >
          {bd.total > 0 ? `+${bd.total}` : "0"}
        </span>
      </div>

      {/* Content preview */}
      <div className="mt-1.5 font-mono text-[11px] leading-5 text-(--color-ink)">
        {turn.content_preview}
      </div>

      {/* Signal pills (selected turns) */}
      {signals.length > 0 ? (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {signals.map((sig) => {
            const style = SIGNAL_STYLES[sig] ?? {
              border: "border-(--color-rule)",
              bg: "bg-white",
              text: "text-(--color-muted)",
            };
            return (
              <span
                key={sig}
                className={`rounded-full border px-2 py-0.5 text-[10px] ${style.border} ${style.bg} ${style.text}`}
              >
                {sig.replace(/_/g, " ")}
              </span>
            );
          })}
          {bd.entity_overlap > 0 || bd.kind_match > 0 || bd.followup_boost > 0 || bd.carryover_entity_match > 0 ? (
            <span className="ml-auto border border-(--color-rule) bg-white px-2 py-0.5 font-mono text-[10px] text-(--color-muted)">
              {[
                bd.entity_overlap > 0 ? `ent+${bd.entity_overlap}` : null,
                bd.kind_match > 0 ? `kind+${bd.kind_match}` : null,
                bd.followup_boost > 0 ? `follow+${bd.followup_boost}` : null,
                bd.carryover_entity_match > 0 ? `carry+${bd.carryover_entity_match}` : null,
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          ) : null}
        </div>
      ) : null}

      {/* Rejection reason (rejected turns) */}
      {turn.rejected_reason ? (
        <div className="mt-1.5 text-[10px] text-(--color-error)">
          ✗ {turn.rejected_reason.replace(/_/g, " ")}
        </div>
      ) : null}
    </div>
  );
}

function renderMemoryDebug(md: MemoryDebugData): React.ReactNode {
  const budgetPct = md.char_budget_max > 0
    ? Math.round((md.char_budget_used / md.char_budget_max) * 100)
    : 0;
  const summary = md.memory_summary;
  const ambiguityStyle = AMBIGUITY_STYLES[summary.ambiguity_level] ?? AMBIGUITY_STYLES.medium;

  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      {/* ── Header ── */}
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Memory debug
      </div>

      {/* ── Request signals row ── */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-(--color-ink)">
          kind: <span className="font-medium">{md.current_task_kind.replace(/_/g, " ")}</span>
        </span>
        {md.followup_detected ? (
          <span className="border border-(--color-warn-soft) bg-(--color-plate) px-2.5 py-0.5 text-(--color-warn)">
            ↩ follow-up detected
          </span>
        ) : null}
        {md.entity_tokens.length > 0 ? (
          <span className="border border-(--color-paper-2) bg-(--color-paper) px-2.5 py-0.5 text-(--color-ink-2)">
            entities: {md.entity_tokens.join(", ")}
          </span>
        ) : (
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-(--color-muted)">
            no entities detected
          </span>
        )}
        {md.recent_entity_hint ? (
          <span className="border border-(--color-paper-2) bg-(--color-paper) px-2.5 py-0.5 text-(--color-ink-2)">
            recent entity: {md.recent_entity_hint}
          </span>
        ) : null}
      </div>

      {/* ── Budget row ── */}
      <div className="mb-3 flex flex-wrap items-center gap-3 text-(--color-muted)">
        <span>
          chars:{" "}
          <span className="font-medium text-(--color-ink)">{md.char_budget_used}</span>
          {" / "}
          {md.char_budget_max}
          {" "}
          <span className="opacity-60">({budgetPct}%)</span>
        </span>
        <span>
          messages:{" "}
          <span className="font-medium text-(--color-ink)">{md.selected_message_count}</span>
          {" (max pairs: "}
          {md.turn_budget_max_pairs}
          {")"}
        </span>
      </div>

      {/* ── Summary block ── */}
      <div className="mb-3 rounded-xl border border-(--color-rule) bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {summary.selection_mode.replace(/_/g, " ")}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${ambiguityStyle.border} ${ambiguityStyle.bg} ${ambiguityStyle.text}`}>
            ambiguity: {summary.ambiguity_level}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            selected {summary.selected_count}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            rejected {summary.rejected_count}
          </span>
        </div>
        <div className="text-[11px] leading-5 text-(--color-ink)">{summary.summary_text}</div>
        {summary.primary_signals.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1">
            {summary.primary_signals.map((signal) => {
              const style = SIGNAL_STYLES[signal] ?? {
                border: "border-(--color-rule)",
                bg: "bg-white",
                text: "text-(--color-muted)",
              };
              return (
                <span
                  key={signal}
                  className={`rounded-full border px-2 py-0.5 text-[10px] ${style.border} ${style.bg} ${style.text}`}
                >
                  {signal.replace(/_/g, " ")}
                </span>
              );
            })}
          </div>
        ) : null}
      </div>

      {/* ── Selected turns ── */}
      {md.selected_turns.length > 0 ? (
        <div className="mb-3">
          <div className="mb-1.5 text-[10px] text-(--color-muted)">
            Selected — {md.selected_turns.length} message{md.selected_turns.length !== 1 ? "s" : ""}
          </div>
          <div className="space-y-1.5">
            {md.selected_turns.map((t) => renderMemoryDebugTurnRow(t, true))}
          </div>
        </div>
      ) : (
        <div className="mb-3 rounded-xl border border-dashed border-(--color-rule) px-3 py-2 text-(--color-muted)">
          No prior turns selected — this is the first message or memory is disabled.
        </div>
      )}

      {/* ── Rejected turns ── */}
      {md.rejected_turns.length > 0 ? (
        <div>
          <div className="mb-1.5 text-[10px] text-(--color-muted)">
            Rejected — {md.rejected_turns.length} message{md.rejected_turns.length !== 1 ? "s" : ""}
          </div>
          <div className="space-y-1.5">
            {md.rejected_turns.map((t) => renderMemoryDebugTurnRow(t, false))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function renderReferenceDebug(referenceDebug: ReferenceDebugData): React.ReactNode {
  const confidenceStyle =
    AMBIGUITY_STYLES[referenceDebug.resolved_reference.confidence] ??
    AMBIGUITY_STYLES.medium;

  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Reference debug
      </div>

      <div className="mb-3 rounded-xl border border-(--color-rule) bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {referenceDebug.resolved_reference.input_type.replace(/_/g, " ")}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${confidenceStyle.border} ${confidenceStyle.bg} ${confidenceStyle.text}`}>
            confidence: {referenceDebug.resolved_reference.confidence}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            rewrite {referenceDebug.rewrite_applied ? "applied" : "not applied"}
          </span>
        </div>

        <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-(--color-muted)">original</span>
          <span className="font-medium text-(--color-ink)">{referenceDebug.original_input}</span>
          <span className="text-(--color-muted)">rewritten</span>
          <span className="font-medium text-(--color-ink)">
            {referenceDebug.rewritten_query ?? "—"}
          </span>
          <span className="text-(--color-muted)">entities</span>
          <span className="font-medium text-(--color-ink)">
            {referenceDebug.resolved_reference.resolved_entities.length > 0
              ? referenceDebug.resolved_reference.resolved_entities.join(", ")
              : "—"}
          </span>
          <span className="text-(--color-muted)">reason</span>
          <span className="text-(--color-ink)">{referenceDebug.resolved_reference.reason}</span>
          <span className="text-(--color-muted)">rewrite note</span>
          <span className="text-(--color-ink)">{referenceDebug.rewrite_reason}</span>
        </div>
      </div>
    </div>
  );
}

function renderGroundingDebug(groundingDebug: GroundingDebugData): React.ReactNode {
  const riskStyle =
    AMBIGUITY_STYLES[groundingDebug.hallucination_risk.level] ??
    AMBIGUITY_STYLES.medium;
  const sources = groundingDebug.grounding_sources;

  const renderSource = (
    label: string,
    source: {
      used: boolean;
      matched_items: string[];
      match_score: number;
      reason?: string | null;
    },
  ) => (
    <div className="rounded-xl border border-(--color-rule) bg-white px-3 py-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
          {label}
        </span>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-[10px] ${
            source.used
              ? "border-(--color-rule) bg-(--color-paper) text-(--color-ink-2)"
              : "border-(--color-rule) bg-white text-(--color-muted)"
          }`}
        >
          {source.used ? "used" : "not used"}
        </span>
        <span className="ml-auto border border-(--color-rule) bg-white px-2 py-0.5 font-mono text-[10px] text-(--color-muted)">
          {source.match_score.toFixed(2)}
        </span>
      </div>
      {source.reason ? (
        <div className="text-[11px] leading-5 text-(--color-ink)">{source.reason}</div>
      ) : null}
      {source.matched_items.length > 0 ? (
        <div className="mt-2 space-y-1">
          {source.matched_items.map((item) => (
            <div key={`${label}-${item}`} className="font-mono text-[11px] leading-5 text-(--color-muted)">
              • {item}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );

  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Grounding debug
      </div>

      <div className="mb-3 rounded-xl border border-(--color-rule) bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            grounding {groundingDebug.grounding_score.overall.toFixed(2)}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${riskStyle.border} ${riskStyle.bg} ${riskStyle.text}`}>
            risk: {groundingDebug.hallucination_risk.level}
          </span>
        </div>
        <div className="text-[11px] leading-5 text-(--color-ink)">
          {groundingDebug.explanation.summary}
        </div>
        <div className="mt-1 text-[11px] leading-5 text-(--color-muted)">
          {groundingDebug.explanation.detail}
        </div>
        <div className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-(--color-muted)">retrieval</span>
          <span className="font-medium text-(--color-ink)">
            {groundingDebug.grounding_score.breakdown.retrieval_weight.toFixed(2)}
          </span>
          <span className="text-(--color-muted)">memory</span>
          <span className="font-medium text-(--color-ink)">
            {groundingDebug.grounding_score.breakdown.memory_weight.toFixed(2)}
          </span>
          <span className="text-(--color-muted)">answer</span>
          <span className="text-(--color-ink)">{groundingDebug.answer_preview}</span>
        </div>
      </div>

      <div className="space-y-3">
        {renderSource("retrieval", sources.retrieval)}
        {renderSource("memory", sources.memory)}
        {renderSource("generation", sources.generation)}
      </div>
    </div>
  );
}

function renderPolicyDebug(policyDebug: PolicyDebugData): React.ReactNode {
  const ambiguityStyle =
    AMBIGUITY_STYLES[policyDebug.signals.ambiguity_level] ??
    AMBIGUITY_STYLES.medium;

  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Policy debug
      </div>

      <div className="rounded-xl border border-(--color-rule) bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {policyDebug.mode}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${ambiguityStyle.border} ${ambiguityStyle.bg} ${ambiguityStyle.text}`}>
            ambiguity: {policyDebug.signals.ambiguity_level}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {policyDebug.signals.query_type}
          </span>
        </div>

        <div className="text-[11px] leading-5 text-(--color-ink)">{policyDebug.reason}</div>

        <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-(--color-muted)">retrieval</span>
          <span className="font-medium text-(--color-ink)">
            {policyDebug.signals.has_retrieval ? "yes" : "no"} · {policyDebug.signals.retrieval_confidence.toFixed(2)}
          </span>
          <span className="text-(--color-muted)">memory</span>
          <span className="font-medium text-(--color-ink)">
            {policyDebug.signals.has_memory ? "yes" : "no"}
          </span>
        </div>
      </div>
    </div>
  );
}

function renderOrchestrationDebug(orchestrationDebug: OrchestrationDebugData): React.ReactNode {
  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Orchestration debug
      </div>

      <div className="rounded-xl border border-(--color-rule) bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {orchestrationDebug.route}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            dev call: {orchestrationDebug.dev_call.invoked ? "yes" : "no"}
          </span>
        </div>

        <div className="text-[11px] leading-5 text-(--color-ink)">{orchestrationDebug.reason}</div>

        <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-(--color-muted)">dev intent</span>
          <span className="font-medium text-(--color-ink)">
            {orchestrationDebug.signals.is_dev_intent ? "yes" : "no"}
          </span>
          <span className="text-(--color-muted)">code keywords</span>
          <span className="font-medium text-(--color-ink)">
            {orchestrationDebug.signals.has_code_keywords ? "yes" : "no"}
          </span>
          <span className="text-(--color-muted)">explicit dev kind</span>
          <span className="font-medium text-(--color-ink)">
            {orchestrationDebug.signals.explicit_dev_kind ? "yes" : "no"}
          </span>
          <span className="text-(--color-muted)">latency</span>
          <span className="font-medium text-(--color-ink)">
            {orchestrationDebug.dev_call.latency_ms ?? "—"} ms
          </span>
          <span className="text-(--color-muted)">returned patch</span>
          <span className="font-medium text-(--color-ink)">
            {orchestrationDebug.dev_call.returned.has_patch ? "yes" : "no"}
          </span>
        </div>
      </div>
    </div>
  );
}

function renderLongTermMemoryDebug(longTermMemoryDebug: LongTermMemoryDebugData): React.ReactNode {
  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Long-term memory debug
      </div>
      {longTermMemoryDebug.retrieved.length === 0 ? (
        <div className="rounded-xl border border-(--color-rule) bg-white px-3 py-3 text-[11px] text-(--color-muted)">
          No long-term memory entries were used.
        </div>
      ) : (
        <div className="space-y-3">
          {longTermMemoryDebug.retrieved.map((entry, index) => (
            <div key={`${entry.type}-${index}`} className="rounded-xl border border-(--color-rule) bg-white px-3 py-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
                  {entry.type}
                </span>
                <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
                  confidence: {entry.confidence.toFixed(2)}
                </span>
              </div>
              <div className="text-[11px] leading-5 text-(--color-ink)">{entry.content}</div>
              <div className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
                <span className="text-(--color-muted)">used</span>
                <span className="font-medium text-(--color-ink)">{entry.used ? "yes" : "no"}</span>
                <span className="text-(--color-muted)">importance</span>
                <span className="font-medium text-(--color-ink)">{entry.importance.toFixed(2)}</span>
                <span className="text-(--color-muted)">decay</span>
                <span className="font-medium text-(--color-ink)">{entry.decayScore.toFixed(2)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function renderSelfImprovementDebug(selfImprovementDebug: SelfImprovementDebugData): React.ReactNode {
  const performance = selfImprovementDebug.performance;
  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Self-improvement debug
      </div>

      <div className="rounded-xl border border-(--color-rule) bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            sample: {performance.sample_size}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            source: {selfImprovementDebug.strategy_source ?? "none"}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            avg: {performance.avg_score.toFixed(2)}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            failure: {(performance.failure_rate * 100).toFixed(0)}%
          </span>
        </div>

        <div className="text-[11px] leading-5 text-(--color-ink)">{selfImprovementDebug.reason}</div>

        <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-(--color-muted)">strategy applied</span>
          <span className="font-medium text-(--color-ink)">
            {selfImprovementDebug.strategy_applied ? "yes" : "no"}
          </span>
          <span className="text-(--color-muted)">new strategy</span>
          <span className="font-medium text-(--color-ink)">
            {selfImprovementDebug.new_strategy_generated ? "yes" : "no"}
          </span>
          <span className="text-(--color-muted)">common failure step</span>
          <span className="font-medium text-(--color-ink)">
            {performance.common_failure_step ?? "—"}
          </span>
          <span className="text-(--color-muted)">last outcome</span>
          <span className="font-medium text-(--color-ink)">
            {selfImprovementDebug.last_experience?.status ?? "—"}
            {typeof selfImprovementDebug.last_experience?.final_score === "number"
              ? ` · ${selfImprovementDebug.last_experience.final_score.toFixed(2)}`
              : ""}
          </span>
        </div>

        {selfImprovementDebug.applied_strategies?.length ? (
          <div className="mt-3 rounded-xl border border-(--color-rule) bg-(--color-paper) px-3 py-3">
            <div className="mb-2 text-[10px] font-medium text-(--color-muted)">
              Applied strategies
            </div>
            <ul className="space-y-1.5 text-[11px] text-(--color-ink)">
              {selfImprovementDebug.applied_strategies.map((item, index) => (
                <li key={`${item}-${index}`}>• {item}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {selfImprovementDebug.anti_patterns?.length ? (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3">
            <div className="mb-2 text-[10px] font-medium text-amber-700">
              Anti-patterns
            </div>
            <ul className="space-y-1.5 text-[11px] text-amber-700">
              {selfImprovementDebug.anti_patterns.map((item, index) => (
                <li key={`${item}-${index}`}>• {item}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {selfImprovementDebug.strategy_lineage?.length ? (
          <div className="mt-3 rounded-xl border border-(--color-rule) bg-(--color-paper) px-3 py-3">
            <div className="mb-2 text-[10px] font-medium text-(--color-muted)">
              Strategy lineage
            </div>
            <ul className="space-y-1.5 text-[11px] text-(--color-ink)">
              {selfImprovementDebug.strategy_lineage.map((entry, index) => (
                <li key={`${entry.patch_record_id ?? entry.strategy_id ?? "lineage"}-${index}`}>
                  • {entry.patch_status ?? "unknown"} → {entry.strategy_type ?? "strategy"}
                  {entry.version ? ` · ${entry.version}` : ""}
                  {entry.source ? ` · ${entry.source}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function renderMetaDebug(metaDebug: MetaDebugData): React.ReactNode {
  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Meta debug
      </div>

      <div className="rounded-xl border border-(--color-rule) bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {metaDebug.strategy_applied ? "applied" : "not applied"}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {metaDebug.strategy_type ?? "none"}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {typeof metaDebug.confidence === "number"
              ? metaDebug.confidence.toFixed(2)
              : "—"}
          </span>
        </div>

        <div className="text-[11px] leading-5 text-(--color-ink)">
          source: {metaDebug.source ?? "none"}
        </div>

        {metaDebug.applied?.length ? (
          <div className="mt-3 rounded-xl border border-(--color-rule) bg-(--color-paper) px-3 py-3">
            <div className="mb-2 text-[10px] font-medium text-(--color-muted)">
              Applied strategies
            </div>
            <ul className="space-y-1.5 text-[11px] text-(--color-ink)">
              {metaDebug.applied.map((entry, index) => (
                <li key={`${entry.id ?? entry.strategy_type ?? "applied"}-${index}`}>
                  • {entry.strategy_type ?? "strategy"}
                  {entry.version ? ` · ${entry.version}` : ""}
                  {typeof entry.confidence === "number" ? ` · ${entry.confidence.toFixed(2)}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {metaDebug.generated?.length ? (
          <div className="mt-3 rounded-xl border border-(--color-rule) bg-(--color-paper) px-3 py-3">
            <div className="mb-2 text-[10px] font-medium text-(--color-muted)">
              Generated strategies
            </div>
            <ul className="space-y-1.5 text-[11px] text-(--color-ink)">
              {metaDebug.generated.map((entry, index) => (
                <li key={`${entry.id ?? entry.strategy_type ?? "generated"}-${index}`}>
                  • {entry.strategy_type ?? "strategy"}
                  {entry.version ? ` · ${entry.version}` : ""}
                  {typeof entry.confidence === "number" ? ` · ${entry.confidence.toFixed(2)}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {metaDebug.rolled_back?.length ? (
          <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-3">
            <div className="mb-2 text-[10px] font-medium text-red-700">
              Rolled back
            </div>
            <ul className="space-y-1.5 text-[11px] text-red-700">
              {metaDebug.rolled_back.map((entry, index) => (
                <li key={`${entry.id ?? entry.strategy_type ?? "rollback"}-${index}`}>
                  • {entry.strategy_type ?? "strategy"}{entry.reason ? ` · ${entry.reason}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function renderRewriteDebug(rewriteDebug: RewriteDebugData): React.ReactNode {
  return (
    <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs">
      <div className="mb-3 text-xs font-medium text-(--color-ink)">
        Rewrite debug
      </div>

      <div className="rounded-xl border border-(--color-rule) bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="border border-(--color-rule) bg-(--color-paper) px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            {rewriteDebug.status ?? "unknown"}
          </span>
          <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
            delta: {rewriteDebug.score_delta >= 0 ? "+" : ""}{rewriteDebug.score_delta.toFixed(2)}
          </span>
        </div>

        <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-(--color-muted)">patch generated</span>
          <span className="font-medium text-(--color-ink)">{rewriteDebug.patch_generated ? "yes" : "no"}</span>
          <span className="text-(--color-muted)">patch valid</span>
          <span className="font-medium text-(--color-ink)">{rewriteDebug.patch_valid ? "yes" : "no"}</span>
          <span className="text-(--color-muted)">sandbox applied</span>
          <span className="font-medium text-(--color-ink)">{rewriteDebug.applied_in_sandbox ? "yes" : "no"}</span>
          <span className="text-(--color-muted)">improved</span>
          <span className="font-medium text-(--color-ink)">{rewriteDebug.improved ? "yes" : "no"}</span>
        </div>
      </div>
    </div>
  );
}

export default function AgentPage() {
  const searchParams = useSearchParams();
  const debugFromQuery = searchParams.get("debug") === "1";
  const promptRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const shouldAutoScrollRef = useRef(true);
  const [mode, setMode] = useState<AgentMode>("web");
  const [kind, setKind] = useState<TaskKind>("ranking_explain");
  const [prompt, setPrompt] = useState("Explain why Oxford ranks highly");
  const [contextJson, setContextJson] = useState(
    JSON.stringify(
      { year: 2026, scope: "global", page: 1, page_size: 5, search: "Oxford" },
      null,
      2
    )
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentStatus, setAgentStatus] = useState<"checking" | "online" | "offline">(
    "checking"
  );
  const [agentHealth, setAgentHealth] = useState<AgentHealthResponse | null>(null);
  const [showDebug, setShowDebug] = useState(debugFromQuery);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [history, setHistory] = useState<RunEntry[]>([]);
  const { authenticated, refresh: refreshAuth } = useAuth();
  const [savePhase, setSavePhase] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  // Session id is stable for the lifetime of the conversation. A new UUID is
  // created when the component mounts (one per page load) or when the user
  // explicitly resets the conversation.
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const hydrated = useHydrated();

  // ?debug=1 appearing turns the debug panel on (it never turns it off). Adjusted during render when the query
  // changes, not in an effect after it.
  const [seenDebugFromQuery, setSeenDebugFromQuery] = useState(debugFromQuery);
  if (seenDebugFromQuery !== debugFromQuery) {
    setSeenDebugFromQuery(debugFromQuery);
    if (debugFromQuery) setShowDebug(true);
  }

  useEffect(() => {
    promptRef.current?.focus();
  }, []);

  // Dev mode exists only with the debug panel open: closing the panel moves back to web mode in the same render.
  // Guarded by the condition it clears, so it settles after one pass.
  if (!showDebug && mode === "dev") {
    setMode("web");
    if (kind === "dev_refinement") {
      setKind("ranking_explain");
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        const res = await fetch("/api/agent/health", {
          cache: "no-store",
        });
        const json = (await res.json()) as AgentHealthResponse;

        if (cancelled) {
          return;
        }

        setAgentHealth(json);
        setAgentStatus(res.ok && json.success ? "online" : "offline");
      } catch {
        if (!cancelled) {
          setAgentHealth({
            success: false,
            status: "offline",
            error: "Failed to reach agent API",
          });
          setAgentStatus("offline");
        }
      }
    }

    void checkHealth();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!shouldAutoScrollRef.current) {
      return;
    }

    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    promptRef.current?.focus();
  }, [history.length, loading]);

  function handleHistoryScroll() {
    const el = scrollContainerRef.current;
    if (!el) {
      return;
    }

    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    shouldAutoScrollRef.current = distanceFromBottom < 120;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setError("Please enter a task.");
      return;
    }

    setLoading(true);
    setError(null);
    shouldAutoScrollRef.current = true;

    const entryId = crypto.randomUUID();
    const pendingEntry: RunEntry = {
      id: entryId,
      mode,
      kind,
      prompt: trimmedPrompt,
      response: null,
      error: null,
    };
    setHistory((current) => [...current, pendingEntry]);
    // The saved copy no longer matches what is on screen.
    setSavePhase("idle");
    setSaveError(null);

    try {
      const res = await fetch("/api/agent/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: trimmedPrompt,
          session_id: sessionId,
        }),
      });

      const json = (await res.json()) as AgentResponse;
      const formattedError =
        json.data?.data?.explanation ??
        json.data?.message ??
        json.error ??
        "Agent request failed.";
      const nextEntry: RunEntry = {
        id: entryId,
        mode,
        kind,
        prompt: trimmedPrompt,
        response: json,
        error: !res.ok || !json.success ? formattedError : null,
      };

      setHistory((current) =>
        current.map((entry) => (entry.id === entryId ? nextEntry : entry))
      );
      if (!res.ok || !json.success) {
        setError(nextEntry.error);
      } else {
        setAgentStatus("online");
      }
    } catch {
      const nextEntry: RunEntry = {
        id: entryId,
        mode,
        kind,
        prompt: trimmedPrompt,
        response: null,
        error: "Failed to reach /api/agent/chat",
      };
      setHistory((current) =>
        current.map((entry) => (entry.id === entryId ? nextEntry : entry))
      );
      setError(nextEntry.error);
      setAgentStatus("offline");
    } finally {
      setLoading(false);
    }
  }

  function resetSession() {
    shouldAutoScrollRef.current = true;
    setHistory([]);
    setError(null);
    setSessionId(crypto.randomUUID());
    setSavePhase("idle");
    setSaveError(null);
  }

  async function handleSaveConversation() {
    const turns = buildConversationTurns(history);
    if (turns.length === 0) {
      return;
    }

    setSavePhase("saving");
    setSaveError(null);

    // No title: the API derives one from the opening question, so saving never
    // has to interrupt the user for a name.
    const result = await saveConversation(sessionId, turns);
    if (result.ok) {
      setSavePhase("saved");
      return;
    }

    // The API's own message is the useful one for a rejected transcript
    // ("Conversation is too long. Limit is 200 turns."), so surface it rather
    // than flattening every failure into "could not save".
    setSaveError(result.message);
    setSavePhase("error");
    if (result.reason === "unauthenticated") {
      void refreshAuth();
    }
  }

  /**
   * Puts a stored transcript back on screen so the user can carry on from it.
   *
   * The session id is adopted along with the turns. Without that, continuing a
   * restored chat and saving again would create a second row rather than
   * updating the one the user just loaded.
   */
  function handleLoadConversation(detail: ConversationDetail) {
    const restored = runEntriesFromTurns(detail.turns, () => crypto.randomUUID());

    setHistory(
      restored.map((entry) => ({
        id: entry.id,
        // Neither mode nor kind is stored: they describe how a request was
        // routed, not what was said, and only surface behind the debug toggle.
        mode: "web" as AgentMode,
        kind: "data_query" as TaskKind,
        prompt: entry.prompt,
        response: entry.restoredReply
          ? ({
              success: true,
              data: {
                taskId: entry.id,
                status: "restored",
                message: "Restored from a saved conversation",
                data: {
                  explanation: entry.restoredReply,
                  explanationParagraphs: entry.restoredReply
                    .split(SPLIT_PARAGRAPHS)
                    .map((part) => part.trim())
                    .filter(Boolean),
                },
                traces: [],
                warnings: [],
              },
            } as AgentResponse)
          : null,
        // A turn saved mid-flight has no reply. Saying so beats the pending
        // branch, which would show a "generating..." spinner that never resolves.
        error: entry.restoredReply ? null : "No reply was stored for this turn.",
      }))
    );

    setSessionId(detail.sessionId);
    setError(null);
    // What is on screen is exactly what is stored, so offering to save it again
    // would be busywork until the user adds a turn.
    setSavePhase("saved");
    setSaveError(null);
    shouldAutoScrollRef.current = true;
  }

  function applyQuickTask(task: (typeof QUICK_TASKS)[number]) {
    setMode(task.mode);
    setKind(task.kind);
    setPrompt(task.prompt);
    setContextJson(task.context);
    setError(null);
  }

  function applySuggestedPrompt(nextPrompt: string) {
    setMode("web");
    setKind("data_query");
    setPrompt(nextPrompt);
    setContextJson("{}");
    setError(null);
    promptRef.current?.focus();
  }

  function handlePromptChange(nextPrompt: string) {
    setPrompt(nextPrompt);
    setContextJson((current) => stripPromptBoundContext(current));
  }

  function handlePromptKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) {
      return;
    }

    event.preventDefault();

    if (loading) {
      return;
    }

    void handleSubmit(event as unknown as React.FormEvent);
  }

  const latest = history.length > 0 ? history[history.length - 1] : null;
  const friendlyError = getFriendlyError(error);
  const visibleQuickTasks = useMemo(
    () => QUICK_TASKS.filter((task) => showDebug || task.mode === "web"),
    [showDebug]
  );
  const promptPlaceholder = PROMPT_HINTS[kind];

  return (
    <main className="min-h-screen bg-(--color-paper) text-(--color-ink)">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
        <header className="mb-6 flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div
              className={`rounded-full border px-3 py-1 text-sm ${
                agentStatus === "online"
                  ? "border-(--color-rule) bg-(--color-paper) text-(--color-ink)"
                  : agentStatus === "offline"
                    ? "border-(--color-error-soft) bg-(--color-plate) text-(--color-error)"
                    : "border-(--color-rule) bg-white text-(--color-muted)"
              }`}
            >
              agent: {agentStatus}
            </div>
            <div className="border border-(--color-rule) bg-white px-3 py-1 text-xs font-semibold text-(--color-muted)">
              provider: {agentHealth?.generation?.providerLabel ?? "mock"}
            </div>
              {showDebug ? (
                <>
                  <div className="border border-(--color-rule) bg-white px-3 py-1 text-xs font-semibold text-(--color-muted)">
                    readonly
                  </div>
                <div className="border border-(--color-rule) bg-white px-3 py-1 text-sm text-(--color-ink)">
                  Chat route does not execute tools
                </div>
              </>
            ) : null}
            <button
              type="button"
              onClick={() => setShowDebug((current) => !current)}
              className={`rounded-full border px-3 py-1 text-sm transition ${
                showDebug
                  ? "border-(--color-ink) bg-(--color-ink) text-white"
                  : "border-(--color-rule) bg-white text-(--color-muted)"
              }`}
            >
              debug: {showDebug ? "on" : "off"}
            </button>
            {authenticated ? (
              <button
                type="button"
                onClick={() => setHistoryOpen(true)}
                className="border border-(--color-rule) bg-white px-3 py-1 text-sm text-(--color-muted) transition hover:border-(--color-ink-2) hover:text-(--color-ink)"
              >
                History
              </button>
            ) : null}
            {history.length > 0 ? (
              <button
                type="button"
                onClick={handleSaveConversation}
                disabled={!authenticated || savePhase === "saving" || savePhase === "saved"}
                title={
                  authenticated
                    ? "Store this transcript on your account"
                    : "Sign in to keep this conversation"
                }
                className={`rounded-full border px-3 py-1 text-sm transition disabled:cursor-not-allowed ${
                  savePhase === "saved"
                    ? "border-(--color-ink-2) bg-(--color-paper-2) text-(--color-ink)"
                    : "border-(--color-rule) bg-white text-(--color-muted) hover:border-(--color-ink-2) hover:text-(--color-ink) disabled:opacity-50"
                }`}
              >
                {!authenticated
                  ? AUTH_MESSAGES.signInToSave
                  : savePhase === "saving"
                    ? AUTH_MESSAGES.saving
                    : savePhase === "saved"
                      ? AUTH_MESSAGES.saved
                      : "Save conversation"}
              </button>
            ) : null}
            {history.length > 0 ? (
              <button
                type="button"
                onClick={resetSession}
                disabled={loading}
                className="border border-(--color-rule) bg-white px-3 py-1 text-sm text-(--color-muted) transition hover:border-(--color-error) hover:text-(--color-error) disabled:cursor-not-allowed disabled:opacity-50"
              >
                New conversation
              </button>
            ) : null}
            {savePhase === "error" && saveError ? (
              <span
                role="status"
                className="border border-(--color-error) bg-(--color-paper) px-3 py-1 text-sm text-(--color-error)"
              >
                {saveError}
              </span>
            ) : null}
          </div>
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-(--color-ink)">
              CrawlerNest Agent
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-(--color-muted)">
              Ask for a ranking explanation, a university lookup, or a maintenance
              question. Agent responses are advisory only. They do not modify
              CrawlerNest.
            </p>
          </div>
        </header>

        <section className="mb-4 flex flex-wrap gap-2">
          {visibleQuickTasks.map((task) => (
            <button
              key={task.label}
              type="button"
              onClick={() => applyQuickTask(task)}
              disabled={loading}
              className="border border-(--color-rule) bg-white px-4 py-2 text-sm text-(--color-ink) transition hover:bg-(--color-paper-2)"
            >
              {task.label}
            </button>
          ))}
        </section>

        {agentStatus === "offline" ? (
          <section className="mb-4 border border-(--color-error-soft) bg-(--color-plate) px-5 py-4 text-sm text-(--color-error)">
            <div className="font-semibold text-(--color-error)">Agent chat route unavailable</div>
            <p className="mt-2 leading-6">
              The page is ready, but the local Next.js chat bridge did not respond.
              Check the dev server and provider configuration, then try again.
            </p>
          </section>
        ) : null}

        <section className="mb-4 border border-(--color-rule) bg-white px-5 py-4 text-sm shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs font-semibold text-(--color-muted)">
                Demo Ready Information
              </div>
              <div className="mt-2 text-base font-semibold text-(--color-ink)">
                Advisory model surface for competition demos
              </div>
              <p className="mt-1 max-w-3xl leading-6 text-(--color-muted)">
                Intended use: explain rankings, recommendations, analytics caveats,
                source freshness, and debugging direction without changing CrawlerNest.
              </p>
            </div>
            <div className="grid gap-2 text-xs sm:grid-cols-2">
              <span className="border border-(--color-rule) bg-(--color-paper) px-3 py-1 text-(--color-ink)">
                provider: {agentHealth?.generation?.providerLabel ?? "mock"}
              </span>
              <span className="border border-(--color-rule) bg-(--color-paper) px-3 py-1 text-(--color-ink-2)">
                readonly
              </span>
              <span className="border border-(--color-rule) bg-(--color-paper) px-3 py-1 text-(--color-ink)">
                advisory-only
              </span>
              {/* Was "no tool calling", which stopped being true when this
                  page's route gained its engine pass: it calls ranking_tools
                  and reads the warehouse. The boundary that still holds is
                  that the read is the only thing it does. */}
              <span className="border border-(--color-rule) bg-(--color-paper) px-3 py-1 text-(--color-ink)">
                readonly warehouse reads
              </span>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-(--color-muted)">
            {AGENT_DEMO_RUBRIC.requiredBoundary.map((boundary) => (
              <span key={boundary} className="bg-(--color-paper) px-2.5 py-1">
                {boundary}
              </span>
            ))}
          </div>
        </section>

        <section className="flex-1 border border-(--color-rule) bg-white shadow-sm">
          {showDebug || loading ? (
            <div className="border-b border-(--color-rule) px-6 py-4">
              <div className="flex flex-wrap items-center gap-3 text-sm text-(--color-muted)">
                {showDebug ? (
                  <>
                    <span className="bg-(--color-paper) px-3 py-1 text-(--color-ink)">
                      mode: {mode}
                    </span>
                    <span className="bg-(--color-paper) px-3 py-1 text-(--color-ink)">
                      kind: {kind}
                    </span>
                  </>
                ) : null}
                {loading ? (
                  <span className="bg-(--color-paper-2) px-3 py-1 text-(--color-ink)">
                    running...
                  </span>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="grid min-h-[520px] lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="flex min-h-[520px] flex-col">
              <div
                ref={scrollContainerRef}
                onScroll={handleHistoryScroll}
                className="flex-1 space-y-4 overflow-y-auto px-6 py-6"
              >
                {history.length === 0 ? (
                  <div className="border border-dashed border-(--color-rule) bg-(--color-paper) px-5 py-6 text-sm text-(--color-muted)">
                    Start with a quick task above, or type your own request below.
                    The first response will appear here.
                  </div>
                ) : null}

                {history.map((entry, historyIndex) => (
                  <div key={entry.id} className="space-y-3">
                    <div className="ml-auto max-w-3xl bg-(--color-ink) px-5 py-4 text-white">
                      <div className="flex items-center justify-between gap-3">
                        {showDebug ? (
                          <div className="text-xs text-white/70">
                            {entry.mode} · {entry.kind}
                          </div>
                        ) : null}
                        {history.length > 1 ? (
                          <div className="ml-auto text-[10px] text-white/50">
                            turn {historyIndex + 1}
                          </div>
                        ) : null}
                      </div>
                      <div className={`text-sm leading-6 ${showDebug || history.length > 1 ? "mt-2" : ""}`}>{entry.prompt}</div>
                    </div>

                    {(() => {
                      if (entry.response === null && !entry.error) {
                        return (
                          <div
                            className={`max-w-4xl border bg-(--color-paper) px-5 py-4 transition ${
                              entry.id === latest?.id
                                ? "border-(--color-rule) shadow-[0_0_0_2px_rgba(26,61,46,0.06)]"
                                : "border-(--color-rule)"
                            }`}
                          >
                            <div className="flex items-center gap-3 text-sm text-(--color-ink)">
                              <span className="h-2 w-2 animate-pulse bg-(--color-ink)" />
                              <span>Agent is generating...</span>
                            </div>
                          </div>
                        );
                      }

                      const isDevMode = entry.mode === "dev";
                      const formatted = entry.response?.data?.data;
                      // Web branch: these are only meaningful when isDevMode is false (formatter shape)
                      const paragraphs =
                        !isDevMode && formatted?.explanationParagraphs && formatted.explanationParagraphs.length > 0
                          ? formatted.explanationParagraphs
                          : !isDevMode && formatted?.explanation
                            ? [formatted.explanation]
                            : [];
                      const items = !isDevMode ? (formatted?.items ?? []) : [];
                      const meta = !isDevMode ? (formatted?.meta ?? {}) : {};
                      const generationSource =
                        !isDevMode && typeof meta.generationSource === "string"
                          ? meta.generationSource
                          : null;
                      const modelName =
                        !isDevMode && typeof meta.modelName === "string"
                          ? meta.modelName
                          : null;
                      const traces = entry.response?.data?.traces ?? [];
                      const warnings = entry.response?.data?.warnings ?? [];
                      const taskId = entry.response?.data?.taskId;
                      const status = entry.response?.data?.status;
                      const validationSummary =
                        isDevMode && formatted
                          ? extractValidationSummary(
                              formatted as Record<string, unknown>
                            )
                          : null;

                      return (
                        <div
                          className={`max-w-4xl border bg-(--color-paper) px-5 py-4 transition ${
                            entry.id === latest?.id
                              ? "border-(--color-rule) shadow-[0_0_0_2px_rgba(26,61,46,0.06)]"
                              : "border-(--color-rule)"
                          }`}
                        >
                      {isDevMode ? (
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="border border-(--color-rule) bg-white px-2 py-0.5 text-[10px] text-(--color-muted)">
                                dev
                              </span>
                              <span className="border border-(--color-rule) bg-white px-2 py-0.5 text-[10px] text-(--color-muted)">
                                {entry.kind.replace(/_/g, " ")}
                              </span>
                            </div>
                            <div className="mt-2 text-sm font-semibold text-(--color-ink)">
                              {entry.response?.data?.message ?? "Dev agent response"}
                            </div>
                          </div>
                          <div className="shrink-0 bg-white px-3 py-1 text-xs font-medium text-(--color-muted)">
                            {entry.response?.data?.status ?? "error"}
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-(--color-ink)">
                              {formatted?.title ?? entry.response?.data?.message ?? "Agent response"}
                            </div>
                            {showDebug && generationSource ? (
                              <div className="mt-2 flex flex-wrap items-center gap-2">
                                <span
                                  className={` border px-2.5 py-0.5 text-[10px] ${
                                    generationSource === "llm"
                                      ? "border-(--color-rule) bg-(--color-paper) text-(--color-ink-2)"
                                      : "border-(--color-warn-soft) bg-(--color-plate) text-(--color-warn)"
                                  }`}
                                >
                                  {generationSource}
                                </span>
                                {modelName ? (
                                  <span className="border border-(--color-rule) bg-white px-2.5 py-0.5 text-[10px] text-(--color-muted)">
                                    {modelName}
                                  </span>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                          <div className="bg-white px-3 py-1 text-xs font-medium text-(--color-muted)">
                            {entry.response?.data?.status ?? "error"}
                          </div>
                        </div>
                      )}

                      {entry.error ? (
                        <div className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                          {entry.error}
                        </div>
                      ) : null}

                          {isDevMode ? (
                            // Dev render branch — engineering-facing structured output.
                            // Never attempts to extract formatter fields (title/explanation/items/meta).
                            <div className="mt-4 space-y-3">

                              {/* ── Execution plan ── */}
                              {traces.length > 0 ? (
                                <div className="border border-(--color-rule) bg-white px-5 py-4">
                                  <div className="mb-3 text-xs text-(--color-muted)">
                                    Execution plan
                                  </div>
                                  <ol className="overflow-hidden rounded-xl border border-(--color-rule)">
                                    {traces.map((trace, traceIndex) => {
                                      const stepLabel =
                                        typeof trace.step === "string"
                                          ? toTitleCase(trace.step)
                                          : JSON.stringify(trace.step);
                                      const owner =
                                        typeof trace.owner === "string" ? trace.owner : null;
                                      return (
                                        <li
                                          key={traceIndex}
                                          className={`flex items-start gap-3 px-4 py-3 ${
                                            traceIndex > 0 ? "border-t border-(--color-rule)" : ""
                                          }`}
                                        >
                                          <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center border border-(--color-rule) bg-(--color-paper) text-[10px] font-semibold text-(--color-ink)">
                                            {traceIndex + 1}
                                          </div>
                                          <div className="min-w-0 flex-1">
                                            <div className="text-sm font-medium text-(--color-ink)">
                                              {stepLabel}
                                            </div>
                                            {owner ? (
                                              <div className="mt-0.5 text-xs text-(--color-muted)">
                                                {owner}
                                              </div>
                                            ) : null}
                                          </div>
                                        </li>
                                      );
                                    })}
                                  </ol>
                                </div>
                              ) : null}

                              {/* ── Validation Summary ── */}
                              {validationSummary !== null
                                ? renderValidationSummary(validationSummary)
                                : null}

                              {/* ── Structured output ── */}
                              <div className="border border-(--color-rule) bg-white px-5 py-4">
                                <div className="mb-4 text-xs text-(--color-muted)">
                                  Structured output
                                </div>
                                {formatted && Object.keys(formatted as Record<string, unknown>).length > 0 ? (
                                  <div className="space-y-5">
                                    {Object.entries(formatted as Record<string, unknown>).map(
                                      ([key, value]) => {
                                        const rendered = renderDevField(key, value);
                                        if (rendered === null) return null;
                                        return (
                                          <div key={key}>
                                            <div className="mb-1.5 text-[10px] text-(--color-muted)">
                                              {toTitleCase(key)}
                                            </div>
                                            {rendered}
                                          </div>
                                        );
                                      }
                                    )}
                                  </div>
                                ) : (
                                  <p className="text-xs text-(--color-muted)">No output data.</p>
                                )}
                              </div>

                              {/* ── Warnings ── */}
                              {warnings.length > 0 ? (
                                <div className="border border-(--color-warn-soft) bg-(--color-plate) px-5 py-4">
                                  <div className="mb-2 text-xs text-(--color-muted)">
                                    Warnings
                                  </div>
                                  <ul className="space-y-1.5">
                                    {warnings.map((w) => (
                                      <li key={w} className="flex items-start gap-2 text-xs text-(--color-warn)">
                                        <span className="mt-0.5 shrink-0 text-(--color-warn)">▲</span>
                                        {w}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ) : (
                                <div className="flex items-center gap-2 border border-(--color-rule) bg-white px-5 py-3">
                                  <span className="h-1.5 w-1.5 bg-(--color-paper-3)" />
                                  <span className="text-xs text-(--color-muted)">No warnings</span>
                                </div>
                              )}
                            </div>
                          ) : (
                            // Web render branch — formatter output only.
                            // Reads only from the formatter-shaped payload: explanation, items, meta.
                            // Never touches raw backend data directly.
                            //
                            // The one exception is `warnings`, which is a
                            // response-level field the formatter deliberately
                            // does not carry: QueryFormatter builds a fresh
                            // dict and drops anything it does not recognise,
                            // caveats included. A disclosure the backend
                            // attached — the year the answer actually
                            // describes, for one — has no other route to this
                            // branch, and it was reaching the dev panel only.
                            <div className="mt-4 bg-white px-5 py-4">
                              <AgentWarningBanner warnings={warnings} />

                              <div className="space-y-3 text-sm leading-7 text-(--color-ink)">
                                {paragraphs.map((paragraph) => (
                                  <p key={paragraph}>{paragraph}</p>
                                ))}
                              </div>

                              {items.length > 0 ? (
                                <div className="mt-4 overflow-hidden rounded-2xl border border-(--color-rule) bg-(--color-paper)">
                                  {items.map((item, index) => (
                                    <div
                                      key={`${item.kind ?? "item"}-${item.label}`}
                                      className={`flex items-start gap-3 px-4 py-3 text-sm ${
                                        index > 0 ? "border-t border-(--color-rule)" : ""
                                      }`}
                                    >
                                      {item.kind ? (
                                        <span className="mt-0.5 shrink-0 border border-(--color-rule) bg-white px-2 py-0.5 text-[10px] text-(--color-muted)">
                                          {item.kind}
                                        </span>
                                      ) : null}
                                      <div className="min-w-0 flex-1">
                                        <div className="font-medium text-(--color-ink)">{item.label}</div>
                                        {item.description ? (
                                          <div className="mt-0.5 text-xs leading-5 text-(--color-muted)">
                                            {item.description}
                                          </div>
                                        ) : null}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              ) : null}

                              {Object.keys(meta).length > 0 ? (
                                <div className="mt-4 rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4">
                                  <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
                                    {Object.entries(meta).map(([key, value]) => (
                                      <div key={key} className="contents">
                                        <span className="text-(--color-muted)">{key}</span>
                                        <span className="font-medium text-(--color-ink)">
                                          {typeof value === "object" && value !== null
                                            ? JSON.stringify(value)
                                            : String(value ?? "")}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          )}

                          {showDebug ? (
                            <details className="mt-4 rounded-2xl bg-white" open>
                              <summary className="cursor-pointer px-4 py-3 text-xs font-medium text-(--color-muted)">
                                Debug details
                              </summary>
                              <div className="space-y-4 border-t border-(--color-rule) p-4">
                                {!isDevMode ? (
                                  <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs text-(--color-muted)">
                                    <div className="font-medium text-(--color-ink)">Generation</div>
                                    <pre className="mt-2 overflow-x-auto">
                                      {JSON.stringify(
                                        {
                                          generationSource,
                                          modelName,
                                        },
                                        null,
                                        2
                                      )}
                                    </pre>
                                  </div>
                                ) : null}

                                {!isDevMode && formatted?.referenceDebug
                                  ? renderReferenceDebug(formatted.referenceDebug)
                                  : null}

                                {!isDevMode && formatted?.policyDebug
                                  ? renderPolicyDebug(formatted.policyDebug)
                                  : null}

                                {formatted?.metaDebug
                                  ? renderMetaDebug(formatted.metaDebug)
                                  : null}

                                {formatted?.rewriteDebug
                                  ? renderRewriteDebug(formatted.rewriteDebug)
                                  : null}

                                {!isDevMode && formatted?.orchestrationDebug
                                  ? renderOrchestrationDebug(formatted.orchestrationDebug)
                                  : null}

                                {!isDevMode && formatted?.longTermMemoryDebug
                                  ? renderLongTermMemoryDebug(formatted.longTermMemoryDebug)
                                  : null}

                                {formatted?.selfImprovementDebug
                                  ? renderSelfImprovementDebug(formatted.selfImprovementDebug)
                                  : null}

                                {!isDevMode && formatted?.groundingDebug
                                  ? renderGroundingDebug(formatted.groundingDebug)
                                  : null}

                                {/* Memory debug — only present when debug=true and generation ran */}
                                {!isDevMode && formatted?.memoryDebug
                                  ? renderMemoryDebug(formatted.memoryDebug)
                                  : null}

                                <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs text-(--color-muted)">
                                  <div className="font-medium text-(--color-ink)">Task info</div>
                                  <pre className="mt-2 overflow-x-auto">{JSON.stringify({ taskId, status }, null, 2)}</pre>
                                </div>

                                <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs text-(--color-muted)">
                                  <div className="font-medium text-(--color-ink)">Warnings</div>
                                  <pre className="mt-2 overflow-x-auto">{JSON.stringify(warnings, null, 2)}</pre>
                                </div>

                                <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs text-(--color-muted)">
                                  <div className="font-medium text-(--color-ink)">Raw trace data</div>
                                  <pre className="mt-2 overflow-x-auto">{JSON.stringify(traces, null, 2)}</pre>
                                </div>

                                <div className="rounded-2xl border border-(--color-rule) bg-(--color-paper) p-4 text-xs text-(--color-muted)">
                                  <div className="font-medium text-(--color-ink)">Raw response</div>
                                  <pre className="mt-2 overflow-x-auto">{formatResponse(entry.response)}</pre>
                                </div>
                              </div>
                            </details>
                          ) : null}
                        </div>
                      );
                    })()}
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>

              <div className="border-t border-(--color-rule) bg-white px-6 py-5">
                {friendlyError ? (
                  <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <div className="font-medium">{friendlyError}</div>
                    {showDebug && friendlyError !== error ? (
                      <div className="mt-2 text-xs text-red-600">
                        Raw error: {error}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                <form onSubmit={handleSubmit} className="space-y-4">
                  <textarea
                    ref={promptRef}
                    value={prompt}
                    onChange={(event) => handlePromptChange(event.target.value)}
                    onKeyDown={handlePromptKeyDown}
                    rows={4}
                    placeholder={promptPlaceholder}
                    className="w-full border border-(--color-rule) bg-(--color-paper) px-5 py-4 text-sm outline-none transition focus:border-(--color-ink)"
                  />

                  <div className="text-xs text-(--color-muted)">
                    Press <span className="font-medium text-(--color-ink)">Enter</span> to send.
                    Use <span className="font-medium text-(--color-ink)">Shift + Enter</span> for a new line.
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {showDebug ? (
                        <>
                          <select
                            value={mode}
                            onChange={(event) => setMode(event.target.value as AgentMode)}
                            className="border border-(--color-rule) bg-white px-4 py-2 text-sm text-(--color-ink) outline-none"
                          >
                            <option value="web">web</option>
                            <option value="dev">dev</option>
                          </select>

                          <select
                            value={kind}
                            onChange={(event) => setKind(event.target.value as TaskKind)}
                            className="border border-(--color-rule) bg-white px-4 py-2 text-sm text-(--color-ink) outline-none"
                          >
                            {TASK_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>

                          <button
                            type="button"
                            onClick={() => setShowAdvanced((current) => !current)}
                            className="border border-(--color-rule) bg-white px-4 py-2 text-sm text-(--color-ink) transition hover:bg-(--color-paper-2)"
                          >
                            {showAdvanced ? "Hide context" : "Context"}
                          </button>
                        </>
                      ) : null}
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="bg-(--color-ink) px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-(--color-ink-2) disabled:cursor-not-allowed disabled:bg-(--color-paper-3)"
                    >
                      {loading ? "Generating..." : "Send"}
                    </button>
                  </div>

                  {showDebug && showAdvanced ? (
                    <div className="border border-(--color-rule) bg-(--color-paper) p-4">
                      <div className="mb-2 text-xs text-(--color-muted)">
                        Context JSON
                      </div>
                      <textarea
                        value={contextJson}
                        onChange={(event) => setContextJson(event.target.value)}
                        rows={8}
                        className="w-full rounded-xl border border-(--color-rule) bg-white px-4 py-3 font-mono text-xs outline-none transition focus:border-(--color-ink)"
                      />
                    </div>
                  ) : null}
                </form>
              </div>
            </div>

            <aside className="border-t border-(--color-rule) bg-(--color-paper) px-6 py-6 lg:border-l lg:border-t-0">
              <div className="border border-(--color-rule) bg-white p-4">
                <div className="text-xs text-(--color-muted)">
                  Good first prompts
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-sm text-(--color-ink)">
                  {visibleQuickTasks.map((task) => (
                    <button
                      key={`hint-${task.label}`}
                      type="button"
                      onClick={() => applyQuickTask(task)}
                      disabled={loading}
                      className="border border-(--color-rule) bg-(--color-paper) px-3 py-1.5 text-left text-sm text-(--color-ink) transition hover:bg-(--color-paper-2) disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {task.prompt}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-6 border border-(--color-rule) bg-white p-4">
                <div className="text-xs text-(--color-muted)">
                  Suggested prompts
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-sm text-(--color-ink)">
                  {AGENT_SUGGESTED_PROMPTS.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => applySuggestedPrompt(suggestion)}
                      disabled={loading}
                      className="border border-(--color-rule) bg-(--color-paper) px-3 py-1.5 text-left text-sm text-(--color-ink) transition hover:bg-(--color-paper-2) disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-6 border border-(--color-rule) bg-white p-4">
                <div className="text-xs text-(--color-muted)">
                  Capability boundary
                </div>
                <div className="mt-3 grid gap-4 text-sm leading-6 sm:grid-cols-2 lg:grid-cols-1">
                  <div>
                    <div className="font-medium text-(--color-ink)">Agent can</div>
                    <ul className="mt-2 space-y-1 text-(--color-muted)">
                      {AGENT_CAPABILITIES.map((capability) => (
                        <li key={capability}>- {capability}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="font-medium text-(--color-error)">Agent cannot</div>
                    <ul className="mt-2 space-y-1 text-(--color-muted)">
                      {AGENT_LIMITATIONS.map((limitation) => (
                        <li key={limitation}>- {limitation}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {showDebug ? (
                <>
                  <div className="mt-6">
                    <h2 className="text-lg font-semibold text-(--color-ink)">How it works</h2>
                    <div className="mt-4 space-y-3 text-sm leading-6 text-(--color-muted)">
                      <p>1. This page sends a readonly chat message to <code>/api/agent/chat</code>.</p>
                      <p>2. The server-side provider bridge selects mock, Ollama, or OpenAI.</p>
                      <p>3. The bridge returns advisory text only; it does not run tools.</p>
                      <p>4. No shell commands, DB writes, pipeline runs, or repo edits are performed.</p>
                    </div>
                  </div>

                  <div className="mt-6 border border-(--color-rule) bg-white p-4">
                    <div className="text-xs text-(--color-muted)">
                      Generation status
                    </div>
                    <div className="mt-3 space-y-2 text-sm text-(--color-ink)">
                      <p>
                        Provider:{" "}
                        <span className="font-medium">
                          {agentHealth?.generation?.providerLabel ?? "fallback only"}
                        </span>
                      </p>
                      <p>
                        Model:{" "}
                        <span className="font-medium">
                          {agentHealth?.generation?.modelName ?? "not configured"}
                        </span>
                      </p>
                      <p>
                        Endpoint:{" "}
                        <span className="font-medium break-all">
                          {agentHealth?.generation?.baseUrl ?? "not configured"}
                        </span>
                      </p>
                      {agentHealth?.generation?.reason ? (
                        <p className="text-(--color-muted)">{agentHealth.generation.reason}</p>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-6 border border-(--color-rule) bg-white p-4">
                    <div className="text-xs text-(--color-muted)">
                      Provider setup
                    </div>
                    <pre className="mt-3 overflow-x-auto rounded-xl bg-(--color-paper) px-4 py-3 text-xs text-(--color-ink)">
                      AGENT_MODEL_PROVIDER=mock npm run dev
                    </pre>
                  </div>

                  <div className="mt-6 border border-(--color-rule) bg-white p-4">
                    <div className="text-xs text-(--color-muted)">
                      Latest task
                    </div>
                    <div className="mt-3 text-sm text-(--color-muted)">
                      {latest ? (
                        <>
                          <p className="font-medium text-(--color-ink)">{latest.prompt}</p>
                          <p className="mt-2">
                            {latest.response?.data?.status ?? "error"} · {latest.kind}
                          </p>
                        </>
                      ) : (
                        <p>No tasks yet.</p>
                      )}
                    </div>
                  </div>

                  <div className="mt-6 border border-(--color-rule) bg-white p-4">
                    <div className="text-xs text-(--color-muted)">
                      Conversation session
                    </div>
                    <div className="mt-3 space-y-2 text-xs text-(--color-muted)">
                      <p>
                        Session:{" "}
                        <span className="font-mono font-medium text-(--color-ink)">
                          {/* The id is generated separately on the server and in the browser, so it is shown
                              only once hydrated; the server's is never sent anywhere. */}
                          {hydrated ? `${sessionId.slice(0, 8)}…` : "…"}
                        </span>
                      </p>
                      <p>
                        Turns:{" "}
                        <span className="font-medium text-(--color-ink)">
                          {history.length}
                        </span>
                      </p>
                      <button
                        type="button"
                        onClick={resetSession}
                        disabled={loading}
                        className="mt-1 border border-(--color-rule) bg-(--color-paper) px-3 py-1 text-xs text-(--color-muted) transition hover:border-(--color-error) hover:text-(--color-error) disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Reset session
                      </button>
                    </div>
                  </div>
                </>
              ) : null}
            </aside>
          </div>
        </section>
      </div>

      {historyOpen ? (
        <ConversationHistoryPanel
          onClose={() => setHistoryOpen(false)}
          onLoad={handleLoadConversation}
          onSessionExpired={() => void refreshAuth()}
          activeSessionId={sessionId}
        />
      ) : null}
    </main>
  );
}
