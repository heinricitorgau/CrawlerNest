/** Shared shapes for the "Your desk" component set. */

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  /** The agent route's `warnings`, shown above the reply by AgentWarningBanner. */
  warnings?: unknown;
  /** The request failed; `content` is the error. */
  error?: boolean;
}

export type TaskStatus = "todo" | "in_progress" | "done" | "cancelled";

export interface DeskTask {
  id: string;
  title: string;
  /** ISO date, YYYY-MM-DD; null when the task has no deadline. */
  dueDate: string | null;
  status: TaskStatus;
  category?: string;
}

export interface PrioritySprint {
  title: string;
  goal: string;
  /** ISO dates, YYYY-MM-DD. */
  startDate: string;
  endDate: string;
  tasks: DeskTask[];
}

export interface DeskTab {
  id: string;
  label: string;
}

export interface SubScore {
  label: string;
  value: number;
}

export interface SkillMastery {
  label: string;
  /** 0-100. */
  percent: number;
}

export interface NarrativeTheme {
  title: string;
  summary: string;
  traits: string[];
  evidence?: string[];
}

export interface Resonance {
  institution: string;
  trait: string;
  /** 0-100. */
  level: number;
  note?: string;
}
