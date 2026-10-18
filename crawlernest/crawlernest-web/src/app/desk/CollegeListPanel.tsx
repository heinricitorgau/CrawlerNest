"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { DeskCard } from "@/components/desk";
import {
  createTarget,
  deleteTarget,
  listTargets,
  updateTarget,
  type DeskApiFailure,
  type LiveTarget,
  type TargetPatch,
} from "@/lib/deskApi";

/** Must match DeskTargetService.STAGES / ROUNDS / BANDS (TasselToolsContractTest holds the tools to the same lists). */
const STAGES = ["researching", "shortlisted", "applying", "submitted", "admitted", "waitlisted", "rejected", "enrolled", "withdrawn"];
const ROUNDS = ["ED", "ED2", "EA", "REA", "RD", "rolling"];
const BANDS = ["reach", "target", "safety"];
const MAX_NOTES = 4000;

const input = "mt-1 block w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm outline-none focus:border-blue-500";

/**
 * The College list tab: the user's schools, each opening into an editor for its
 * stage, round, deadline, label and notes. Notes matter beyond this page: when
 * Tassel judges how a theme fits a school, it reads them, and a fit judged from
 * them is marked "from your notes" rather than "from the model's general knowledge".
 *
 * @param onChanged called after any save, so the desk's cards re-read the list
 */
