"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuthPlaceholder";
import { useSavedUniversities } from "@/hooks/useSavedUniversities";
import type { SavedUniversityItem } from "@/hooks/useSavedUniversities";

function LoadingShell() {
  return (
    <main className="min-h-screen bg-[#f5f3ee]">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <div className="animate-pulse space-y-4">
          <div className="h-10 w-64 rounded-2xl bg-[#e0ddd8]" />
          <div className="h-24 rounded-2xl bg-[#e0ddd8]" />
          <div className="h-24 rounded-2xl bg-[#e0ddd8]" />
        </div>
      </div>
    </main>
  );
}

function SignInPrompt() {
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
        <h1 className="text-xl font-bold text-[#1a3d2e]">Sign in to view saved universities</h1>
        <p className="mt-2 text-sm text-[#6b7068]">
          Your saved universities are tied to your account. Sign in to access them.
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

function SavedList({ items, onRemove }: { items: SavedUniversityItem[]; onRemove: (item: SavedUniversityItem) => void }) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-[#e0ddd8] bg-white p-8 text-center shadow-sm">
        <p className="text-[#6b7068]">No saved universities yet.</p>
        <p className="mt-1 text-sm text-[#6b7068]">
          Use the <span className="font-medium text-[#1a3d2e]">+ Save</span> button on any ranking row.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block rounded-full border border-[#3d7a5a] px-5 py-2.5 text-sm font-semibold text-[#1a3d2e] transition hover:bg-[#e8f2ec]"
        >
          Browse Rankings
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div
          key={item.canonicalUniversityId}
          className="rounded-2xl border border-[#e0ddd8] bg-white px-5 py-4 shadow-sm"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <Link
                href={`/universities/${item.slug}`}
                className="text-base font-semibold text-[#1a1a1a] underline-offset-4 transition hover:text-[#1a3d2e] hover:underline"
              >
                {item.universityName}
              </Link>
              {item.country ? (
                <div className="mt-1 text-sm text-[#6b7068]">{item.country}</div>
              ) : null}
              {item.savedAt ? (
                <div className="mt-2 text-xs text-[#6b7068]">
                  Saved {new Date(item.savedAt).toLocaleDateString("en-CA", { dateStyle: "medium" })}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => onRemove(item)}
              className="shrink-0 rounded-full border border-[#e0ddd8] bg-white px-3 py-1.5 text-xs font-medium text-[#1a3d2e] transition hover:border-red-300 hover:bg-red-50 hover:text-red-700"
            >
              Remove
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function SavedUniversitiesPage() {
  const { authenticated, loading: authLoading } = useAuth();
  const { savedItems, loading, toggleSave } = useSavedUniversities(authenticated && !authLoading);

  if (authLoading) {
    return <LoadingShell />;
  }

  if (!authenticated) {
    return <SignInPrompt />;
  }

  return (
    <main className="min-h-screen bg-[#f5f3ee]">
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="mb-8">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-[#6b7068]">
            Your Account
          </p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-[#16382a]">
            Saved Universities
          </h1>
          <p className="mt-2 text-[#6b7068]">
            Universities you have saved are synced to your account across devices.
          </p>
        </div>

        {loading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-20 rounded-2xl bg-[#e0ddd8]" />
            <div className="h-20 rounded-2xl bg-[#e0ddd8]" />
          </div>
        ) : (
          <SavedList items={savedItems} onRemove={toggleSave} />
        )}

        <p className="mt-8 text-center text-sm text-[#6b7068]">
          <Link href="/" className="underline-offset-4 hover:underline hover:text-[#1a3d2e]">
            ← Back to Rankings
          </Link>
        </p>
      </div>
    </main>
  );
}
