"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { clampPercent, daysUntil, formatShortDate } from "./meter";
import type { DeskTask, PrioritySprint, TaskStatus } from "./types";

const STATUS_STYLE: Record<TaskStatus, { label: string; dot: string }> = {
  todo: { label: "To do", dot: "border-2 border-slate-300 bg-white" },
  in_progress: { label: "In progress", dot: "bg-blue-500" },
  done: { label: "Done", dot: "bg-emerald-500" },
  cancelled: { label: "Cancelled", dot: "bg-slate-300" },
};

const isClosed = (task: DeskTask) => task.status === "done" || task.status === "cancelled";

export function deadlineBadge(task: DeskTask, today: Date): { text: string; className: string } | null {
  if (task.dueDate === null) return null;
  if (isClosed(task)) return { text: formatShortDate(task.dueDate), className: "bg-slate-100 text-slate-500" };
  const days = daysUntil(task.dueDate, today);
  if (days < 0) return { text: `${-days}d overdue`, className: "bg-red-100 text-red-700" };
  if (days === 0) return { text: "Due today", className: "bg-red-100 text-red-700" };
  if (days <= 7) return { text: `${days}d left`, className: "bg-amber-100 text-amber-800" };
  return { text: formatShortDate(task.dueDate), className: "bg-slate-100 text-slate-600" };
}

interface TaskListProps {
  tasks: DeskTask[];
  today: Date;
  onToggle?: (taskId: string) => void;
}

/** Open tasks first, each group by due date. */
export function TaskList({ tasks, today, onToggle }: TaskListProps) {
  const ordered = [...tasks].sort(
    (a, b) =>
      Number(isClosed(a)) - Number(isClosed(b)) ||
      // Undated after dated, as the API orders them.
      Number(a.dueDate === null) - Number(b.dueDate === null) ||
      (a.dueDate ?? "").localeCompare(b.dueDate ?? ""),
  );
  return (
    <ul className="divide-y divide-slate-100">
      {ordered.map((task) => {
        const badge = deadlineBadge(task, today);
        const status = STATUS_STYLE[task.status];
        return (
          <li key={task.id} className="flex items-center gap-3 py-2.5">
            <button
              type="button"
              onClick={onToggle ? () => onToggle(task.id) : undefined}
              disabled={!onToggle}
              aria-label={`${task.title}: ${status.label}`}
              className={`h-3.5 w-3.5 shrink-0 rounded-full ${status.dot}`}
            />
            <div className="min-w-0 flex-1">
              <p className={`truncate text-sm ${isClosed(task) ? "text-slate-400 line-through" : "text-slate-800"}`}>
                {task.title}
              </p>
              {task.category ? <p className="text-xs text-slate-500">{task.category}</p> : null}
            </div>
            {badge ? (
              <span className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-medium tabular-nums ${badge.className}`}>
                {badge.text}
              </span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

interface SprintCardProps {
  sprint: PrioritySprint;
  today: Date;
  onToggleTask?: (taskId: string) => void;
  /** Shows an add-task row when given. Resolve false to keep the typed text (the save failed). */
  onAddTask?: (input: { title: string; dueDate?: string }) => Promise<boolean>;
}

export function SprintCard({ sprint, today, onToggleTask, onAddTask }: SprintCardProps) {
  // Cancelled tasks are out of the sprint's count, as they are in the API's taskCount.
  const counted = sprint.tasks.filter((task) => task.status !== "cancelled");
  const done = counted.filter((task) => task.status === "done").length;
  const progress = clampPercent(done, counted.length);
  const daysLeft = daysUntil(sprint.endDate, today);
  return (
    <DeskCard
      eyebrow="Priority sprint"
      title={sprint.title}
      aside={
        <span className="text-xs text-slate-500">
          {formatShortDate(sprint.startDate)} – {formatShortDate(sprint.endDate)}
          {daysLeft >= 0 ? ` · ${daysLeft}d left` : " · ended"}
        </span>
      }
    >
      <p className="text-sm text-slate-600">{sprint.goal}</p>
      <div className="mt-3 flex items-center gap-3">
        <div
          role="progressbar"
          aria-label="Sprint progress"
          aria-valuemin={0}
          aria-valuemax={counted.length}
          aria-valuenow={done}
          className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200"
        >
          <div className="h-full rounded-full bg-blue-600 transition-[width] duration-500" style={{ width: `${progress}%` }} />
        </div>
        <span className="text-xs tabular-nums text-slate-600">{done}/{counted.length}</span>
      </div>
      <div className="mt-2">
        <TaskList tasks={sprint.tasks} today={today} onToggle={onToggleTask} />
      </div>
      {onAddTask ? <AddTaskRow onAdd={onAddTask} /> : null}
    </DeskCard>
  );
}

function AddTaskRow({ onAdd }: { onAdd: NonNullable<SprintCardProps["onAddTask"]> }) {
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    const saved = await onAdd({ title: title.trim(), dueDate: dueDate || undefined });
    setSaving(false);
    if (saved) {
      setTitle("");
      setDueDate("");
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
      <label htmlFor="desk-new-task" className="sr-only">New task</label>
      <input
        id="desk-new-task"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        maxLength={200}
        placeholder="Add a task…"
        className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500"
      />
      <label htmlFor="desk-new-task-due" className="sr-only">Due date</label>
      <input
        id="desk-new-task-due"
        type="date"
        value={dueDate}
        onChange={(event) => setDueDate(event.target.value)}
        className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm text-slate-700 outline-none focus:border-blue-500"
      />
      <button
        type="submit"
        disabled={!title.trim() || saving}
        className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300"
      >
        Add
      </button>
    </form>
  );
}

interface DeskCardProps {
  title: string;
  eyebrow?: string;
  aside?: ReactNode;
  children: ReactNode;
}

/** The frame every card on the right-hand panel shares. */
export function DeskCard({ title, eyebrow, aside, children }: DeskCardProps) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          {eyebrow ? (
            <p className="text-[11px] font-semibold uppercase tracking-widest text-blue-600">{eyebrow}</p>
          ) : null}
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        </div>
        {aside}
      </header>
      {children}
    </section>
  );
}
