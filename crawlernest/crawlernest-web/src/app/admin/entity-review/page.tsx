"use client";

import { useCallback, useEffect, useState } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ReviewCandidate {
  sourceCode: string;
  sourceEntityId: string;
  sourceName: string;
  sourceCountry: string | null;
  matchedCanonicalUniversityId: number | null;
  matchedCanonicalName: string | null;
  matchedCanonicalCountry: string | null;
  matchMethod: string;
  confidenceScore: number | null;
  tokenOverlap: number | null;
  countryMismatch: boolean | null;
  suspiciousMerge: boolean | null;
  candidateCountHint: number | null;
  existingDecision: string | null;
}

interface ReviewPayload {
  items: ReviewCandidate[];
  totalPending: number;
  caveats: string[];
}

interface CanonicalOption {
  canonicalUniversityId: number;
  displayName: string;
  country: string | null;
}

type Decision = "confirmed" | "rejected" | "remapped";

type LoadState =
  | { status: "loading" }
  | { status: "ok"; data: ReviewPayload }
  | { status: "error"; message: string };

// ── Helpers ───────────────────────────────────────────────────────────────────

function candidateKey(candidate: ReviewCandidate): string {
  return `${candidate.sourceCode}:${candidate.sourceEntityId}`;
}

function formatScore(score: number | null): string {
  return score === null ? "—" : score.toFixed(4);
}

// ── UI primitives ─────────────────────────────────────────────────────────────

function Flag({ label, active }: { label: string; active: boolean | null }) {
  if (!active) return null;
  return (
    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-800">
      {label}
    </span>
  );
}

function CaveatList({ caveats }: { caveats: string[] }) {
  if (caveats.length === 0) return null;
  return (
    <div className="mb-6 rounded border border-slate-200 bg-slate-50 p-4">
      <h2 className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-600">
        What this screen does and does not do
      </h2>
      <ul className="list-disc space-y-1 pl-5 text-xs text-slate-600">
        {caveats.map((caveat) => (
          <li key={caveat}>{caveat}</li>
        ))}
      </ul>
    </div>
  );
}

// ── Remap picker ──────────────────────────────────────────────────────────────

