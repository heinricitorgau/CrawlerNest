"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DeskCard, ResonanceBar, ThemeCard } from "@/components/desk";
import {
  decideTheme,
  generateResonance,
  generateThemes,
  getNarrative,
  type DeskApiFailure,
  type DeskApiResult,
  type Narrative,
} from "@/lib/deskApi";

const button = "rounded-lg px-3 py-1.5 text-sm font-medium disabled:opacity-50";

/**
 * Themes drawn from the user's drafts, and how each accepted theme resonates with
 * the schools on their list. Every action returns the whole narrative, so what is
 * shown is always one consistent state. The caveats travel with it.
 */
export function LiveNarrativeCard({ onModelCall }: { onModelCall?: () => void } = {}) {
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [failure, setFailure] = useState<DeskApiFailure | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void getNarrative().then((result) => {
      if (!live) return;
      if (result.ok) setNarrative(result.data);
      else setFailure(result);
    });
    return () => {
      live = false;
    };
  }, []);

  async function run(label: string, action: () => Promise<DeskApiResult<Narrative>>) {
    setBusy(label);
    const result = await action();
    setBusy(null);
    onModelCall?.();
    if (result.ok) {
      setNarrative(result.data);
      setFailure(null);
    } else {
      setFailure(result);
    }
  }

  if (failure?.reason === "unauthenticated") {
    return (
      <DeskCard eyebrow="Narrative" title="Your story">
        <p className="text-sm text-slate-600">
          <Link href="/signin" className="font-medium text-blue-600 hover:underline">Sign in</Link> to find the themes in your writing.
        </p>
      </DeskCard>
    );
  }
  if (!narrative) {
    return failure ? (
      <DeskCard eyebrow="Narrative" title="Your story"><p role="alert" className="text-sm text-red-700">{failure.message}</p></DeskCard>
    ) : null;
  }

  const accepted = narrative.themes.filter((t) => t.status === "accepted");
  const suggested = narrative.themes.filter((t) => t.status === "suggested");
  const error = failure ? <p role="alert" className="text-sm text-red-700">{failure.message}</p> : null;

  return (
    <section aria-label="Narrative" className="space-y-3">
      {narrative.themes.length === 0 ? (
        <DeskCard eyebrow="Narrative" title="Find your story">
          <p className="text-sm text-slate-600">Tassel reads your reviewed essay drafts and names the thread that runs through them.</p>
          <div className="mt-3 flex items-center gap-3">
            <button type="button" disabled={busy !== null} onClick={() => run("themes", generateThemes)}
              className={`${button} bg-slate-900 text-white`}>
              {busy === "themes" ? "Reading your drafts…" : "Find my themes"}
            </button>
          </div>
          {error}
        </DeskCard>
      ) : null}

      {[...accepted, ...suggested].map((theme) => (
        <ThemeCard key={theme.id} title={theme.title} summary={theme.summary} traits={theme.traits}
          evidence={theme.quotes} status={theme.status === "suggested" ? "suggested" : "accepted"}
          actions={theme.status === "suggested" ? (
            <>
              <button type="button" disabled={busy !== null} onClick={() => run(`accept-${theme.id}`, () => decideTheme(theme.id, "accepted"))}
                className={`${button} bg-white text-slate-900`}>Keep this theme</button>
              <button type="button" disabled={busy !== null} onClick={() => run(`dismiss-${theme.id}`, () => decideTheme(theme.id, "dismissed"))}
                className={`${button} text-slate-300 hover:text-white`}>Dismiss</button>
            </>
          ) : undefined} />
      ))}

      {narrative.themes.length > 0 ? (
        <DeskCard eyebrow="Resonance" title="Fit with your schools"
          aside={
            <button type="button" disabled={busy !== null} onClick={() => run("themes", generateThemes)}
              className="text-xs font-medium text-blue-600 hover:underline disabled:opacity-50">
              {busy === "themes" ? "Reading…" : "Look for new themes"}
            </button>
          }>
          {accepted.length === 0 ? (
            <p className="text-sm text-slate-500">Keep a theme above, and its fit with each school on your list can be assessed.</p>
          ) : narrative.resonance.length === 0 ? (
            <p className="text-sm text-slate-500">Not assessed yet.</p>
          ) : (
            <div className="space-y-4">
              {narrative.resonance.map((r) => (
                <ResonanceBar key={`${r.themeId}-${r.targetEntityId}`}
                  trait={accepted.find((t) => t.id === r.themeId)?.title ?? "Theme"}
                  institution={r.institution} level={r.level}
                  note={`${r.rationale} ${r.institutionBasis === "user_notes" ? "(From your notes.)" : "(From the model's general knowledge.)"}`} />
              ))}
            </div>
          )}
          {accepted.length > 0 ? (
            <button type="button" disabled={busy !== null} onClick={() => run("resonance", generateResonance)}
              className={`${button} mt-4 bg-slate-900 text-white`}>
              {busy === "resonance" ? "Assessing…" : narrative.resonance.length ? "Reassess fit" : "Assess fit with my schools"}
            </button>
          ) : null}
          {error}
        </DeskCard>
      ) : null}

      {narrative.caveats.length > 0 ? (
        <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          {narrative.caveats.map((c) => <p key={c}>{c}</p>)}
        </div>
      ) : null}
    </section>
  );
}
