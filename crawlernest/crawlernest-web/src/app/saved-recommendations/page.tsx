"use client";

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/hooks/useAuthPlaceholder";
import { AUTH_MESSAGES } from "@/lib/authMessages";

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
    <main className="min-h-screen bg-[#f5f3ee]">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <div className="animate-pulse space-y-4">
          <div className="h-10 w-64 rounded-2xl bg-[#e0ddd8]" />
          <div className="h-28 rounded-2xl bg-[#e0ddd8]" />
          <div className="h-28 rounded-2xl bg-[#e0ddd8]" />
        </div>
      </div>
    </main>
  );
}

function SignInPrompt({ message }: { message?: string }) {
  return (
    <main className="min-h-screen bg-[#f5f3ee] flex items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border border-[#e0ddd8] bg-white px-8 py-10 shadow-sm text-center">
        <div className="mx-auto mb-5 inline-flex h-12 w-12 items-center justify-center rounded-full bg-[#e8f2ec]">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
            stroke="#3d7a5a" strokeWidth="2.5" strokeLinecap="round"
            strokeLinejoin="round" aria-hidden="true">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
        <h1 className="text-xl font-bold text-[#1a3d2e]">Sign in to view saved plans</h1>
        <p className="mt-2 text-sm text-[#6b7068]">
          {message ?? "Your saved recommendation plans are tied to your account."}
        </p>
        <Link
          href="/signin"
          className="mt-6 inline-block w-full rounded-lg bg-[#1a3d2e] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
        >
          Sign in
        </Link>
        <p className="mt-4 text-sm text-[#6b7068]">
          {"Don't have an account? "}
          <Link href="/signup" className="font-medium text-[#3d7a5a] underline-offset-4 hover:underline">
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

function DetailPanel({ detail, onClose }: { detail: RecommendationDetail; onClose: () => void }) {
  const req = detail.requestJson ?? {};
  const result = detail.resultJson as {
    data?: {
      reach?: Array<{ universityName?: string }>;
      target?: Array<{ universityName?: string }>;
      safety?: Array<{ universityName?: string }>;
    };
  };
  const reach = result?.data?.reach ?? [];
  const target = result?.data?.target ?? [];
  const safety = result?.data?.safety ?? [];

  return (
    <div className="mt-4 rounded-2xl border border-[#d8e6dd] bg-[#f6fbf7] p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="text-base font-semibold text-[#1a3d2e]">Plan Detail</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-[#6b7068] underline-offset-4 hover:underline"
        >
          Close
        </button>
      </div>

      <div className="mb-4">
        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#6b7068] mb-2">Profile</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-[#1a1a1a]">
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
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#6b7068] mb-1">Reach</div>
              <ul className="space-y-1">
                {reach.map((u, i) => (
                  <li key={i} className="text-sm text-[#1a1a1a]">{u.universityName ?? "—"}</li>
                ))}
              </ul>
            </div>
          )}
          {target.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#6b7068] mb-1">Target</div>
              <ul className="space-y-1">
                {target.map((u, i) => (
                  <li key={i} className="text-sm text-[#1a1a1a]">{u.universityName ?? "—"}</li>
                ))}
              </ul>
            </div>
          )}
          {safety.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[#6b7068] mb-1">Safety</div>
              <ul className="space-y-1">
                {safety.map((u, i) => (
                  <li key={i} className="text-sm text-[#1a1a1a]">{u.universityName ?? "—"}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <p className="text-sm text-[#6b7068]">No university data in this snapshot.</p>
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
      <div className="rounded-2xl border border-[#e0ddd8] bg-white p-8 text-center shadow-sm">
        <p className="text-[#6b7068]">No saved plans yet.</p>
        <p className="mt-1 text-sm text-[#6b7068]">
          Use the <span className="font-medium text-[#1a3d2e]">Save plan</span> button on the recommendations page.
        </p>
        <Link
          href="/recommendations"
          className="mt-6 inline-block rounded-full border border-[#3d7a5a] px-5 py-2.5 text-sm font-semibold text-[#1a3d2e] transition hover:bg-[#e8f2ec]"
        >
          Generate Recommendations
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.id} className="rounded-2xl border border-[#e0ddd8] bg-white px-5 py-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="text-base font-semibold text-[#1a1a1a]">{item.title}</div>
              {item.requestSummary ? (
                <div className="mt-1 text-sm text-[#6b7068]">{item.requestSummary}</div>
              ) : null}
              {item.topRecommendationName ? (
                <div className="mt-1 text-xs text-[#3d7a5a] font-medium">
                  Top: {item.topRecommendationName}
                </div>
              ) : null}
              <div className="mt-2 text-xs text-[#6b7068]">
                {new Date(item.createdAt).toLocaleDateString("en-CA", { dateStyle: "medium" })}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => void handleToggleDetail(item.id)}
                className="rounded-full border border-[#e0ddd8] bg-white px-3 py-1.5 text-xs font-medium text-[#1a3d2e] transition hover:border-[#3d7a5a] hover:bg-[#e8f2ec]"
              >
                {expandedId === item.id ? "Hide" : "View"}
              </button>
              <button
                type="button"
                onClick={() => onDelete(item.id)}
                className="rounded-full border border-[#e0ddd8] bg-white px-3 py-1.5 text-xs font-medium text-[#1a3d2e] transition hover:border-red-300 hover:bg-red-50 hover:text-red-700"
              >
                Delete
              </button>
            </div>
          </div>

          {expandedId === item.id && (
            detailLoading ? (
              <div className="mt-4 text-sm text-[#6b7068]">Loading…</div>
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

export default function SavedRecommendationsPage() {
  const { authenticated, loading: authLoading, refresh: refreshAuth } = useAuth();
  const [listState, setListState] = useState<ListState>({ phase: "loading" });

  const fetchList = useCallback(async () => {
    if (!authenticated) return;
    setListState({ phase: "loading" });
    try {
      const res = await fetch("/api/user/saved-recommendations", {
        credentials: "include",
        cache: "no-store",
      });
      if (res.ok) {
        const json = (await res.json()) as { data?: RecommendationSummary[] };
        setListState({ phase: "ok", items: Array.isArray(json?.data) ? json.data : [] });
      } else if (res.status === 401) {
        setListState({ phase: "session_expired" });
        void refreshAuth();
      } else {
        setListState({ phase: "unavailable" });
      }
    } catch {
      setListState({ phase: "unavailable" });
    }
  }, [authenticated, refreshAuth]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

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
    <main className="min-h-screen bg-[#f5f3ee]">
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-8">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-[#6b7068]">
            Your Account
          </p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-[#16382a]">
            Saved Recommendation Plans
          </h1>
          <p className="mt-2 text-[#6b7068]">
            Snapshots of recommendation results you have saved for reference.
          </p>
        </div>

        {listState.phase === "loading" ? (
          <div className="animate-pulse space-y-3">
            <div className="h-24 rounded-2xl bg-[#e0ddd8]" />
            <div className="h-24 rounded-2xl bg-[#e0ddd8]" />
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

        <p className="mt-8 text-center text-sm text-[#6b7068]">
          <Link href="/recommendations" className="underline-offset-4 hover:underline hover:text-[#1a3d2e]">
            ← Back to Recommendations
          </Link>
        </p>
      </div>
    </main>
  );
}
