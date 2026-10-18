import { normalizeAuthError } from "@/lib/authMessages";
import type { DeskTask, PrioritySprint, SkillMastery, TaskStatus } from "@/components/desk";

/**
 * Client for the Java DeskController (`/api/v1/user/desk`, reached through the
 * Next proxy at `/api/user/desk`).
 *
 * Like conversationsApi, calls return a result object rather than throwing, so a
 * caller can tell "sign in" from "try again" without parsing a message.
 */

export type DeskApiFailure = {
  ok: false;
  reason: "unauthenticated" | "not_found" | "rejected" | "unavailable";
  message: string;
};

export type DeskApiResult<T> = { ok: true; data: T } | DeskApiFailure;

const BASE = "/api/user/desk";

async function call<T>(
  path: string,
  init: RequestInit,
  parse: (data: unknown) => T,
): Promise<DeskApiResult<T>> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { credentials: "include", cache: "no-store", ...init });
  } catch {
    return { ok: false, reason: "unavailable", message: "Could not reach the server." };
  }
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // An empty or non-JSON body: the status still classifies it.
  }
  if (!response.ok) {
    // The desk API's own message when it sent one -- "No model is configured"
    // says more than the generic 503 text -- except for 401, which is always "sign in".
    const apiError = (payload as { error?: unknown } | null)?.error;
    const message =
      response.status !== 401 && typeof apiError === "string" && apiError.trim()
        ? apiError
        : normalizeAuthError(response.status, payload);
    const reason =
      response.status === 401 ? "unauthenticated"
        : response.status === 404 ? "not_found"
          : response.status === 400 || response.status === 409 ? "rejected"
            : "unavailable";
    return { ok: false, reason, message };
  }
  return { ok: true, data: parse((payload as { data?: unknown } | null)?.data ?? null) };
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

// ─── Shapes the API returns, reduced to what the desk components take ────────

const TASK_STATUSES: readonly TaskStatus[] = ["todo", "in_progress", "done", "cancelled"];

export function toDeskTask(raw: unknown): DeskTask | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  if (typeof row.id !== "number" || typeof row.title !== "string") return null;
  const status = TASK_STATUSES.includes(row.status as TaskStatus) ? (row.status as TaskStatus) : "todo";
  return {
    id: String(row.id),
    title: row.title,
    dueDate: typeof row.dueDate === "string" ? row.dueDate : null,
    status,
    category: typeof row.category === "string" ? row.category : undefined,
  };
}

function toTasks(raw: unknown): DeskTask[] {
  return Array.isArray(raw) ? raw.map(toDeskTask).filter((task): task is DeskTask => task !== null) : [];
}

export type LiveSprint = PrioritySprint & { id: number };

export function toSprint(raw: unknown): LiveSprint | null {
  if (!raw || typeof raw !== "object") return null;
  const { sprint, tasks } = raw as { sprint?: Record<string, unknown>; tasks?: unknown };
  if (!sprint || typeof sprint.id !== "number" || typeof sprint.title !== "string") return null;
  return {
    id: sprint.id,
    title: sprint.title,
    goal: typeof sprint.goal === "string" ? sprint.goal : "",
    startDate: String(sprint.startDate ?? ""),
    endDate: String(sprint.endDate ?? ""),
    tasks: toTasks(tasks),
  };
}

export type LiveSkill = SkillMastery & { subject: string; attempted: number; correct: number };

/** Units with no attempts yet have no percentage, and are left out rather than drawn at 0%. */
export function toSkills(raw: unknown): LiveSkill[] {
  if (!Array.isArray(raw)) return [];
  const skills: LiveSkill[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    if (typeof row.unit !== "string" || typeof row.subject !== "string" || typeof row.masteryPct !== "number") continue;
    skills.push({
      subject: row.subject,
      label: row.unit,
      percent: row.masteryPct,
      attempted: typeof row.questionsAttempted === "number" ? row.questionsAttempted : 0,
      correct: typeof row.questionsCorrect === "number" ? row.questionsCorrect : 0,
    });
  }
  return skills;
}

// ─── Calls ───────────────────────────────────────────────────────────────────

/** `data` is null when no sprint covers today. */
export const getCurrentSprint = () => call("/sprints/current", {}, toSprint);

