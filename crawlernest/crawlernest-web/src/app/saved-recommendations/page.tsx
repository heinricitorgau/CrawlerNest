"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuthPlaceholder";
import { AUTH_MESSAGES } from "@/lib/authMessages";
import { STANDARD_CAVEATS, editionCaveats } from "@/lib/caveatMessages";
import { DATASET_YEARS } from "@/lib/datasetScope";

/**
 * The ranking edition a saved snapshot was computed against, or null when the
 * snapshot does not record one.
 *
 * A saved plan is a stored result, not a live query: it cannot be switched to
 * another edition, only labelled with the one it used. Plans saved before the
 * edition was recorded carry no year, and are labelled as such rather than
 * assumed to be the current edition -- which is exactly the claim that would age
 * badly, since the newest edition changes under them.
 */
export function savedEdition(
  requestJson: Record<string, unknown> | undefined,
  resultJson: Record<string, unknown> | undefined,
): number | null {
  const fromRequest = requestJson?.rankingYear;
  const metadata = (resultJson as { metadata?: Record<string, unknown> } | undefined)?.metadata;
  const fromResult = metadata?.ranking_year;
  for (const value of [fromRequest, fromResult]) {
    const year = typeof value === "string" ? Number(value) : value;
    if (typeof year === "number" && Number.isInteger(year) && DATASET_YEARS.includes(year)) {
      return year;
    }
  }
  return null;
}

/** What a snapshot discloses: its own edition when recorded, else the editions held. */
export function savedCaveats(edition: number | null): string[] {
  return edition == null ? STANDARD_CAVEATS : editionCaveats(edition);
}

type RecommendationSummary = {
  id: number;
  title: string;
  createdAt: string;
  requestSummary: string | null;
  topRecommendationName: string | null;
};

type RecommendationDetail = {
  id: number;
  title: string;
  createdAt: string;
  requestJson: Record<string, unknown>;
  resultJson: Record<string, unknown>;
};

type ListState =
  | { phase: "loading" }
  | { phase: "ok"; items: RecommendationSummary[] }
  | { phase: "session_expired" }
  | { phase: "unavailable" };

function LoadingShell() {
  return (
    <main className="min-h-screen bg-(--color-paper)">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <div className="animate-pulse space-y-4">
          <div className="h-10 w-64 rounded-2xl bg-(--color-paper-2)" />
          <div className="h-28 rounded-2xl bg-(--color-paper-2)" />
          <div className="h-28 rounded-2xl bg-(--color-paper-2)" />
        </div>
      </div>
    </main>
  );
}

