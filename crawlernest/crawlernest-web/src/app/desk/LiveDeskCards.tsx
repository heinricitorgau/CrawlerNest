"use client";

import Link from "next/link";
import { useEffect, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { DeskCard, SkillMasteryList, SprintCard } from "@/components/desk";
import {
  createSprint,
  createTask,
  getCurrentSprint,
  listSkills,
  setTaskStatus,
  type DeskApiFailure,
  type DeskApiResult,
  type LiveSprint,
} from "@/lib/deskApi";

type Load<T> = { phase: "loading" } | { phase: "ready"; data: T } | { phase: "failed"; failure: DeskApiFailure };

/**
 * Loads once on mount and again on retry. State is set only when the request
 * settles (never synchronously in the effect), and not at all after unmount.
 */
function useDeskLoad<T>(
  fetcher: () => Promise<DeskApiResult<T>>,
): [Load<T>, Dispatch<SetStateAction<Load<T>>>, () => void] {
  const [state, setState] = useState<Load<T>>({ phase: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    void fetcher().then((result) => {
      if (live) setState(result.ok ? { phase: "ready", data: result.data } : { phase: "failed", failure: result });
    });
    return () => {
      live = false;
    };
  }, [fetcher, attempt]);

  const retry = () => {
    setState({ phase: "loading" });
    setAttempt((n) => n + 1);
  };
  return [state, setState, retry];
}

/** What a card shows instead of data: a sign-in prompt, or the server's error. */
function FailureNotice({ failure, onRetry }: { failure: DeskApiFailure; onRetry: () => void }) {
  if (failure.reason === "unauthenticated") {
    return (
      <p className="text-sm text-slate-600">
        <Link href="/signin" className="font-medium text-blue-600 hover:underline">Sign in</Link> to see your own
        tasks and progress.
      </p>
    );
  }
  return (
    <div role="alert" className="flex items-center justify-between gap-3 text-sm text-red-700">
      <span>{failure.message}</span>
      <button type="button" onClick={onRetry} className="shrink-0 rounded-md border border-red-200 px-2 py-1 text-xs">
        Retry
      </button>
    </div>
  );
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

// ─── Sprint ──────────────────────────────────────────────────────────────────

export function LiveSprintCard({ today }: { today: Date }) {
  const [state, setState, load] = useDeskLoad(getCurrentSprint);
  const [actionError, setActionError] = useState<string | null>(null);

  if (state.phase === "loading") {
    return <DeskCard eyebrow="Priority sprint" title="Loading…"><p className="text-sm text-slate-400">Loading your sprint.</p></DeskCard>;
  }
  if (state.phase === "failed") {
    return <DeskCard eyebrow="Priority sprint" title="Your sprint"><FailureNotice failure={state.failure} onRetry={load} /></DeskCard>;
  }
  if (state.data === null) {
    return <StartSprint today={today} onStarted={(sprint) => setState({ phase: "ready", data: sprint })} />;
  }

  const sprint = state.data;

  async function toggle(taskId: string) {
    const task = sprint.tasks.find((t) => t.id === taskId);
    if (!task) return;
    const next = task.status === "done" ? "todo" : "done";
    const apply = (status: typeof next | typeof task.status) =>
      setState({ phase: "ready", data: { ...sprint, tasks: sprint.tasks.map((t) => (t.id === taskId ? { ...t, status } : t)) } });
    // Optimistic: the box ticks now, and goes back if the server refuses.
    apply(next);
    const result = await setTaskStatus(taskId, next);
    if (!result.ok) {
      apply(task.status);
      setActionError(result.message);
    } else {
      setActionError(null);
    }
  }

  async function add(input: { title: string; dueDate?: string }) {
    const result = await createTask({ ...input, sprintId: sprint.id });
    if (!result.ok || result.data === null) {
      setActionError(result.ok ? "The task was saved but could not be read back." : result.message);
      return false;
    }
    setActionError(null);
    setState({ phase: "ready", data: { ...sprint, tasks: [...sprint.tasks, result.data] } });
    return true;
  }

  return (
    <div className="space-y-2">
      <SprintCard sprint={sprint} today={today} onToggleTask={toggle} onAddTask={add} />
      {actionError ? <p role="alert" className="px-1 text-xs text-red-700">{actionError}</p> : null}
    </div>
  );
}

function StartSprint({ today, onStarted }: { today: Date; onStarted: (sprint: LiveSprint) => void }) {
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [endDate, setEndDate] = useState(() => isoDate(new Date(today.getTime() + 13 * 86_400_000)));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    const result = await createSprint({ title: title.trim(), goal: goal.trim() || undefined, startDate: isoDate(today), endDate });
    setSaving(false);
    if (!result.ok || result.data === null) {
      setError(result.ok ? "The sprint was saved but could not be read back." : result.message);
      return;
    }
    onStarted(result.data);
  }

  return (
    <DeskCard eyebrow="Priority sprint" title="No sprint covers today">
      <form onSubmit={submit} className="space-y-2">
        <p className="text-sm text-slate-600">Start one: name the push and when it ends.</p>
        <label className="block text-xs font-medium text-slate-600">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} required
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500" />
        </label>
        <label className="block text-xs font-medium text-slate-600">
          Goal (optional)
          <input value={goal} onChange={(e) => setGoal(e.target.value)} maxLength={500}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500" />
        </label>
        <label className="block text-xs font-medium text-slate-600">
          Ends
          <input type="date" value={endDate} min={isoDate(today)} onChange={(e) => setEndDate(e.target.value)} required
            className="mt-1 block rounded-lg border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-blue-500" />
        </label>
        {error ? <p role="alert" className="text-xs text-red-700">{error}</p> : null}
        <button type="submit" disabled={!title.trim() || saving}
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300">
          Start sprint
        </button>
      </form>
    </DeskCard>
  );
}

// ─── Skills ──────────────────────────────────────────────────────────────────

export function LiveSkillsCard() {
  const [state, , load] = useDeskLoad(listSkills);

  if (state.phase === "loading") {
    return <DeskCard eyebrow="Test prep" title="Skill mastery"><p className="text-sm text-slate-400">Loading.</p></DeskCard>;
  }
  if (state.phase === "failed") {
    return <DeskCard eyebrow="Test prep" title="Skill mastery"><FailureNotice failure={state.failure} onRetry={load} /></DeskCard>;
  }
  if (state.data.length === 0) {
    return (
      <DeskCard eyebrow="Test prep" title="Skill mastery">
        <p className="text-sm text-slate-500">No practice results yet. Mastery appears here once you record some.</p>
      </DeskCard>
    );
  }

  const subjects = [...new Set(state.data.map((skill) => skill.subject))];
  return (
    <>
      {subjects.map((subject) => (
        <DeskCard key={subject} eyebrow="Test prep" title={`${subject} mastery`}>
          <SkillMasteryList skills={state.data.filter((skill) => skill.subject === subject)} />
          <p className="mt-2 text-xs text-slate-500">Share of practice questions answered correctly, per unit.</p>
        </DeskCard>
      ))}
    </>
  );
}