export const createSprint = (input: { title: string; goal?: string; startDate: string; endDate: string }) =>
  call("/sprints", json("POST", input), toSprint);

export const createTask = (input: { title: string; dueDate?: string; sprintId?: number }) =>
  call("/tasks", json("POST", input), toDeskTask);

export const setTaskStatus = (taskId: string, status: TaskStatus) =>
  call(`/tasks/${encodeURIComponent(taskId)}`, json("PATCH", { status }), toDeskTask);

export const listSkills = () => call("/skills", {}, toSkills);

/** Adds to a unit's counts; the API computes the percentage. Resolves to the unit's new row. */
export const recordSkillResult = (input: { subject: string; unit: string; attempted: number; correct: number }) =>
  call("/skills/results", json("POST", input), (raw) => toSkills([raw])[0] ?? null);

export type LiveTarget = { id: number; name: string; stage: string; deadline: string | null; programmeName: string | null };

function toTargets(raw: unknown): LiveTarget[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item) => {
    const r = (item ?? {}) as Record<string, unknown>;
    return typeof r.id === "number" && typeof r.name === "string"
      ? [{
          id: r.id, name: r.name, stage: typeof r.stage === "string" ? r.stage : "researching",
          deadline: typeof r.deadline === "string" ? r.deadline : null,
          programmeName: typeof r.programmeName === "string" ? r.programmeName : null,
        }]
      : [];
  });
}

export const listTargets = () => call("/targets", {}, toTargets);

// ─── Essay review ────────────────────────────────────────────────────────────

export type EssayDimension = { key: string; label: string; score: number; rationale: string };

export type EssaySuggestion = {
  start: number;
  end: number;
  original: string;
  suggested: string;
  dimension: string;
  reason: string;
};

export type EssayReview = {
  id: number;
  essayTitle: string;
  draftText: string;
  wordCount: number;
  /** The prompt's limit as the user gave it; null when they did not. */
  wordLimit: number | null;
  rubricVersion: string;
  overallScore: number;
  dimensions: EssayDimension[];
  suggestions: EssaySuggestion[];
  comparedToRevision: { id: number; overallDelta: number; dimensionDeltas: Record<string, number> } | null;
  cached: boolean;
  /** Quotes the model gave that were not in the draft exactly once, and so were not shown. */
  droppedQuotes: number;
  model: string;
  evaluatedAt: string;
  /** Always true: the scores are a model's judgement. Kept so no caller can lose the flag. */
  isEstimated: true;
  caveats: string[];
};

export type EssaySummary = { id: number; essayTitle: string; overallScore: number; wordCount: number; createdAt: string };

const str = (v: unknown, fallback = "") => (typeof v === "string" ? v : fallback);
const num = (v: unknown, fallback = 0) => (typeof v === "number" ? v : fallback);

export function toEssayReview(raw: unknown): EssayReview | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.id !== "number" || r.isEstimated !== true) return null;
  const overall = (r.overall ?? {}) as Record<string, unknown>;
  const provenance = (r.provenance ?? {}) as Record<string, unknown>;
  const compared = r.comparedToRevision as Record<string, unknown> | null | undefined;
  return {
    id: r.id,
    essayTitle: str(r.essayTitle),
    draftText: str(r.draftText),
    wordCount: num(r.wordCount),
    wordLimit: typeof r.wordLimit === "number" ? r.wordLimit : null,
    rubricVersion: str(r.rubricVersion),
    overallScore: num(overall.score),
    dimensions: (Array.isArray(r.dimensions) ? r.dimensions : []).map((d) => {
      const row = d as Record<string, unknown>;
      return { key: str(row.key), label: str(row.label), score: num(row.score), rationale: str(row.rationale) };
    }),
    suggestions: (Array.isArray(r.suggestions) ? r.suggestions : []).map((s) => {
      const row = s as Record<string, unknown>;
      return {
        start: num(row.start), end: num(row.end), original: str(row.original), suggested: str(row.suggested),
        dimension: str(row.dimension), reason: str(row.reason),
      };
    }),
    comparedToRevision: compared && typeof compared.id === "number"
      ? { id: compared.id, overallDelta: num(compared.overallDelta), dimensionDeltas: (compared.dimensionDeltas ?? {}) as Record<string, number> }
      : null,
    cached: r.cached === true,
    droppedQuotes: num(r.droppedQuotes),
    model: str(provenance.model, "unknown model"),
    evaluatedAt: str(provenance.evaluatedAt),
    isEstimated: true,
    caveats: Array.isArray(r.caveats) ? r.caveats.filter((c): c is string => typeof c === "string") : [],
  };
}

