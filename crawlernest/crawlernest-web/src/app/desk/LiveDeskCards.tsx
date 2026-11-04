"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { DeadlineList, DeskCard, SkillMasteryList, SprintCard, type DeskTask } from "@/components/desk";
import {
  createSprint,
  createTask,
  getCurrentSprint,
  listSkills,
  listTargets,
  recordSkillResult,
  setTaskStatus,
  type DeskApiFailure,
  type DeskApiResult,
  type LiveSkill,
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
  // Tasks with a save in flight. A second tick before the first returns would
  // carry the old revision and be refused as if another tab had changed it.
  const saving = useRef(new Set<string>());

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
    if (!task || saving.current.has(taskId)) return;
    const next = task.status === "done" ? "todo" : "done";
    // Functional updates, so a save that settles late does not undo another task's tick.
    const replaceTask = (row: DeskTask) =>
      setState((prev) => prev.phase !== "ready" || prev.data === null ? prev
        : { phase: "ready", data: { ...prev.data, tasks: prev.data.tasks.map((t) => (t.id === taskId ? row : t)) } });
    // Optimistic: the box ticks now, and goes back if the server refuses.
    replaceTask({ ...task, status: next });
    saving.current.add(taskId);
    const result = await setTaskStatus(taskId, next, task.revision);
    saving.current.delete(taskId);
    if (!result.ok) {
      replaceTask(task);
      if (result.reason === "conflict") {
        // Changed in another tab or by Tassel: show the stored sprint rather than a stale one.
        setActionError("That task was changed elsewhere, so the latest version is shown. Tick it again if you still want to.");
        load();
      } else {
        setActionError(result.message);
      }
      return;
    }
    setActionError(null);
    // Keep the server's row, so the next tick sends the new revision.
    if (result.data) replaceTask(result.data);
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
  const [state, setState, load] = useDeskLoad(listSkills);
  const [logging, setLogging] = useState<{ subject: string; unit: string } | null>(null);

  if (state.phase === "loading") {
    return <DeskCard eyebrow="Test prep" title="Skill mastery"><p className="text-sm text-slate-400">Loading.</p></DeskCard>;
  }
  if (state.phase === "failed") {
    return <DeskCard eyebrow="Test prep" title="Skill mastery"><FailureNotice failure={state.failure} onRetry={load} /></DeskCard>;
  }

  const skills = state.data;
  function saved(skill: LiveSkill) {
    setState({ phase: "ready", data: [...skills.filter((s) => !(s.subject === skill.subject && s.label === skill.label)), skill] });
    setLogging(null);
  }

  const form = (
    <RecordResultForm key={logging ? `${logging.subject}/${logging.unit}` : "new"} initial={logging} onSaved={saved}
      onCancel={logging ? () => setLogging(null) : undefined} />
  );

  if (skills.length === 0) {
    return (
      <DeskCard eyebrow="Test prep" title="Skill mastery">
        <p className="text-sm text-slate-500">No practice results yet. Record a practice set and mastery appears here.</p>
        {form}
      </DeskCard>
    );
  }

  const subjects = [...new Set(skills.map((skill) => skill.subject))].sort();
  return (
    <>
      {subjects.map((subject) => {
        const units = skills.filter((skill) => skill.subject === subject).sort((a, b) => a.label.localeCompare(b.label));
        // Pooled over questions, not averaged over units: a unit with 5 questions
        // should not count as much as one with 200.
        const attempted = units.reduce((n, u) => n + u.attempted, 0);
        const correct = units.reduce((n, u) => n + u.correct, 0);
        const overall = attempted > 0 ? Math.round((1000 * correct) / attempted) / 10 : 0;
        return (
          <DeskCard key={subject} eyebrow="Test prep" title={`${subject} mastery`}
            aside={<span className="text-xs tabular-nums text-slate-500">{overall}% of {attempted} questions</span>}>
            <SkillMasteryList skills={units} onPractice={(unit) => setLogging({ subject, unit })} />
            <p className="mt-2 text-xs text-slate-500">Share of practice questions answered correctly, per unit and overall.</p>
            {logging?.subject === subject ? form : null}
          </DeskCard>
        );
      })}
      {logging === null ? <DeskCard eyebrow="Test prep" title="Record practice">{form}</DeskCard> : null}
    </>
  );
}

