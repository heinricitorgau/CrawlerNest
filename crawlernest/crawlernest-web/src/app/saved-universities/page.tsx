"use client";

import Link from "next/link";
import { useAuth } from "@/hooks/useAuthPlaceholder";
import { useSavedUniversities } from "@/hooks/useSavedUniversities";
import type { SavedUniversityItem } from "@/hooks/useSavedUniversities";
import { AUTH_MESSAGES } from "@/lib/authMessages";

function LoadingShell() {
  return (
    <main className="min-h-screen bg-(--color-paper)">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <div className="animate-pulse space-y-4">
          <div className="h-10 w-64 rounded-2xl bg-(--color-paper-2)" />
          <div className="h-24 rounded-2xl bg-(--color-paper-2)" />
          <div className="h-24 rounded-2xl bg-(--color-paper-2)" />
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
        <h1 className="text-xl font-bold text-(--color-ink)">Sign in to view saved universities</h1>
        <p className="mt-2 text-sm text-(--color-muted)">
          {message ?? "Your saved universities are tied to your account. Sign in to access them."}
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

function SavedList({ items, onRemove }: { items: SavedUniversityItem[]; onRemove: (item: SavedUniversityItem) => void }) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-(--color-rule) bg-white p-8 text-center shadow-sm">
        <p className="text-(--color-muted)">No saved universities yet.</p>
        <p className="mt-1 text-sm text-(--color-muted)">
          Use the <span className="font-medium text-(--color-ink)">{AUTH_MESSAGES.save}</span> button on any ranking row.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block border border-(--color-ink-2) px-5 py-2.5 text-sm font-semibold text-(--color-ink) transition hover:bg-(--color-paper-2)"
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
          className="rounded-2xl border border-(--color-rule) bg-white px-5 py-4 shadow-sm"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <Link
                href={`/universities/${item.slug}`}
                className="text-base font-semibold text-(--color-ink) underline-offset-4 transition hover:text-(--color-ink) hover:underline"
              >
                {item.universityName}
              </Link>
              {item.country ? (
                <div className="mt-1 text-sm text-(--color-muted)">{item.country}</div>
              ) : null}
              {item.savedAt ? (
                <div className="mt-2 text-xs text-(--color-muted)">
                  Saved {new Date(item.savedAt).toLocaleDateString("en-CA", { dateStyle: "medium" })}
                </div>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => onRemove(item)}
              className="shrink-0 border border-(--color-rule) bg-white px-3 py-1.5 text-xs font-medium text-(--color-ink) transition hover:border-red-300 hover:bg-red-50 hover:text-red-700"
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
  const { authenticated, loading: authLoading, refresh: refreshAuth } = useAuth();
  const { savedItems, loading, toggleSave, sessionExpired } =
    useSavedUniversities(authenticated && !authLoading, () => void refreshAuth());

  if (authLoading) {
    return <LoadingShell />;
  }

  if (!authenticated || sessionExpired) {
    return (
      <SignInPrompt
        message={
          sessionExpired
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
            Saved Universities
          </h1>
          <p className="mt-2 text-(--color-muted)">
            Universities you have saved are synced to your account across devices.
          </p>
        </div>

        {loading ? (
          <div className="animate-pulse space-y-3">
            <div className="h-20 rounded-2xl bg-(--color-paper-2)" />
            <div className="h-20 rounded-2xl bg-(--color-paper-2)" />
          </div>
        ) : (
          <SavedList items={savedItems} onRemove={toggleSave} />
        )}

        <p className="mt-8 text-center text-sm text-(--color-muted)">
          <Link href="/" className="underline-offset-4 hover:underline hover:text-(--color-ink)">
            ← Back to Rankings
          </Link>
        </p>
      </div>
    </main>
  );
}