function RemapPicker({
  onPick,
  disabled,
}: {
  onPick: (canonicalUniversityId: number) => void;
  disabled: boolean;
}) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<CanonicalOption[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setOptions([]);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const timer = setTimeout(() => {
      fetch(`/api/admin/mapping-reviews/canonical-search?q=${encodeURIComponent(trimmed)}`, {
        cache: "no-store",
      })
        .then(async (res) => {
          const json = (await res.json()) as { data?: { items?: CanonicalOption[] } };
          if (!cancelled) setOptions(json.data?.items ?? []);
        })
        .catch(() => {
          if (!cancelled) setOptions([]);
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query]);

  return (
    <div className="mt-3 rounded border border-slate-200 bg-white p-3">
      <label className="block text-[11px] font-medium uppercase tracking-wide text-slate-500">
        Remap to a different university
      </label>
      <input
        type="text"
        value={query}
        disabled={disabled}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Type at least two characters…"
        className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm"
      />
      {searching && <p className="mt-1 text-xs text-slate-400">Searching…</p>}
      {options.length > 0 && (
        <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto">
          {options.map((option) => (
            <li key={option.canonicalUniversityId}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onPick(option.canonicalUniversityId)}
                className="w-full rounded px-2 py-1 text-left text-sm hover:bg-slate-100 disabled:opacity-50"
              >
                <span className="font-medium text-slate-800">{option.displayName}</span>
                <span className="ml-2 text-xs text-slate-500">
                  {option.country ?? "—"} · id {option.canonicalUniversityId}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Candidate card ────────────────────────────────────────────────────────────

function CandidateCard({
  candidate,
  busy,
  onDecide,
}: {
  candidate: ReviewCandidate;
  busy: boolean;
  onDecide: (
    candidate: ReviewCandidate,
    decision: Decision,
    decidedCanonicalUniversityId: number | null,
    note: string
  ) => void;
}) {
  const [showRemap, setShowRemap] = useState(false);
  const [note, setNote] = useState("");

  return (
    <li className="rounded border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] font-bold text-white">
          {candidate.sourceCode}
        </span>
        <span className="text-[11px] text-slate-400">{candidate.sourceEntityId}</span>
        <Flag label="country mismatch" active={candidate.countryMismatch} />
        <Flag label="suspicious merge" active={candidate.suspiciousMerge} />
        {candidate.existingDecision && (
          <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[11px] font-medium text-sky-800">
            decided: {candidate.existingDecision}
          </span>
        )}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-400">Source says</p>
          <p className="text-sm font-medium text-slate-900">{candidate.sourceName}</p>
          <p className="text-xs text-slate-500">{candidate.sourceCountry ?? "—"}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-400">Matched to</p>
          <p className="text-sm font-medium text-slate-900">
            {candidate.matchedCanonicalName ?? "—"}
          </p>
          <p className="text-xs text-slate-500">
            {candidate.matchedCanonicalCountry ?? "—"}
            {candidate.matchedCanonicalUniversityId !== null &&
              ` · id ${candidate.matchedCanonicalUniversityId}`}
          </p>
        </div>
      </div>

      <p className="mt-3 text-xs text-slate-500">
        {candidate.matchMethod} · score {formatScore(candidate.confidenceScore)} · token overlap{" "}
        {formatScore(candidate.tokenOverlap)} · {candidate.candidateCountHint ?? "?"} candidates
        considered
      </p>

      <input
        type="text"
        value={note}
        disabled={busy}
        onChange={(event) => setNote(event.target.value)}
        placeholder="Note (optional) — why this call?"
        className="mt-3 w-full rounded border border-slate-300 px-2 py-1 text-sm"
      />

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            onDecide(candidate, "confirmed", candidate.matchedCanonicalUniversityId, note)
          }
          className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          Confirm
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDecide(candidate, "rejected", null, note)}
          className="rounded bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-700 disabled:opacity-50"
        >
          Reject
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setShowRemap((open) => !open)}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
        >
          {showRemap ? "Cancel remap" : "Remap…"}
        </button>
      </div>

      {showRemap && (
        <RemapPicker
          disabled={busy}
          onPick={(canonicalUniversityId) =>
            onDecide(candidate, "remapped", canonicalUniversityId, note)
          }
        />
      )}
    </li>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function EntityReviewPage() {
  const [status, setStatus] = useState<"pending" | "decided">("pending");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(() => {
    setState({ status: "loading" });
    fetch(`/api/admin/mapping-reviews?status=${status}&limit=50`, { cache: "no-store" })
      .then(async (res) => {
        const json = (await res.json()) as {
          success?: boolean;
          data?: ReviewPayload;
          error?: string;
        };
        if (!res.ok || json.success === false || !json.data) {
          setState({ status: "error", message: json.error ?? `HTTP ${res.status}` });
          return;
        }
        setState({ status: "ok", data: json.data });
      })
      .catch((err: unknown) => {
        setState({
          status: "error",
          message: err instanceof Error ? err.message : "Fetch failed",
        });
      });
  }, [status]);

  useEffect(load, [load]);

  const decide = useCallback(
    (
      candidate: ReviewCandidate,
      decision: Decision,
      decidedCanonicalUniversityId: number | null,
      note: string
    ) => {
      setBusyKey(candidateKey(candidate));
      setFlash(null);
      fetch("/api/admin/mapping-reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sourceCode: candidate.sourceCode,
          sourceEntityId: candidate.sourceEntityId,
          decision,
          decidedCanonicalUniversityId:
            decision === "rejected" ? null : decidedCanonicalUniversityId,
          note: note.trim() === "" ? null : note.trim(),
        }),
      })
        .then(async (res) => {
          const json = (await res.json()) as { success?: boolean; error?: string };
          if (!res.ok || json.success === false) {
            setFlash(json.error ?? `HTTP ${res.status}`);
            return;
          }
          setFlash(
            `Recorded ${decision} for ${candidate.sourceName}. It takes effect on the next ingestion.`
          );
          load();
        })
        .catch((err: unknown) => {
          setFlash(err instanceof Error ? err.message : "Request failed");
        })
        .finally(() => setBusyKey(null));
    },
    [load]
  );

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-lg font-bold text-slate-900">Entity resolution review</h1>
        <p className="mt-1 text-sm text-slate-500">
          Fuzzy matches the resolver was unsure about. Sampling found most of them wrong, so each
          one needs a person.
        </p>
      </header>

      <div className="mb-4 flex gap-2">
        {(["pending", "decided"] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setStatus(option)}
            className={
              status === option
                ? "rounded bg-slate-800 px-3 py-1.5 text-sm font-medium text-white"
                : "rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
            }
          >
            {option === "pending" ? "Pending" : "Decided"}
          </button>
        ))}
      </div>

      {flash && (
        <p className="mb-4 rounded border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700">
          {flash}
        </p>
      )}

      {state.status === "loading" && <p className="text-sm text-slate-500">Loading…</p>}

      {state.status === "error" && (
        <div className="rounded border border-rose-200 bg-rose-50 p-4">
          <p className="text-sm font-medium text-rose-800">{state.message}</p>
          <p className="mt-1 text-xs text-rose-700">
            This screen is restricted to configured reviewers. Sign in with a reviewer account, and
            make sure crawlernest.reviewer.emails lists it on the API server.
          </p>
        </div>
      )}

      {state.status === "ok" && (
        <>
          <CaveatList caveats={state.data.caveats} />
          <p className="mb-3 text-xs text-slate-500">
            {state.data.totalPending} match{state.data.totalPending === 1 ? "" : "es"} still awaiting
            a decision.
          </p>
          {state.data.items.length === 0 ? (
            <p className="rounded border border-slate-200 bg-white p-4 text-sm text-slate-500">
              Nothing here.
            </p>
          ) : (
            <ul className="space-y-3">
              {state.data.items.map((candidate) => (
                <CandidateCard
                  key={candidateKey(candidate)}
                  candidate={candidate}
                  busy={busyKey === candidateKey(candidate)}
                  onDecide={decide}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  );
}