export function CollegeListPanel({ onChanged }: { onChanged?: () => void }) {
  const [targets, setTargets] = useState<LiveTarget[] | null>(null);
  const [failure, setFailure] = useState<DeskApiFailure | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    void listTargets().then((result) => {
      if (!live) return;
      if (result.ok) setTargets(result.data);
      else setFailure(result);
    });
    return () => {
      live = false;
    };
  }, []);

  function replace(updated: LiveTarget) {
    setTargets((prev) => (prev ?? []).map((t) => (t.id === updated.id ? updated : t)));
    onChanged?.();
  }

  if (failure?.reason === "unauthenticated") {
    return (
      <DeskCard eyebrow="College list" title="Your schools">
        <p className="text-sm text-slate-600">
          <Link href="/signin" className="font-medium text-blue-600 hover:underline">Sign in</Link> to keep a list of schools.
        </p>
      </DeskCard>
    );
  }
  if (failure) {
    return <DeskCard eyebrow="College list" title="Your schools"><p role="alert" className="text-sm text-red-700">{failure.message}</p></DeskCard>;
  }
  if (!targets) {
    return <DeskCard eyebrow="College list" title="Your schools"><p className="text-sm text-slate-400">Loading.</p></DeskCard>;
  }

  return (
    <>
      <DeskCard eyebrow="College list" title={`Your schools (${targets.length})`}>
        {targets.length === 0 ? (
          <p className="text-sm text-slate-500">No schools yet. Add one below, or tell Tassel where you&apos;re applying.</p>
        ) : (
          <ul className="space-y-2" aria-label="Schools">
            {targets.map((t) => (
              <li key={t.id} className="rounded-lg border border-slate-200">
                <button type="button" aria-expanded={openId === t.id} onClick={() => setOpenId(openId === t.id ? null : t.id)}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-slate-50">
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-slate-800">{t.name}</span>
                    <span className="block truncate text-xs text-slate-500">
                      {[t.programmeName, t.stage, t.applicationRound, t.deadline ? `due ${t.deadline}` : null].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">{t.notes ? "Notes ✓" : "No notes"}</span>
                </button>
                {t.universityStatus === "merged" ? (
                  <p className="px-3 pb-2 text-xs text-amber-800">This school&apos;s record was merged into another one in CrawlerNest; remove it and add the school again.</p>
                ) : null}
                {openId === t.id ? (
                  <TargetEditor target={t} onSaved={replace}
                    onRemoved={() => { setTargets((prev) => (prev ?? []).filter((x) => x.id !== t.id)); setOpenId(null); onChanged?.(); }} />
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </DeskCard>
      <AddSchool onAdded={(t) => { setTargets((prev) => [...(prev ?? []), t]); setOpenId(t.id); onChanged?.(); }} />
    </>
  );
}

function TargetEditor({ target, onSaved, onRemoved }: {
  target: LiveTarget;
  onSaved: (t: LiveTarget) => void;
  onRemoved: () => void;
}) {
  const [stage, setStage] = useState(target.stage);
  const [round, setRound] = useState(target.applicationRound ?? "");
  const [deadline, setDeadline] = useState(target.deadline ?? "");
  const [band, setBand] = useState(target.userBand ?? "");
  const [notes, setNotes] = useState(target.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ error: boolean; text: string } | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  // Only what changed goes in the PATCH; an emptied field is sent as null, which clears it.
  const patch: TargetPatch = {};
  if (stage !== target.stage) patch.stage = stage;
  if ((round || null) !== target.applicationRound) patch.applicationRound = round || null;
  if ((deadline || null) !== target.deadline) patch.deadline = deadline || null;
  if ((band || null) !== target.userBand) patch.userBand = band || null;
  if ((notes.trim() || null) !== target.notes) patch.notes = notes.trim() || null;
  const dirty = Object.keys(patch).length > 0;

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!dirty || saving) return;
    setSaving(true);
    const result = await updateTarget(target.id, patch);
    setSaving(false);
    if (!result.ok || !result.data) {
      setMessage({ error: true, text: result.ok ? "Saved, but the school could not be read back." : result.message });
      return;
    }
    setMessage({ error: false, text: "Saved." });
    onSaved(result.data);
  }

  async function remove() {
    const result = await deleteTarget(target.id);
    if (result.ok) onRemoved();
    else setMessage({ error: true, text: result.message });
  }

  return (
    <form onSubmit={save} aria-label={`Edit ${target.name}`} className="space-y-3 border-t border-slate-100 px-3 py-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <label className="text-xs font-medium text-slate-600">Stage
          <select value={stage} onChange={(e) => setStage(e.target.value)} className={input}>
            {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">Round
          <select value={round} onChange={(e) => setRound(e.target.value)} className={input}>
            <option value="">Not set</option>
            {ROUNDS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">Your deadline
          <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={input} />
        </label>
        <label className="text-xs font-medium text-slate-600">Your label
          <select value={band} onChange={(e) => setBand(e.target.value)} className={input}>
            <option value="">None</option>
            {BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </label>
      </div>
      <label className="block text-xs font-medium text-slate-600">
        Notes
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={MAX_NOTES} rows={5}
          placeholder="What draws you to this school: programmes, people, the way it teaches, anything you've learned."
          className={`${input} leading-relaxed`} />
        <span className="mt-1 flex justify-between font-normal text-slate-500">
          <span>Tassel reads these notes when it judges how your themes fit this school.</span>
          <span className="tabular-nums">{notes.length} / {MAX_NOTES}</span>
        </span>
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" disabled={!dirty || saving}
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300">
          {saving ? "Saving…" : "Save"}
        </button>
        {confirmRemove ? (
          <>
            <button type="button" onClick={remove} className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white">Remove {target.name}</button>
            <button type="button" onClick={() => setConfirmRemove(false)} className="text-sm text-slate-500 hover:underline">Keep it</button>
          </>
        ) : (
          <button type="button" onClick={() => setConfirmRemove(true)} className="text-sm text-slate-500 hover:text-red-700">Remove…</button>
        )}
        {message ? <span role={message.error ? "alert" : "status"} className={`text-xs ${message.error ? "text-red-700" : "text-emerald-700"}`}>{message.text}</span> : null}
      </div>
    </form>
  );
}

function AddSchool({ onAdded }: { onAdded: (t: LiveTarget) => void }) {
  const [name, setName] = useState("");
  const [programme, setProgramme] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    const result = await createTarget({ customName: name.trim(), programmeName: programme.trim() || undefined });
    setSaving(false);
    if (!result.ok || !result.data) {
      setError(result.ok ? "Added, but the school could not be read back." : result.message);
      return;
    }
    setName("");
    setProgramme("");
    setError(null);
    onAdded(result.data);
  }

  return (
    <DeskCard eyebrow="College list" title="Add a school">
      <form onSubmit={submit} aria-label="Add a school" className="grid grid-cols-1 gap-2 sm:grid-cols-[2fr_2fr_auto] sm:items-end">
        <label className="text-xs font-medium text-slate-600">School
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={200} placeholder="University of Michigan" className={input} />
        </label>
        <label className="text-xs font-medium text-slate-600">Programme (optional)
          <input value={programme} onChange={(e) => setProgramme(e.target.value)} maxLength={200} placeholder="Computer Science" className={input} />
        </label>
        <button type="submit" disabled={!name.trim() || saving}
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300">
          Add
        </button>
        {error ? <p role="alert" className="text-xs text-red-700 sm:col-span-3">{error}</p> : null}
      </form>
    </DeskCard>
  );
}