function RecordResultForm({ initial, onSaved, onCancel }: {
  initial: { subject: string; unit: string } | null;
  onSaved: (skill: LiveSkill) => void;
  onCancel?: () => void;
}) {
  const [subject, setSubject] = useState(initial?.subject ?? "");
  const [unit, setUnit] = useState(initial?.unit ?? "");
  const [attempted, setAttempted] = useState("");
  const [correct, setCorrect] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const a = Number(attempted);
  const c = Number(correct);
  const valid = subject.trim() && unit.trim() && Number.isInteger(a) && a >= 1 && Number.isInteger(c) && c >= 0 && c <= a;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || saving) return;
    setSaving(true);
    const result = await recordSkillResult({ subject: subject.trim(), unit: unit.trim(), attempted: a, correct: c });
    setSaving(false);
    if (!result.ok || !result.data) {
      setError(result.ok ? "The result was saved but could not be read back." : result.message);
      return;
    }
    onSaved(result.data);
  }

  const input = "mt-1 block w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-blue-500";
  return (
    <form onSubmit={submit} className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 sm:grid-cols-4" aria-label="Record practice result">
      <label className="text-xs font-medium text-slate-600">Subject
        <input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={60} placeholder="SAT Math" className={input} />
      </label>
      <label className="text-xs font-medium text-slate-600">Unit
        <input value={unit} onChange={(e) => setUnit(e.target.value)} maxLength={80} placeholder="Algebra" className={input} />
      </label>
      <label className="text-xs font-medium text-slate-600">Questions
        <input type="number" min={1} max={1000} value={attempted} onChange={(e) => setAttempted(e.target.value)} className={input} />
      </label>
      <label className="text-xs font-medium text-slate-600">Correct
        <input type="number" min={0} max={1000} value={correct} onChange={(e) => setCorrect(e.target.value)} className={input} />
      </label>
      <div className="col-span-2 flex items-center gap-2 sm:col-span-4">
        <button type="submit" disabled={!valid || saving}
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300">
          Record result
        </button>
        {onCancel ? <button type="button" onClick={onCancel} className="text-sm text-slate-500 hover:underline">Cancel</button> : null}
        {attempted && correct && c > a ? <span className="text-xs text-red-700">Correct cannot exceed questions.</span> : null}
        {error ? <span role="alert" className="text-xs text-red-700">{error}</span> : null}
      </div>
    </form>
  );
}

// ─── Deadlines ───────────────────────────────────────────────────────────────

/** Stages after which a school's application deadline no longer needs watching. */
const DECIDED_STAGES = new Set(["submitted", "admitted", "waitlisted", "rejected", "enrolled", "withdrawn"]);

export function LiveDeadlinesCard({ today }: { today: Date }) {
  const [state, , load] = useDeskLoad(listTargets);

  if (state.phase === "loading") return null;
  if (state.phase === "failed") {
    // Signed out is already said by the sprint card above; say nothing twice.
    return state.failure.reason === "unauthenticated" ? null : (
      <DeskCard eyebrow="Timeline" title="Application deadlines"><FailureNotice failure={state.failure} onRetry={load} /></DeskCard>
    );
  }
  const todayIso = isoDate(today);
  const upcoming = state.data.filter((t) => t.deadline !== null && t.deadline >= todayIso && !DECIDED_STAGES.has(t.stage));
  if (upcoming.length === 0) return null;
  return (
    <DeskCard eyebrow="Timeline" title="Application deadlines">
      <DeadlineList
        today={today}
        deadlines={upcoming.slice(0, 8).map((t) => ({
          id: String(t.id),
          name: t.name,
          date: t.deadline as string,
          detail: [t.programmeName, t.stage].filter(Boolean).join(" · "),
        }))}
      />
      <p className="mt-2 text-xs text-slate-500">The deadlines you entered for schools on your list. Check each school&apos;s site: dates change every year.</p>
    </DeskCard>
  );
}
