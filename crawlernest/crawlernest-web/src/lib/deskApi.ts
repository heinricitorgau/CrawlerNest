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
    const message = normalizeAuthError(response.status, payload);
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

export type LiveSkill = SkillMastery & { subject: string; attempted: number };

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