function toEssaySummaries(raw: unknown): EssaySummary[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item) => {
    const r = (item ?? {}) as Record<string, unknown>;
    return typeof r.id === "number"
      ? [{ id: r.id, essayTitle: str(r.essayTitle), overallScore: num(r.overallScore), wordCount: num(r.wordCount), createdAt: str(r.createdAt) }]
      : [];
  });
}

export const evaluateEssay = (input: {
  essayTitle: string;
  essayPrompt?: string;
  draftText: string;
  revisionOfId?: number;
  wordLimit?: number;
}) =>
  call("/essays/evaluate", json("POST", input), toEssayReview);

export const listEssays = () => call("/essays", {}, toEssaySummaries);

export const getEssay = (id: number) => call(`/essays/${encodeURIComponent(String(id))}`, {}, toEssayReview);

// ─── Narrative ───────────────────────────────────────────────────────────────

export type LiveTheme = {
  id: number;
  title: string;
  summary: string;
  traits: string[];
  status: "suggested" | "accepted" | "dismissed";
  quotes: string[];
  model: string;
  isEstimated: true;
};

export type LiveResonance = {
  themeId: number;
  targetEntityId: number;
  institution: string;
  /** 1-5. */
  level: number;
  rationale: string;
  institutionBasis: "user_notes" | "model_general_knowledge";
  isEstimated: true;
};

export type Narrative = { themes: LiveTheme[]; resonance: LiveResonance[]; caveats: string[] };

/** Rows without isEstimated are dropped: a model's output never renders without the flag. */
export function toNarrative(raw: unknown): Narrative {
  const r = (raw ?? {}) as Record<string, unknown>;
  const themes = (Array.isArray(r.themes) ? r.themes : []).flatMap((item): LiveTheme[] => {
    const t = (item ?? {}) as Record<string, unknown>;
    if (typeof t.id !== "number" || t.isEstimated !== true) return [];
    const status: LiveTheme["status"] = t.status === "accepted" || t.status === "dismissed" ? t.status : "suggested";
    return [{
      id: t.id, title: str(t.title), summary: str(t.summary), status,
      traits: Array.isArray(t.traits) ? t.traits.filter((x): x is string => typeof x === "string") : [],
      quotes: (Array.isArray(t.evidence) ? t.evidence : []).map((e) => str((e as Record<string, unknown>)?.quote)).filter(Boolean),
      model: str(((t.provenance ?? {}) as Record<string, unknown>).model, "unknown model"),
      isEstimated: true as const,
    }];
  });
  const resonance = (Array.isArray(r.resonance) ? r.resonance : []).flatMap((item) => {
    const x = (item ?? {}) as Record<string, unknown>;
    if (typeof x.themeId !== "number" || typeof x.targetEntityId !== "number" || x.isEstimated !== true) return [];
    return [{
      themeId: x.themeId, targetEntityId: x.targetEntityId, institution: str(x.institution), level: num(x.level, 1),
      rationale: str(x.rationale),
      institutionBasis: x.institutionBasis === "user_notes" ? "user_notes" as const : "model_general_knowledge" as const,
      isEstimated: true as const,
    }];
  });
  const caveats = Array.isArray(r.caveats) ? r.caveats.filter((c): c is string => typeof c === "string") : [];
  return { themes, resonance, caveats };
}

export const getNarrative = () => call("/story/narrative", {}, toNarrative);
export const generateThemes = () => call("/story/themes/generate", { method: "POST" }, toNarrative);
export const decideTheme = (id: number, status: "accepted" | "dismissed") =>
  call(`/story/themes/${encodeURIComponent(String(id))}`, json("PATCH", { status }), toNarrative);
export const generateResonance = () => call("/story/resonance/generate", { method: "POST" }, toNarrative);