function SignInPrompt({ message }: { message?: string }) {
  return (
    <main className="min-h-screen bg-(--color-paper) flex items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border border-(--color-rule) bg-white px-8 py-10 shadow-sm text-center">
        <div className="mx-auto mb-5 inline-flex h-12 w-12 items-center justify-center bg-(--color-paper-2)">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
            stroke="#3d7a5a" strokeWidth="2.5" strokeLinecap="round"
            strokeLinejoin="round" aria-hidden="true">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <h1 className="text-xl font-bold text-(--color-ink)">Sign in to view saved plans</h1>
        <p className="mt-2 text-sm text-(--color-muted)">
          {message ?? "Your saved recommendation plans are tied to your account."}
        </p>
        <Link
          href="/signin"
          className="mt-6 inline-block w-full rounded-lg bg-(--color-ink) px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-(--color-ink-2)"
        >
          Sign in
        </Link>
        <p className="mt-4 text-sm text-(--color-muted)">
          {"Don't have an account? "}
          <Link href="/signup" className="font-medium text-(--color-ink-2) underline-offset-4 hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}

function UnavailableBanner() {
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-800 text-sm">
      <div className="font-medium">{AUTH_MESSAGES.loadFailed}</div>
      <div className="mt-1 text-amber-700">Please try refreshing the page.</div>
    </div>
  );
}

type SnapshotUniversity = {
  universityName?: string;
  explanation?: string;
  recommendationExplain?: {
    reasons?: string[];
    warnings?: string[];
    dimensions?: {
      rankingFit?: number;
      riskFit?: number;
      languageFit?: number;
      dataConfidence?: number;
    };
  };
};

function SnapshotEvidenceSection({ items, edition }: { items: SnapshotUniversity[]; edition: number | null }) {
  const withEvidence = items.filter((u) => u.recommendationExplain);
  if (withEvidence.length === 0) {
    return (
      <p className="mt-3 text-xs text-(--color-muted) italic">
        Evidence details were not stored in this snapshot.
      </p>
    );
  }
  return (
    <div className="mt-3 space-y-3">
      {withEvidence.map((u, i) => (
        <div key={i} className="rounded-lg border border-(--color-rule) bg-white p-3">
          <div className="mb-1 text-xs font-semibold text-(--color-ink)">{u.universityName ?? "—"}</div>
          {u.recommendationExplain?.reasons?.map((r, j) => (
            <div key={j} className="text-xs text-(--color-ink-2)">✓ {r}</div>
          ))}
          {u.recommendationExplain?.warnings?.map((w, j) => (
            <div key={j} className="text-xs text-(--color-error)">⚠ {w}</div>
          ))}
        </div>
      ))}
      <div className="mt-2">
        <div className="mb-1 text-xs font-semibold text-(--color-error)">
          Data Caveats
        </div>
        <ul className="space-y-0.5">
          {savedCaveats(edition).map((c) => (
            <li key={c} className="text-xs text-(--color-error)">· {c}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function DetailPanel({ detail, onClose }: { detail: RecommendationDetail; onClose: () => void }) {
  const req = detail.requestJson ?? {};
  const result = detail.resultJson as {
    data?: {
      reach?: SnapshotUniversity[];
      target?: SnapshotUniversity[];
      safety?: SnapshotUniversity[];
    };
  };
  const reach = result?.data?.reach ?? [];
  const target = result?.data?.target ?? [];
  const safety = result?.data?.safety ?? [];
  const allItems = [...reach, ...target, ...safety];
  const edition = savedEdition(detail.requestJson, detail.resultJson);

  return (
    <div className="mt-4 rounded-2xl border border-(--color-accent-soft) bg-(--color-paper) p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="text-base font-semibold text-(--color-ink)">Plan Detail</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-(--color-muted) underline-offset-4 hover:underline"
        >
          Close
        </button>
      </div>

      <div className="mb-4 rounded-xl border border-(--color-rule) bg-white px-3 py-2 text-xs text-(--color-muted)">
        {edition != null ? (
          <>
            Ranked against the <span className="font-semibold text-(--color-ink)">{edition}</span> edition, as it stood when
            this plan was saved. Newer editions may rank these universities differently.
          </>
        ) : (
          <>
            This plan does not record which ranking edition it used; it was saved before that was stored. It cannot be
            attributed to any one edition.
          </>
        )}
      </div>

      <div className="mb-4">
        <div className="text-xs font-semibold text-(--color-muted) mb-2">Profile</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-(--color-ink)">
          {req.country ? <span>Country: <span className="font-medium">{String(req.country)}</span></span> : null}
          {req.ielts != null ? <span>IELTS: <span className="font-medium">{String(req.ielts)}</span></span> : null}
          {req.targetRank != null ? <span>Target Rank: <span className="font-medium">#{String(req.targetRank)}</span></span> : null}
          {req.riskProfile ? <span>Risk: <span className="font-medium capitalize">{String(req.riskProfile)}</span></span> : null}
          {req.selectedPlan ? <span>Plan: <span className="font-medium capitalize">{String(req.selectedPlan)}</span></span> : null}
        </div>
      </div>

      {(reach.length > 0 || target.length > 0 || safety.length > 0) ? (
        <div className="space-y-3">
          {reach.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-(--color-muted) mb-1">Reach</div>
              <ul className="space-y-1">
                {reach.map((u, i) => (
                  <li key={i} className="text-sm text-(--color-ink)">{u.universityName ?? "—"}</li>
                ))}
              </ul>
            </div>
          )}
          {target.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-(--color-muted) mb-1">Target</div>
              <ul className="space-y-1">
                {target.map((u, i) => (
                  <li key={i} className="text-sm text-(--color-ink)">{u.universityName ?? "—"}</li>
                ))}
              </ul>
            </div>
          )}
          {safety.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-(--color-muted) mb-1">Safety</div>
              <ul className="space-y-1">
                {safety.map((u, i) => (
                  <li key={i} className="text-sm text-(--color-ink)">{u.universityName ?? "—"}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-(--color-muted)">No university data in this snapshot.</p>
      )}

      {/* Evidence section */}
      {allItems.length > 0 && (
        <div className="mt-4 border-t border-(--color-rule) pt-4">
          <div className="text-xs font-semibold text-(--color-muted) mb-1">
            Evidence Details
          </div>
          <SnapshotEvidenceSection items={allItems} edition={edition} />
        </div>
      )}
    </div>
  );
}

function SavedList({ items, onDelete, onSessionExpired }: {
  items: RecommendationSummary[];
  onDelete: (id: number) => void;
  onSessionExpired: () => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RecommendationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  async function handleToggleDetail(id: number) {
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      setDetailError(null);
      return;
    }
    setExpandedId(id);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      const res = await fetch(`/api/user/saved-recommendations/${id}`, {
        credentials: "include",
        cache: "no-store",
      });
      if (res.ok) {
        const json = (await res.json()) as { data?: RecommendationDetail };
        setDetail(json.data ?? null);
      } else if (res.status === 401) {
        onSessionExpired();
      } else {
        setDetailError(AUTH_MESSAGES.loadFailed);
      }
    } catch {
      setDetailError(AUTH_MESSAGES.loadFailed);
    } finally {
      setDetailLoading(false);
    }
  }

  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-(--color-rule) bg-white p-8 text-center shadow-sm">
        <p className="text-(--color-muted)">No saved plans yet.</p>
        <p className="mt-1 text-sm text-(--color-muted)">
          Use the <span className="font-medium text-(--color-ink)">Save plan</span> button on the recommendations page.
        </p>
        <Link
          href="/recommendations"
          className="mt-6 inline-block border border-(--color-ink-2) px-5 py-2.5 text-sm font-semibold text-(--color-ink) transition hover:bg-(--color-paper-2)"
        >
          Generate Recommendations
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.id} className="rounded-2xl border border-(--color-rule) bg-white px-5 py-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="text-base font-semibold text-(--color-ink)">{item.title}</div>
              {item.requestSummary ? (
                <div className="mt-1 text-sm text-(--color-muted)">{item.requestSummary}</div>
              ) : null}
              {item.topRecommendationName ? (
                <div className="mt-1 text-xs text-(--color-ink-2) font-medium">
                  Top: {item.topRecommendationName}
                </div>
              ) : null}
              <div className="mt-2 text-xs text-(--color-muted)">
                {new Date(item.createdAt).toLocaleDateString("en-CA", { dateStyle: "medium" })}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => void handleToggleDetail(item.id)}
                className="border border-(--color-rule) bg-white px-3 py-1.5 text-xs font-medium text-(--color-ink) transition hover:border-(--color-ink-2) hover:bg-(--color-paper-2)"
              >
                {expandedId === item.id ? "Hide" : "View"}
              </button>
              <button
                type="button"
                onClick={() => onDelete(item.id)}
                className="border border-(--color-rule) bg-white px-3 py-1.5 text-xs font-medium text-(--color-ink) transition hover:border-red-300 hover:bg-red-50 hover:text-red-700"
              >
                Delete
              </button>
            </div>
          </div>

          {expandedId === item.id && (
            detailLoading ? (
              <div className="mt-4 text-sm text-(--color-muted)">Loading…</div>
            ) : detailError ? (
              <div className="mt-4 text-sm text-amber-700">{detailError}</div>
            ) : detail ? (
              <DetailPanel detail={detail} onClose={() => { setExpandedId(null); setDetail(null); }} />
            ) : null
          )}
        </div>
      ))}
    </div>
  );
}

/** One read of the saved list, as the state to show. Sets no state, so an effect can call it. */
async function requestList(): Promise<ListState> {
  try {
    const res = await fetch("/api/user/saved-recommendations", { credentials: "include", cache: "no-store" });
    if (res.ok) {
      const json = (await res.json()) as { data?: RecommendationSummary[] };
      return { phase: "ok", items: Array.isArray(json?.data) ? json.data : [] };
    }
    return res.status === 401 ? { phase: "session_expired" } : { phase: "unavailable" };
  } catch {
    return { phase: "unavailable" };
  }
}

export default function SavedRecommendationsPage() {
  const { authenticated, loading: authLoading, refresh: refreshAuth } = useAuth();
  const [listState, setListState] = useState<ListState>({ phase: "loading" });

  // The list is fetched once signed in; state is set only in the response's callback.
  useEffect(() => {
    if (!authenticated) return;
    let cancelled = false;
    void requestList().then((next) => {
      if (cancelled) return;
      setListState(next);
      if (next.phase === "session_expired") void refreshAuth();
    });
    return () => {
      cancelled = true;
    };
  }, [authenticated, refreshAuth]);

  async function handleDelete(id: number) {
    try {
      const res = await fetch(`/api/user/saved-recommendations/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        setListState((prev) =>
          prev.phase === "ok"
            ? { phase: "ok", items: prev.items.filter((item) => item.id !== id) }
            : prev
        );
      } else if (res.status === 401) {
        setListState({ phase: "session_expired" });
        void refreshAuth();
      }
    } catch {
      // ignore transient delete failures
    }
  }

  function handleSessionExpired() {
    setListState({ phase: "session_expired" });
    void refreshAuth();
  }

  if (authLoading) {
    return <LoadingShell />;
  }

  if (!authenticated || listState.phase === "session_expired") {
    return (
      <SignInPrompt
        message={
          listState.phase === "session_expired"
            ? AUTH_MESSAGES.sessionExpired
            : undefined
        }
      />
    );
  }

  return (
    <main className="min-h-screen bg-(--color-paper)">
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-8">
          <p className="text-sm font-medium text-(--color-muted)">
            Your Account
          </p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-(--color-ink)">
            Saved Recommendation Plans
          </h1>
          <p className="mt-2 text-(--color-muted)">
            Snapshots of recommendation results you have saved for reference.
          </p>
        </div>

        {listState.phase === "loading" ? (
          <div className="animate-pulse space-y-3">
            <div className="h-24 rounded-2xl bg-(--color-paper-2)" />
            <div className="h-24 rounded-2xl bg-(--color-paper-2)" />
          </div>
        ) : listState.phase === "unavailable" ? (
          <UnavailableBanner />
        ) : (
          <SavedList
            items={listState.items}
            onDelete={handleDelete}
            onSessionExpired={handleSessionExpired}
          />
        )}

        <p className="mt-8 text-center text-sm text-(--color-muted)">
          <Link href="/recommendations" className="underline-offset-4 hover:underline hover:text-(--color-ink)">
            ← Back to Recommendations
          </Link>
        </p>
      </div>
    </main>
  );
}
