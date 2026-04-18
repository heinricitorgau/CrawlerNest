"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

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

const AGENT_START_COMMAND =
  "python3 -m crawlernest.interfaces.api.agent_api --host 127.0.0.1 --port 8090";

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
  {
    label: "Refine Extractor",
    mode: "dev",
    kind: "dev_refinement",
    prompt: "Improve THE extractor failure handling",
    context: JSON.stringify(
      { target: "the_extractor", notes: ["focus on parse stability"] },
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
    error.includes("Failed to reach /api/agent/tasks") ||
    error.includes("Failed to reach agent API")
  ) {
    return "Agent service is offline. Start the Python agent API, then try again.";
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
    return <span className="text-[#6b7068] italic">null</span>;
  }
  if (typeof value === "boolean") {
    return (
      <span className={value ? "font-mono text-[#1a6b3a]" : "font-mono text-[#a33a3a]"}>
        {String(value)}
      </span>
    );
  }
  if (typeof value === "number") {
    return <span className="font-mono text-[#1a3d2e]">{String(value)}</span>;
  }
  if (typeof value === "string") {
    return <span className="text-[#1a1a1a]">{value}</span>;
  }
  if (Array.isArray(value)) {
    const isSimple = value.every((v) => typeof v === "string" || typeof v === "number");
    if (isSimple) {
      return (
        <div className="flex flex-wrap gap-1.5">
          {value.map((item, i) => (
            <span
              key={i}
              className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-xs text-[#1a1a1a]"
            >
              {String(item)}
            </span>
          ))}
        </div>
      );
    }
    return (
      <pre className="overflow-x-auto rounded-xl bg-[#f0ede8] px-3 py-2 text-xs leading-5 text-[#1a1a1a]">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  if (typeof value === "object") {
    if (depth >= 2) {
      return (
        <pre className="overflow-x-auto rounded-xl bg-[#f0ede8] px-3 py-2 text-xs leading-5 text-[#1a1a1a]">
          {JSON.stringify(value, null, 2)}
        </pre>
      );
    }
    return (
      <div className="space-y-3">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k}>
            <div className="mb-1 text-[10px] uppercase tracking-[0.14em] text-[#6b7068]">
              {toTitleCase(k)}
            </div>
            {renderStructuredValue(v, depth + 1)}
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-[#6b7068]">{String(value)}</span>;
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
      <div className="rounded-xl bg-[#faf8f4] px-4 py-3 text-sm leading-6 text-[#1a1a1a]">
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
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[#d8d3cb] bg-[#faf8f4] font-mono text-[10px] text-[#6b7068]">
              {i + 1}
            </span>
            <span
              className={`rounded-lg border px-3 py-1 text-xs ${
                i === stages.length - 1
                  ? "border-[#cfe5d7] bg-[#edf7f1] text-[#1a3d2e]"
                  : "border-[#e0ddd8] bg-white text-[#1a1a1a]"
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
        ? { text: "text-[#1a6b3a]", bg: "bg-[#edf7f1]", border: "border-[#cfe5d7]" }
        : pct >= 40
          ? { text: "text-[#7c5c1a]", bg: "bg-[#fffbf4]", border: "border-[#f0d8b8]" }
          : { text: "text-[#a33a3a]", bg: "bg-[#fff4f4]", border: "border-[#f0caca]" };
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
        <div className="rounded-xl border border-[#d8d3cb] bg-[#faf8f4] px-4 py-3 text-sm leading-6 text-[#1a1a1a]">
          {value}
        </div>
      );
    }
  }

  // ── file_patch: dark monospaced block — visually distinct from prose ──────
  if (key === "file_patch") {
    return (
      <pre className="overflow-x-auto rounded-xl bg-[#1a1a1a] px-4 py-3 text-xs leading-5 text-[#e8e6e0]">
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
          border: "border-[#cfe5d7]",
          bg: "bg-[#edf7f1]",
          label: "text-[#1a6b3a]",
          dot: "bg-[#1a6b3a]",
          text: "Passed",
        }
      : failed
        ? {
            border: "border-[#f0caca]",
            bg: "bg-[#fff4f4]",
            label: "text-[#a33a3a]",
            dot: "bg-[#a33a3a]",
            text: "Failed",
          }
        : {
            border: "border-[#d8d3cb]",
            bg: "bg-[#faf8f4]",
            label: "text-[#6b7068]",
            dot: "bg-[#6b7068]",
            text: "Unknown",
          };
    const extraEntries = Object.entries(obj).filter(
      ([k]) => k !== "passed" && k !== "status"
    );
    return (
      <div className={`rounded-xl border ${style.border} ${style.bg} px-4 py-3`}>
        <div className={`mb-2 flex items-center gap-1.5 text-xs font-semibold ${style.label}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
          {style.text}
        </div>
        {extraEntries.length > 0 ? (
          <div className="space-y-1.5">
            {extraEntries.map(([k, v]) => (
              <div key={k} className="flex items-start gap-3 text-xs">
                <span className="w-28 shrink-0 text-[#6b7068]">{toTitleCase(k)}</span>
                <span className="text-[#1a1a1a]">
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
          border: "border-[#cfe5d7]",
          bg: "bg-[#edf7f1]",
          label: "text-[#1a6b3a]",
          dot: "bg-[#1a6b3a]",
          text: "Healthy",
        }
      : summary.status === "failed"
        ? {
            border: "border-[#f0caca]",
            bg: "bg-[#fff4f4]",
            label: "text-[#a33a3a]",
            dot: "bg-[#a33a3a]",
            text: "Failed",
          }
        : {
            border: "border-[#f0d8b8]",
            bg: "bg-[#fffbf4]",
            label: "text-[#7c5c1a]",
            dot: "bg-[#c47c1a]",
            text: "Warning",
          };

  return (
    <div
      className={`rounded-[1.5rem] border ${cfg.border} ${cfg.bg} px-5 py-4`}
    >
      <div className="mb-3 text-xs uppercase tracking-[0.14em] text-[#6b7068]">
        Validation Summary
      </div>

      {/* Overall status + counts */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${cfg.dot}`} />
          <span className={`text-sm font-semibold ${cfg.label}`}>
            {cfg.text}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-[#6b7068]">
          <span>
            <span className="font-semibold text-[#1a6b3a]">
              {summary.passedCount}
            </span>{" "}
            passed
          </span>
          {summary.failedCount > 0 ? (
            <span>
              <span className="font-semibold text-[#a33a3a]">
                {summary.failedCount}
              </span>{" "}
              failed
            </span>
          ) : null}
          <span>
            <span className="font-semibold text-[#1a1a1a]">
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
              className={`rounded-full border px-2.5 py-0.5 text-xs ${
                item.passed
                  ? "border-[#cfe5d7] bg-white text-[#1a6b3a]"
                  : item.failed
                    ? "border-[#f0caca] bg-white text-[#a33a3a]"
                    : "border-[#d8d3cb] bg-white text-[#6b7068]"
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
  always_recent:  { border: "border-[#cfe5d7]", bg: "bg-[#edf7f1]", text: "text-[#1a6b3a]" },
  entity_overlap: { border: "border-[#c2d9f5]", bg: "bg-[#eef5fd]", text: "text-[#1a3d6b]" },
  kind_match:     { border: "border-[#e0d3f5]", bg: "bg-[#f5f0fd]", text: "text-[#4a2d7a]" },
  followup_boost: { border: "border-[#f0d8b8]", bg: "bg-[#fffbf4]", text: "text-[#7c5c1a]" },
  carryover_entity_match: { border: "border-[#d7d1f7]", bg: "bg-[#f4f1ff]", text: "text-[#5a3fb4]" },
};

const AMBIGUITY_STYLES: Record<"low" | "medium" | "high", { border: string; bg: string; text: string }> = {
  low: { border: "border-[#cfe5d7]", bg: "bg-[#edf7f1]", text: "text-[#1a6b3a]" },
  medium: { border: "border-[#f0d8b8]", bg: "bg-[#fffbf4]", text: "text-[#7c5c1a]" },
  high: { border: "border-[#f0caca]", bg: "bg-[#fff4f4]", text: "text-[#a33a3a]" },
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
          ? "border-[#cfe5d7] bg-[#f4fbf7]"
          : "border-[#e8e4de] bg-white"
      }`}
    >
      {/* Role + task_kind + score */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span
          className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] ${
            turn.role === "user"
              ? "border-[#d8d3cb] bg-[#faf8f4] text-[#6b7068]"
              : "border-[#d0dde8] bg-[#eef4fb] text-[#2a4a6b]"
          }`}
        >
          {turn.role}
        </span>
        {turn.task_kind ? (
          <span className="rounded-full border border-[#e0ddd8] bg-white px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            {turn.task_kind.replace(/_/g, " ")}
          </span>
        ) : null}
        {/* Score badge */}
        <span
          className={`ml-auto rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold ${
            bd.total > 0
              ? "border-[#cfe5d7] bg-[#edf7f1] text-[#1a6b3a]"
              : "border-[#e0ddd8] bg-white text-[#6b7068]"
          }`}
        >
          {bd.total > 0 ? `+${bd.total}` : "0"}
        </span>
      </div>

      {/* Content preview */}
      <div className="mt-1.5 font-mono text-[11px] leading-5 text-[#1a1a1a]">
        {turn.content_preview}
      </div>

      {/* Signal pills (selected turns) */}
      {signals.length > 0 ? (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {signals.map((sig) => {
            const style = SIGNAL_STYLES[sig] ?? {
              border: "border-[#d8d3cb]",
              bg: "bg-white",
              text: "text-[#6b7068]",
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
            <span className="ml-auto rounded-full border border-[#e0ddd8] bg-white px-2 py-0.5 font-mono text-[10px] text-[#6b7068]">
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
        <div className="mt-1.5 text-[10px] text-[#a33a3a]">
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
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      {/* ── Header ── */}
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Memory debug
      </div>

      {/* ── Request signals row ── */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[#1a1a1a]">
          kind: <span className="font-medium">{md.current_task_kind.replace(/_/g, " ")}</span>
        </span>
        {md.followup_detected ? (
          <span className="rounded-full border border-[#f0d8b8] bg-[#fffbf4] px-2.5 py-0.5 text-[#7c5c1a]">
            ↩ follow-up detected
          </span>
        ) : null}
        {md.entity_tokens.length > 0 ? (
          <span className="rounded-full border border-[#c2d9f5] bg-[#eef5fd] px-2.5 py-0.5 text-[#1a3d6b]">
            entities: {md.entity_tokens.join(", ")}
          </span>
        ) : (
          <span className="rounded-full border border-[#e0ddd8] bg-white px-2.5 py-0.5 text-[#6b7068]">
            no entities detected
          </span>
        )}
        {md.recent_entity_hint ? (
          <span className="rounded-full border border-[#d7d1f7] bg-[#f4f1ff] px-2.5 py-0.5 text-[#5a3fb4]">
            recent entity: {md.recent_entity_hint}
          </span>
        ) : null}
      </div>

      {/* ── Budget row ── */}
      <div className="mb-3 flex flex-wrap items-center gap-3 text-[#6b7068]">
        <span>
          chars:{" "}
          <span className="font-medium text-[#1a1a1a]">{md.char_budget_used}</span>
          {" / "}
          {md.char_budget_max}
          {" "}
          <span className="opacity-60">({budgetPct}%)</span>
        </span>
        <span>
          messages:{" "}
          <span className="font-medium text-[#1a1a1a]">{md.selected_message_count}</span>
          {" (max pairs: "}
          {md.turn_budget_max_pairs}
          {")"}
        </span>
      </div>

      {/* ── Summary block ── */}
      <div className="mb-3 rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            {summary.selection_mode.replace(/_/g, " ")}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${ambiguityStyle.border} ${ambiguityStyle.bg} ${ambiguityStyle.text}`}>
            ambiguity: {summary.ambiguity_level}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            selected {summary.selected_count}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            rejected {summary.rejected_count}
          </span>
        </div>
        <div className="text-[11px] leading-5 text-[#1a1a1a]">{summary.summary_text}</div>
        {summary.primary_signals.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1">
            {summary.primary_signals.map((signal) => {
              const style = SIGNAL_STYLES[signal] ?? {
                border: "border-[#d8d3cb]",
                bg: "bg-white",
                text: "text-[#6b7068]",
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
          <div className="mb-1.5 text-[10px] uppercase tracking-[0.14em] text-[#6b7068]">
            Selected — {md.selected_turns.length} message{md.selected_turns.length !== 1 ? "s" : ""}
          </div>
          <div className="space-y-1.5">
            {md.selected_turns.map((t) => renderMemoryDebugTurnRow(t, true))}
          </div>
        </div>
      ) : (
        <div className="mb-3 rounded-xl border border-dashed border-[#d8d3cb] px-3 py-2 text-[#6b7068]">
          No prior turns selected — this is the first message or memory is disabled.
        </div>
      )}

      {/* ── Rejected turns ── */}
      {md.rejected_turns.length > 0 ? (
        <div>
          <div className="mb-1.5 text-[10px] uppercase tracking-[0.14em] text-[#6b7068]">
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
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Reference debug
      </div>

      <div className="mb-3 rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            {referenceDebug.resolved_reference.input_type.replace(/_/g, " ")}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${confidenceStyle.border} ${confidenceStyle.bg} ${confidenceStyle.text}`}>
            confidence: {referenceDebug.resolved_reference.confidence}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            rewrite {referenceDebug.rewrite_applied ? "applied" : "not applied"}
          </span>
        </div>

        <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-[#6b7068]">original</span>
          <span className="font-medium text-[#1a1a1a]">{referenceDebug.original_input}</span>
          <span className="text-[#6b7068]">rewritten</span>
          <span className="font-medium text-[#1a1a1a]">
            {referenceDebug.rewritten_query ?? "—"}
          </span>
          <span className="text-[#6b7068]">entities</span>
          <span className="font-medium text-[#1a1a1a]">
            {referenceDebug.resolved_reference.resolved_entities.length > 0
              ? referenceDebug.resolved_reference.resolved_entities.join(", ")
              : "—"}
          </span>
          <span className="text-[#6b7068]">reason</span>
          <span className="text-[#1a1a1a]">{referenceDebug.resolved_reference.reason}</span>
          <span className="text-[#6b7068]">rewrite note</span>
          <span className="text-[#1a1a1a]">{referenceDebug.rewrite_reason}</span>
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
    <div className="rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
          {label}
        </span>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-[10px] ${
            source.used
              ? "border-[#cfe5d7] bg-[#edf7f1] text-[#1a6b3a]"
              : "border-[#e0ddd8] bg-white text-[#6b7068]"
          }`}
        >
          {source.used ? "used" : "not used"}
        </span>
        <span className="ml-auto rounded-full border border-[#d8d3cb] bg-white px-2 py-0.5 font-mono text-[10px] text-[#6b7068]">
          {source.match_score.toFixed(2)}
        </span>
      </div>
      {source.reason ? (
        <div className="text-[11px] leading-5 text-[#1a1a1a]">{source.reason}</div>
      ) : null}
      {source.matched_items.length > 0 ? (
        <div className="mt-2 space-y-1">
          {source.matched_items.map((item) => (
            <div key={`${label}-${item}`} className="font-mono text-[11px] leading-5 text-[#6b7068]">
              • {item}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );

  return (
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Grounding debug
      </div>

      <div className="mb-3 rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            grounding {groundingDebug.grounding_score.overall.toFixed(2)}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${riskStyle.border} ${riskStyle.bg} ${riskStyle.text}`}>
            risk: {groundingDebug.hallucination_risk.level}
          </span>
        </div>
        <div className="text-[11px] leading-5 text-[#1a1a1a]">
          {groundingDebug.explanation.summary}
        </div>
        <div className="mt-1 text-[11px] leading-5 text-[#6b7068]">
          {groundingDebug.explanation.detail}
        </div>
        <div className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-[#6b7068]">retrieval</span>
          <span className="font-medium text-[#1a1a1a]">
            {groundingDebug.grounding_score.breakdown.retrieval_weight.toFixed(2)}
          </span>
          <span className="text-[#6b7068]">memory</span>
          <span className="font-medium text-[#1a1a1a]">
            {groundingDebug.grounding_score.breakdown.memory_weight.toFixed(2)}
          </span>
          <span className="text-[#6b7068]">answer</span>
          <span className="text-[#1a1a1a]">{groundingDebug.answer_preview}</span>
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
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Policy debug
      </div>

      <div className="rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            {policyDebug.mode}
          </span>
          <span className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${ambiguityStyle.border} ${ambiguityStyle.bg} ${ambiguityStyle.text}`}>
            ambiguity: {policyDebug.signals.ambiguity_level}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            {policyDebug.signals.query_type}
          </span>
        </div>

        <div className="text-[11px] leading-5 text-[#1a1a1a]">{policyDebug.reason}</div>

        <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-[#6b7068]">retrieval</span>
          <span className="font-medium text-[#1a1a1a]">
            {policyDebug.signals.has_retrieval ? "yes" : "no"} · {policyDebug.signals.retrieval_confidence.toFixed(2)}
          </span>
          <span className="text-[#6b7068]">memory</span>
          <span className="font-medium text-[#1a1a1a]">
            {policyDebug.signals.has_memory ? "yes" : "no"}
          </span>
        </div>
      </div>
    </div>
  );
}

function renderOrchestrationDebug(orchestrationDebug: OrchestrationDebugData): React.ReactNode {
  return (
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Orchestration debug
      </div>

      <div className="rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            {orchestrationDebug.route}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            dev call: {orchestrationDebug.dev_call.invoked ? "yes" : "no"}
          </span>
        </div>

        <div className="text-[11px] leading-5 text-[#1a1a1a]">{orchestrationDebug.reason}</div>

        <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-[#6b7068]">dev intent</span>
          <span className="font-medium text-[#1a1a1a]">
            {orchestrationDebug.signals.is_dev_intent ? "yes" : "no"}
          </span>
          <span className="text-[#6b7068]">code keywords</span>
          <span className="font-medium text-[#1a1a1a]">
            {orchestrationDebug.signals.has_code_keywords ? "yes" : "no"}
          </span>
          <span className="text-[#6b7068]">explicit dev kind</span>
          <span className="font-medium text-[#1a1a1a]">
            {orchestrationDebug.signals.explicit_dev_kind ? "yes" : "no"}
          </span>
          <span className="text-[#6b7068]">latency</span>
          <span className="font-medium text-[#1a1a1a]">
            {orchestrationDebug.dev_call.latency_ms ?? "—"} ms
          </span>
          <span className="text-[#6b7068]">returned patch</span>
          <span className="font-medium text-[#1a1a1a]">
            {orchestrationDebug.dev_call.returned.has_patch ? "yes" : "no"}
          </span>
        </div>
      </div>
    </div>
  );
}

function renderLongTermMemoryDebug(longTermMemoryDebug: LongTermMemoryDebugData): React.ReactNode {
  return (
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Long-term memory debug
      </div>
      {longTermMemoryDebug.retrieved.length === 0 ? (
        <div className="rounded-xl border border-[#e0ddd8] bg-white px-3 py-3 text-[11px] text-[#6b7068]">
          No long-term memory entries were used.
        </div>
      ) : (
        <div className="space-y-3">
          {longTermMemoryDebug.retrieved.map((entry, index) => (
            <div key={`${entry.type}-${index}`} className="rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
                  {entry.type}
                </span>
                <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
                  confidence: {entry.confidence.toFixed(2)}
                </span>
              </div>
              <div className="text-[11px] leading-5 text-[#1a1a1a]">{entry.content}</div>
              <div className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
                <span className="text-[#6b7068]">used</span>
                <span className="font-medium text-[#1a1a1a]">{entry.used ? "yes" : "no"}</span>
                <span className="text-[#6b7068]">importance</span>
                <span className="font-medium text-[#1a1a1a]">{entry.importance.toFixed(2)}</span>
                <span className="text-[#6b7068]">decay</span>
                <span className="font-medium text-[#1a1a1a]">{entry.decayScore.toFixed(2)}</span>
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
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Self-improvement debug
      </div>

      <div className="rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            sample: {performance.sample_size}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            source: {selfImprovementDebug.strategy_source ?? "none"}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            avg: {performance.avg_score.toFixed(2)}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            failure: {(performance.failure_rate * 100).toFixed(0)}%
          </span>
        </div>

        <div className="text-[11px] leading-5 text-[#1a1a1a]">{selfImprovementDebug.reason}</div>

        <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-[#6b7068]">strategy applied</span>
          <span className="font-medium text-[#1a1a1a]">
            {selfImprovementDebug.strategy_applied ? "yes" : "no"}
          </span>
          <span className="text-[#6b7068]">new strategy</span>
          <span className="font-medium text-[#1a1a1a]">
            {selfImprovementDebug.new_strategy_generated ? "yes" : "no"}
          </span>
          <span className="text-[#6b7068]">common failure step</span>
          <span className="font-medium text-[#1a1a1a]">
            {performance.common_failure_step ?? "—"}
          </span>
          <span className="text-[#6b7068]">last outcome</span>
          <span className="font-medium text-[#1a1a1a]">
            {selfImprovementDebug.last_experience?.status ?? "—"}
            {typeof selfImprovementDebug.last_experience?.final_score === "number"
              ? ` · ${selfImprovementDebug.last_experience.final_score.toFixed(2)}`
              : ""}
          </span>
        </div>

        {selfImprovementDebug.applied_strategies?.length ? (
          <div className="mt-3 rounded-xl border border-[#ece7de] bg-[#faf8f4] px-3 py-3">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7068]">
              Applied strategies
            </div>
            <ul className="space-y-1.5 text-[11px] text-[#1a1a1a]">
              {selfImprovementDebug.applied_strategies.map((item, index) => (
                <li key={`${item}-${index}`}>• {item}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {selfImprovementDebug.anti_patterns?.length ? (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-amber-700">
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
          <div className="mt-3 rounded-xl border border-[#ece7de] bg-[#faf8f4] px-3 py-3">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7068]">
              Strategy lineage
            </div>
            <ul className="space-y-1.5 text-[11px] text-[#1a1a1a]">
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
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Meta debug
      </div>

      <div className="rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            {metaDebug.strategy_applied ? "applied" : "not applied"}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            {metaDebug.strategy_type ?? "none"}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            {typeof metaDebug.confidence === "number"
              ? metaDebug.confidence.toFixed(2)
              : "—"}
          </span>
        </div>

        <div className="text-[11px] leading-5 text-[#1a1a1a]">
          source: {metaDebug.source ?? "none"}
        </div>

        {metaDebug.applied?.length ? (
          <div className="mt-3 rounded-xl border border-[#ece7de] bg-[#faf8f4] px-3 py-3">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7068]">
              Applied strategies
            </div>
            <ul className="space-y-1.5 text-[11px] text-[#1a1a1a]">
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
          <div className="mt-3 rounded-xl border border-[#ece7de] bg-[#faf8f4] px-3 py-3">
            <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-[#6b7068]">
              Generated strategies
            </div>
            <ul className="space-y-1.5 text-[11px] text-[#1a1a1a]">
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
            <div className="mb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-red-700">
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
    <div className="rounded-2xl border border-[#d8d3cb] bg-[#faf8f4] p-4 text-xs">
      <div className="mb-3 text-xs font-medium uppercase tracking-[0.16em] text-[#1a3d2e]">
        Rewrite debug
      </div>

      <div className="rounded-xl border border-[#e0ddd8] bg-white px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
            {rewriteDebug.status ?? "unknown"}
          </span>
          <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] text-[#6b7068]">
            delta: {rewriteDebug.score_delta >= 0 ? "+" : ""}{rewriteDebug.score_delta.toFixed(2)}
          </span>
        </div>

        <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[11px]">
          <span className="text-[#6b7068]">patch generated</span>
          <span className="font-medium text-[#1a1a1a]">{rewriteDebug.patch_generated ? "yes" : "no"}</span>
          <span className="text-[#6b7068]">patch valid</span>
          <span className="font-medium text-[#1a1a1a]">{rewriteDebug.patch_valid ? "yes" : "no"}</span>
          <span className="text-[#6b7068]">sandbox applied</span>
          <span className="font-medium text-[#1a1a1a]">{rewriteDebug.applied_in_sandbox ? "yes" : "no"}</span>
          <span className="text-[#6b7068]">improved</span>
          <span className="font-medium text-[#1a1a1a]">{rewriteDebug.improved ? "yes" : "no"}</span>
        </div>
      </div>
    </div>
  );
}

export default function AgentPage() {
  const searchParams = useSearchParams();
  const debugFromQuery = searchParams.get("debug") === "1";
  const promptRef = useRef<HTMLTextAreaElement | null>(null);
  const historyRef = useRef<HTMLDivElement | null>(null);
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
  // Session id is stable for the lifetime of the conversation.  A new UUID is
  // created when the component mounts (one per page load) or when the user
  // explicitly resets the conversation.
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());

  useEffect(() => {
    if (debugFromQuery) {
      setShowDebug(true);
    }
  }, [debugFromQuery]);

  useEffect(() => {
    promptRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!showDebug && mode === "dev") {
      setMode("web");
      if (kind === "dev_refinement") {
        setKind("ranking_explain");
      }
    }
  }, [showDebug, mode, kind]);

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
    if (history.length === 0) {
      return;
    }

    historyRef.current?.scrollTo({
      top: 0,
      behavior: "smooth",
    });
    promptRef.current?.focus();
  }, [history.length]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (!trimmedPrompt) {
      setError("Please enter a task.");
      return;
    }

    let parsedContext: Record<string, unknown> = {};
    try {
      parsedContext = contextJson.trim() ? JSON.parse(contextJson) : {};
    } catch {
      setError("Context JSON is invalid.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/agent/tasks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          mode,
          kind,
          source: mode === "dev" ? "api-dev" : "web",
          user_input: trimmedPrompt,
          context: parsedContext,
          constraints: { debug: showDebug },
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
        id: crypto.randomUUID(),
        mode,
        kind,
        prompt: trimmedPrompt,
        response: json,
        error: !res.ok || !json.success ? formattedError : null,
      };

      setHistory((current) => [nextEntry, ...current]);
      if (!res.ok || !json.success) {
        setError(nextEntry.error);
        if ((json.error ?? "").includes("Failed to reach agent API")) {
          setAgentStatus("offline");
        }
      } else {
        setAgentStatus("online");
      }
    } catch {
      const nextEntry: RunEntry = {
        id: crypto.randomUUID(),
        mode,
        kind,
        prompt: trimmedPrompt,
        response: null,
        error: "Failed to reach /api/agent/tasks",
      };
      setHistory((current) => [nextEntry, ...current]);
      setError(nextEntry.error);
      setAgentStatus("offline");
    } finally {
      setLoading(false);
    }
  }

  function resetSession() {
    setHistory([]);
    setError(null);
    setSessionId(crypto.randomUUID());
  }

  function applyQuickTask(task: (typeof QUICK_TASKS)[number]) {
    setMode(task.mode);
    setKind(task.kind);
    setPrompt(task.prompt);
    setContextJson(task.context);
    setError(null);
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

  const latest = history[0] ?? null;
  const friendlyError = getFriendlyError(error);
  const visibleQuickTasks = useMemo(
    () => QUICK_TASKS.filter((task) => showDebug || task.mode === "web"),
    [showDebug]
  );
  const promptPlaceholder = PROMPT_HINTS[kind];

  return (
    <main className="min-h-screen bg-[#f5f3ee] text-[#1a1a1a]">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8">
        <header className="mb-6 flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div
              className={`rounded-full border px-3 py-1 text-sm ${
                agentStatus === "online"
                  ? "border-[#cfe5d7] bg-[#edf7f1] text-[#1a3d2e]"
                  : agentStatus === "offline"
                    ? "border-[#f0caca] bg-[#fff4f4] text-[#a33a3a]"
                    : "border-[#d8d3cb] bg-white text-[#6b7068]"
              }`}
            >
              agent: {agentStatus}
            </div>
              {showDebug ? (
                <>
                  <div className="rounded-full border border-[#d8d3cb] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[#6b7068]">
                    {agentHealth?.generation?.configured
                      ? `provider: ${agentHealth.generation.providerLabel ?? "configured"}`
                      : "provider: fallback"}
                  </div>
                  <div className="rounded-full border border-[#d8d3cb] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[#6b7068]">
                    Agent
                  </div>
                <div className="rounded-full border border-[#d8d3cb] bg-white px-3 py-1 text-sm text-[#1a3d2e]">
                  Web and dev agent share the same core
                </div>
              </>
            ) : null}
            <button
              type="button"
              onClick={() => setShowDebug((current) => !current)}
              className={`rounded-full border px-3 py-1 text-sm transition ${
                showDebug
                  ? "border-[#16382a] bg-[#16382a] text-white"
                  : "border-[#d8d3cb] bg-white text-[#6b7068]"
              }`}
            >
              debug: {showDebug ? "on" : "off"}
            </button>
            {history.length > 0 ? (
              <button
                type="button"
                onClick={resetSession}
                disabled={loading}
                className="rounded-full border border-[#d8d3cb] bg-white px-3 py-1 text-sm text-[#6b7068] transition hover:border-[#a33a3a] hover:text-[#a33a3a] disabled:cursor-not-allowed disabled:opacity-50"
              >
                New conversation
              </button>
            ) : null}
          </div>
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-[#16382a]">
              CrawlerNest Agent
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#6b7068]">
              Ask for a ranking explanation, a university lookup, or a dev refinement
              task. The page stays thin and sends everything through the same agent
              API used by future web features.
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
              className="rounded-full border border-[#d8d3cb] bg-white px-4 py-2 text-sm text-[#1a3d2e] transition hover:bg-[#e8f2ec]"
            >
              {task.label}
            </button>
          ))}
        </section>

        {agentStatus === "offline" ? (
          <section className="mb-4 rounded-[1.5rem] border border-[#f0caca] bg-[#fff8f8] px-5 py-4 text-sm text-[#7c3131]">
            <div className="font-semibold text-[#a33a3a]">Agent service offline</div>
            <p className="mt-2 leading-6">
              The page is ready, but the independent Python agent API is not running.
              Start it with:
            </p>
            <pre className="mt-3 overflow-x-auto rounded-xl bg-white px-4 py-3 text-xs text-[#1a1a1a]">
              {AGENT_START_COMMAND}
            </pre>
          </section>
        ) : null}

        <section className="flex-1 rounded-[2rem] border border-[#e0ddd8] bg-white shadow-sm">
          {showDebug || loading ? (
            <div className="border-b border-[#e0ddd8] px-6 py-4">
              <div className="flex flex-wrap items-center gap-3 text-sm text-[#6b7068]">
                {showDebug ? (
                  <>
                    <span className="rounded-full bg-[#f5f3ee] px-3 py-1 text-[#1a3d2e]">
                      mode: {mode}
                    </span>
                    <span className="rounded-full bg-[#f5f3ee] px-3 py-1 text-[#1a3d2e]">
                      kind: {kind}
                    </span>
                  </>
                ) : null}
                {loading ? (
                  <span className="rounded-full bg-[#e8f2ec] px-3 py-1 text-[#1a3d2e]">
                    running...
                  </span>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="grid min-h-[520px] lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="flex min-h-[520px] flex-col">
              <div ref={historyRef} className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
                {history.length === 0 ? (
                  <div className="rounded-[1.5rem] border border-dashed border-[#d8d3cb] bg-[#faf8f4] px-5 py-6 text-sm text-[#6b7068]">
                    Start with a quick task above, or type your own request below.
                    The first response will appear here.
                  </div>
                ) : null}

                {history.map((entry, historyIndex) => (
                  <div key={entry.id} className="space-y-3">
                    <div className="ml-auto max-w-3xl rounded-[1.5rem] bg-[#16382a] px-5 py-4 text-white">
                      <div className="flex items-center justify-between gap-3">
                        {showDebug ? (
                          <div className="text-xs uppercase tracking-[0.16em] text-white/70">
                            {entry.mode} · {entry.kind}
                          </div>
                        ) : null}
                        {history.length > 1 ? (
                          <div className="ml-auto text-[10px] text-white/50">
                            turn {history.length - historyIndex}
                          </div>
                        ) : null}
                      </div>
                      <div className={`text-sm leading-6 ${showDebug || history.length > 1 ? "mt-2" : ""}`}>{entry.prompt}</div>
                    </div>

                    {(() => {
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
                          className={`max-w-4xl rounded-[1.5rem] border bg-[#faf8f4] px-5 py-4 transition ${
                            entry.id === latest?.id
                              ? "border-[#cfe5d7] shadow-[0_0_0_2px_rgba(26,61,46,0.06)]"
                              : "border-[#e0ddd8]"
                          }`}
                        >
                      {isDevMode ? (
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="rounded-full border border-[#d8d3cb] bg-white px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-[#6b7068]">
                                dev
                              </span>
                              <span className="rounded-full border border-[#d8d3cb] bg-white px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-[#6b7068]">
                                {entry.kind.replace(/_/g, " ")}
                              </span>
                            </div>
                            <div className="mt-2 text-sm font-semibold text-[#1a3d2e]">
                              {entry.response?.data?.message ?? "Dev agent response"}
                            </div>
                          </div>
                          <div className="shrink-0 rounded-full bg-white px-3 py-1 text-xs font-medium text-[#6b7068]">
                            {entry.response?.data?.status ?? "error"}
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-[#1a3d2e]">
                              {formatted?.title ?? entry.response?.data?.message ?? "Agent response"}
                            </div>
                            {showDebug && generationSource ? (
                              <div className="mt-2 flex flex-wrap items-center gap-2">
                                <span
                                  className={`rounded-full border px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] ${
                                    generationSource === "llm"
                                      ? "border-[#cfe5d7] bg-[#edf7f1] text-[#1a6b3a]"
                                      : "border-[#f0d8b8] bg-[#fffbf4] text-[#7c5c1a]"
                                  }`}
                                >
                                  {generationSource}
                                </span>
                                {modelName ? (
                                  <span className="rounded-full border border-[#d8d3cb] bg-white px-2.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
                                    {modelName}
                                  </span>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                          <div className="rounded-full bg-white px-3 py-1 text-xs font-medium text-[#6b7068]">
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
                                <div className="rounded-[1.5rem] border border-[#d8d3cb] bg-white px-5 py-4">
                                  <div className="mb-3 text-xs uppercase tracking-[0.14em] text-[#6b7068]">
                                    Execution plan
                                  </div>
                                  <ol className="overflow-hidden rounded-xl border border-[#ece7de]">
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
                                            traceIndex > 0 ? "border-t border-[#ece7de]" : ""
                                          }`}
                                        >
                                          <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[#cfe5d7] bg-[#edf7f1] text-[10px] font-semibold text-[#1a3d2e]">
                                            {traceIndex + 1}
                                          </div>
                                          <div className="min-w-0 flex-1">
                                            <div className="text-sm font-medium text-[#1a1a1a]">
                                              {stepLabel}
                                            </div>
                                            {owner ? (
                                              <div className="mt-0.5 text-xs text-[#6b7068]">
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
                              <div className="rounded-[1.5rem] border border-[#d8d3cb] bg-white px-5 py-4">
                                <div className="mb-4 text-xs uppercase tracking-[0.14em] text-[#6b7068]">
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
                                            <div className="mb-1.5 text-[10px] uppercase tracking-[0.14em] text-[#6b7068]">
                                              {toTitleCase(key)}
                                            </div>
                                            {rendered}
                                          </div>
                                        );
                                      }
                                    )}
                                  </div>
                                ) : (
                                  <p className="text-xs text-[#6b7068]">No output data.</p>
                                )}
                              </div>

                              {/* ── Warnings ── */}
                              {warnings.length > 0 ? (
                                <div className="rounded-[1.5rem] border border-[#f0d8b8] bg-[#fffbf4] px-5 py-4">
                                  <div className="mb-2 text-xs uppercase tracking-[0.14em] text-[#6b7068]">
                                    Warnings
                                  </div>
                                  <ul className="space-y-1.5">
                                    {warnings.map((w) => (
                                      <li key={w} className="flex items-start gap-2 text-xs text-[#7c5c1a]">
                                        <span className="mt-0.5 shrink-0 text-[#c47c1a]">▲</span>
                                        {w}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ) : (
                                <div className="flex items-center gap-2 rounded-[1.5rem] border border-[#e0ddd8] bg-white px-5 py-3">
                                  <span className="h-1.5 w-1.5 rounded-full bg-[#cfe5d7]" />
                                  <span className="text-xs text-[#6b7068]">No warnings</span>
                                </div>
                              )}
                            </div>
                          ) : (
                            // Web render branch — formatter output only.
                            // Reads only from the formatter-shaped payload: explanation, items, meta.
                            // Never touches raw backend data directly.
                            <div className="mt-4 rounded-[1.5rem] bg-white px-5 py-4">
                              <div className="space-y-3 text-sm leading-7 text-[#1a1a1a]">
                                {paragraphs.map((paragraph) => (
                                  <p key={paragraph}>{paragraph}</p>
                                ))}
                              </div>

                              {items.length > 0 ? (
                                <div className="mt-4 overflow-hidden rounded-2xl border border-[#ece7de] bg-[#faf8f4]">
                                  {items.map((item, index) => (
                                    <div
                                      key={`${item.kind ?? "item"}-${item.label}`}
                                      className={`flex items-start gap-3 px-4 py-3 text-sm ${
                                        index > 0 ? "border-t border-[#ece7de]" : ""
                                      }`}
                                    >
                                      {item.kind ? (
                                        <span className="mt-0.5 shrink-0 rounded-full border border-[#d8d3cb] bg-white px-2 py-0.5 text-[10px] uppercase tracking-[0.12em] text-[#6b7068]">
                                          {item.kind}
                                        </span>
                                      ) : null}
                                      <div className="min-w-0 flex-1">
                                        <div className="font-medium text-[#1a1a1a]">{item.label}</div>
                                        {item.description ? (
                                          <div className="mt-0.5 text-xs leading-5 text-[#6b7068]">
                                            {item.description}
                                          </div>
                                        ) : null}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              ) : null}

                              {Object.keys(meta).length > 0 ? (
                                <div className="mt-4 rounded-2xl border border-[#ece7de] bg-[#faf8f4] p-4">
                                  <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
                                    {Object.entries(meta).map(([key, value]) => (
                                      <div key={key} className="contents">
                                        <span className="text-[#6b7068]">{key}</span>
                                        <span className="font-medium text-[#1a1a1a]">
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
                              <summary className="cursor-pointer px-4 py-3 text-xs font-medium uppercase tracking-[0.16em] text-[#6b7068]">
                                Debug details
                              </summary>
                              <div className="space-y-4 border-t border-[#ece7de] p-4">
                                {!isDevMode ? (
                                  <div className="rounded-2xl border border-[#ece7de] bg-[#faf8f4] p-4 text-xs text-[#6b7068]">
                                    <div className="font-medium text-[#1a3d2e]">Generation</div>
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

                                <div className="rounded-2xl border border-[#ece7de] bg-[#faf8f4] p-4 text-xs text-[#6b7068]">
                                  <div className="font-medium text-[#1a3d2e]">Task info</div>
                                  <pre className="mt-2 overflow-x-auto">{JSON.stringify({ taskId, status }, null, 2)}</pre>
                                </div>

                                <div className="rounded-2xl border border-[#ece7de] bg-[#faf8f4] p-4 text-xs text-[#6b7068]">
                                  <div className="font-medium text-[#1a3d2e]">Warnings</div>
                                  <pre className="mt-2 overflow-x-auto">{JSON.stringify(warnings, null, 2)}</pre>
                                </div>

                                <div className="rounded-2xl border border-[#ece7de] bg-[#faf8f4] p-4 text-xs text-[#6b7068]">
                                  <div className="font-medium text-[#1a3d2e]">Raw trace data</div>
                                  <pre className="mt-2 overflow-x-auto">{JSON.stringify(traces, null, 2)}</pre>
                                </div>

                                <div className="rounded-2xl border border-[#ece7de] bg-[#faf8f4] p-4 text-xs text-[#6b7068]">
                                  <div className="font-medium text-[#1a3d2e]">Raw response</div>
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
              </div>

              <div className="border-t border-[#e0ddd8] bg-white px-6 py-5">
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
                    className="w-full rounded-[1.5rem] border border-[#d8d3cb] bg-[#faf8f4] px-5 py-4 text-sm outline-none transition focus:border-[#1a3d2e]"
                  />

                  <div className="text-xs text-[#6b7068]">
                    Press <span className="font-medium text-[#1a3d2e]">Enter</span> to send.
                    Use <span className="font-medium text-[#1a3d2e]">Shift + Enter</span> for a new line.
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {showDebug ? (
                        <>
                          <select
                            value={mode}
                            onChange={(event) => setMode(event.target.value as AgentMode)}
                            className="rounded-full border border-[#d8d3cb] bg-white px-4 py-2 text-sm text-[#1a3d2e] outline-none"
                          >
                            <option value="web">web</option>
                            <option value="dev">dev</option>
                          </select>

                          <select
                            value={kind}
                            onChange={(event) => setKind(event.target.value as TaskKind)}
                            className="rounded-full border border-[#d8d3cb] bg-white px-4 py-2 text-sm text-[#1a3d2e] outline-none"
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
                            className="rounded-full border border-[#d8d3cb] bg-white px-4 py-2 text-sm text-[#1a3d2e] transition hover:bg-[#e8f2ec]"
                          >
                            {showAdvanced ? "Hide context" : "Context"}
                          </button>
                        </>
                      ) : null}
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="rounded-full bg-[#16382a] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#2a5a42] disabled:cursor-not-allowed disabled:bg-[#c0bdb8]"
                    >
                      {loading ? "Running..." : "Run"}
                    </button>
                  </div>

                  {showDebug && showAdvanced ? (
                    <div className="rounded-[1.25rem] border border-[#e0ddd8] bg-[#faf8f4] p-4">
                      <div className="mb-2 text-xs uppercase tracking-[0.16em] text-[#6b7068]">
                        Context JSON
                      </div>
                      <textarea
                        value={contextJson}
                        onChange={(event) => setContextJson(event.target.value)}
                        rows={8}
                        className="w-full rounded-xl border border-[#d8d3cb] bg-white px-4 py-3 font-mono text-xs outline-none transition focus:border-[#1a3d2e]"
                      />
                    </div>
                  ) : null}
                </form>
              </div>
            </div>

            <aside className="border-t border-[#e0ddd8] bg-[#faf8f4] px-6 py-6 lg:border-l lg:border-t-0">
              <div className="rounded-[1.5rem] border border-[#e0ddd8] bg-white p-4">
                <div className="text-xs uppercase tracking-[0.16em] text-[#6b7068]">
                  Good first prompts
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-sm text-[#1a3d2e]">
                  {visibleQuickTasks.map((task) => (
                    <button
                      key={`hint-${task.label}`}
                      type="button"
                      onClick={() => applyQuickTask(task)}
                      disabled={loading}
                      className="rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-3 py-1.5 text-left text-sm text-[#1a3d2e] transition hover:bg-[#e8f2ec] disabled:cursor-not-allowed disabled:opacity-70"
                    >
                      {task.prompt}
                    </button>
                  ))}
                </div>
              </div>

              {showDebug ? (
                <>
                  <div className="mt-6">
                    <h2 className="text-lg font-semibold text-[#1a3d2e]">How it works</h2>
                    <div className="mt-4 space-y-3 text-sm leading-6 text-[#6b7068]">
                      <p>1. This page sends a task to <code>/api/agent/tasks</code>.</p>
                      <p>2. The Next proxy forwards it to the independent Python agent API.</p>
                      <p>3. The agent service runs the shared planner, runner, and tools.</p>
                      <p>4. The structured result comes back here unchanged.</p>
                    </div>
                  </div>

                  <div className="mt-6 rounded-[1.5rem] border border-[#e0ddd8] bg-white p-4">
                    <div className="text-xs uppercase tracking-[0.16em] text-[#6b7068]">
                      Generation status
                    </div>
                    <div className="mt-3 space-y-2 text-sm text-[#1a1a1a]">
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
                        <p className="text-[#6b7068]">{agentHealth.generation.reason}</p>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-6 rounded-[1.5rem] border border-[#e0ddd8] bg-white p-4">
                    <div className="text-xs uppercase tracking-[0.16em] text-[#6b7068]">
                      Agent startup
                    </div>
                    <pre className="mt-3 overflow-x-auto rounded-xl bg-[#faf8f4] px-4 py-3 text-xs text-[#1a1a1a]">
                      {AGENT_START_COMMAND}
                    </pre>
                  </div>

                  <div className="mt-6 rounded-[1.5rem] border border-[#e0ddd8] bg-white p-4">
                    <div className="text-xs uppercase tracking-[0.16em] text-[#6b7068]">
                      Latest task
                    </div>
                    <div className="mt-3 text-sm text-[#6b7068]">
                      {latest ? (
                        <>
                          <p className="font-medium text-[#1a3d2e]">{latest.prompt}</p>
                          <p className="mt-2">
                            {latest.response?.data?.status ?? "error"} · {latest.kind}
                          </p>
                        </>
                      ) : (
                        <p>No tasks yet.</p>
                      )}
                    </div>
                  </div>

                  <div className="mt-6 rounded-[1.5rem] border border-[#e0ddd8] bg-white p-4">
                    <div className="text-xs uppercase tracking-[0.16em] text-[#6b7068]">
                      Conversation session
                    </div>
                    <div className="mt-3 space-y-2 text-xs text-[#6b7068]">
                      <p>
                        Session:{" "}
                        <span className="font-mono font-medium text-[#1a3d2e]">
                          {sessionId.slice(0, 8)}…
                        </span>
                      </p>
                      <p>
                        Turns:{" "}
                        <span className="font-medium text-[#1a3d2e]">
                          {history.length}
                        </span>
                      </p>
                      <button
                        type="button"
                        onClick={resetSession}
                        disabled={loading}
                        className="mt-1 rounded-full border border-[#d8d3cb] bg-[#faf8f4] px-3 py-1 text-xs text-[#6b7068] transition hover:border-[#a33a3a] hover:text-[#a33a3a] disabled:cursor-not-allowed disabled:opacity-50"
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
    </main>
  );
}
