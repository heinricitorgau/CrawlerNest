"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { DeskCard, EssayReviewResult } from "@/components/desk";
import {
  evaluateEssay,
  getEssay,
  listEssays,
  type DeskApiFailure,
  type EssayReview,
  type EssaySummary,
} from "@/lib/deskApi";

const MAX_DRAFT = 20000;

/** Split on whitespace, as the API counts; a preview, the stored count is the API's. */
function draftWords(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

function SignInPrompt() {
  return (
    <p className="text-sm text-slate-600">
      <Link href="/signin" className="font-medium text-blue-600 hover:underline">Sign in</Link> to have your drafts scored
      and kept.
    </p>
  );
}

/** The Essay review tab: submit a draft, see its review, pick an earlier draft to revise. */
export function EssayReviewPanel({ onModelCall }: { onModelCall?: () => void } = {}) {
  const [history, setHistory] = useState<EssaySummary[] | null>(null);
  const [failure, setFailure] = useState<DeskApiFailure | null>(null);
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState("");
  const [revisionOf, setRevisionOf] = useState<number | "">("");
  const [wordLimit, setWordLimit] = useState("");
  const [review, setReview] = useState<EssayReview | null>(null);
  const [scoring, setScoring] = useState(false);

  useEffect(() => {
    let live = true;
    void listEssays().then((result) => {
      if (!live) return;
      if (result.ok) setHistory(result.data);
      else setFailure(result);
    });
    return () => {
      live = false;
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !draft.trim() || scoring) return;
    setScoring(true);
    setFailure(null);
    const result = await evaluateEssay({
      essayTitle: title.trim(),
      essayPrompt: prompt.trim() || undefined,
      draftText: draft,
      revisionOfId: revisionOf === "" ? undefined : revisionOf,
      wordLimit: wordLimit ? Number(wordLimit) : undefined,
    });
    setScoring(false);
    onModelCall?.();
    if (!result.ok || result.data === null) {
      setFailure(result.ok ? { ok: false, reason: "unavailable", message: "The review could not be read." } : result);
      return;
    }
    const saved = result.data;
    setReview(saved);
    setHistory((prev) => [
      { id: saved.id, essayTitle: saved.essayTitle, overallScore: saved.overallScore, wordCount: saved.wordCount, createdAt: saved.evaluatedAt },
      ...(prev ?? []).filter((h) => h.id !== saved.id),
    ]);
  }

  async function open(id: number) {
    const result = await getEssay(id);
    if (result.ok && result.data) {
      setReview(result.data);
      setFailure(null);
    } else if (!result.ok) {
      setFailure(result);
    }
  }

  if (failure?.reason === "unauthenticated") {
    return <DeskCard eyebrow="Essay review" title="Score a draft"><SignInPrompt /></DeskCard>;
  }

  return (
    <>
      <DeskCard eyebrow="Essay review" title="Score a draft">
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-xs font-medium text-slate-600">
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required
              placeholder="Personal statement"
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Essay prompt (optional)
            <input value={prompt} onChange={(e) => setPrompt(e.target.value)} maxLength={2000}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500" />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Word limit (optional)
            <input type="number" min={1} max={5000} value={wordLimit} onChange={(e) => setWordLimit(e.target.value)}
              placeholder="650"
              className="mt-1 block w-32 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-blue-500" />
          </label>
          {history && history.length > 0 ? (
            <label className="block text-xs font-medium text-slate-600">
              This revises (optional)
              <select value={revisionOf} onChange={(e) => setRevisionOf(e.target.value === "" ? "" : Number(e.target.value))}
                className="mt-1 block w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm">
                <option value="">A new essay</option>
                {history.map((h) => (
                  <option key={h.id} value={h.id}>{h.essayTitle} ({h.createdAt.slice(0, 10)})</option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="block text-xs font-medium text-slate-600">
            Draft
            <textarea value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={MAX_DRAFT} required rows={10}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm leading-relaxed outline-none focus:border-blue-500" />
          </label>
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs tabular-nums text-slate-500">
              {draftWords(draft)} words{wordLimit ? ` of ${wordLimit}` : ""} · {draft.length.toLocaleString()} / {MAX_DRAFT.toLocaleString()} characters
            </span>
            <button type="submit" disabled={!title.trim() || !draft.trim() || scoring}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:bg-slate-300">
              {scoring ? "Scoring… (up to a minute)" : "Score draft"}
            </button>
          </div>
          {failure ? <p role="alert" className="text-sm text-red-700">{failure.message}</p> : null}
        </form>
      </DeskCard>

      {review ? (
        <DeskCard eyebrow="Review" title={review.essayTitle}>
          <EssayReviewResult review={review} />
        </DeskCard>
      ) : null}

      {history && history.length > 0 ? (
        <DeskCard eyebrow="History" title="Earlier reviews">
          <ul className="divide-y divide-slate-100">
            {history.map((h) => (
              <li key={h.id}>
                <button type="button" onClick={() => open(h.id)}
                  className="flex w-full items-center justify-between gap-3 py-2 text-left text-sm hover:bg-slate-50">
                  <span className="truncate text-slate-800">{h.essayTitle}</span>
                  <span className="shrink-0 tabular-nums text-slate-500">{h.overallScore} · {h.createdAt.slice(0, 10)}</span>
                </button>
              </li>
            ))}
          </ul>
        </DeskCard>
      ) : null}
    </>
  );
}

/** "Your desk": the latest review in brief, or a pointer to the Essay review tab. */
export function LatestEssayCard({ onOpenReviews }: { onOpenReviews: () => void }) {
  const [state, setState] = useState<{ review: EssayReview | null; failure: DeskApiFailure | null; loading: boolean }>(
    { review: null, failure: null, loading: true });

  useEffect(() => {
    let live = true;
    void (async () => {
      const list = await listEssays();
      if (!live) return;
      if (!list.ok) return setState({ review: null, failure: list, loading: false });
      if (list.data.length === 0) return setState({ review: null, failure: null, loading: false });
      const latest = await getEssay(list.data[0].id);
      if (!live) return;
      setState(latest.ok ? { review: latest.data, failure: null, loading: false } : { review: null, failure: latest, loading: false });
    })();
    return () => {
      live = false;
    };
  }, []);

  const openButton = (
    <button type="button" onClick={onOpenReviews} className="text-xs font-medium text-blue-600 hover:underline">
      Open essay review
    </button>
  );

  if (state.loading) {
    return <DeskCard eyebrow="Essay review" title="Latest draft"><p className="text-sm text-slate-400">Loading.</p></DeskCard>;
  }
  if (state.failure?.reason === "unauthenticated") {
    return <DeskCard eyebrow="Essay review" title="Latest draft"><SignInPrompt /></DeskCard>;
  }
  if (state.failure) {
    return <DeskCard eyebrow="Essay review" title="Latest draft"><p role="alert" className="text-sm text-red-700">{state.failure.message}</p></DeskCard>;
  }
  if (!state.review) {
    return (
      <DeskCard eyebrow="Essay review" title="No drafts scored yet" aside={openButton}>
        <p className="text-sm text-slate-500">Paste a draft on the Essay review tab to see it scored on impact, introspection, passion and originality.</p>
      </DeskCard>
    );
  }
  return (
    <DeskCard eyebrow="Essay review" title={state.review.essayTitle} aside={openButton}>
      <EssayReviewResult review={state.review} compact />
    </DeskCard>
  );
}
