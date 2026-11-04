"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function UniversityError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[CrawlerNest] University page error:", error);
  }, [error]);

  return (
    <main className="min-h-screen bg-(--color-paper) flex items-center justify-center px-6">
      <div className="max-w-md w-full rounded-2xl border border-(--color-rule) bg-white p-8 shadow-sm text-center">
        <h2 className="text-lg font-bold text-(--color-ink)">Failed to load university</h2>
        <p className="mt-2 text-sm text-(--color-muted)">
          We couldn&apos;t fetch the university details. The backend may be unavailable.
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            onClick={reset}
            className="bg-(--color-ink) px-5 py-2 text-sm font-semibold text-white transition hover:bg-(--color-ink-2)"
          >
            Retry
          </button>
          <Link
            href="/"
            className="border border-(--color-rule) px-5 py-2 text-sm font-semibold text-(--color-ink) transition hover:border-(--color-ink)"
          >
            Back to Rankings
          </Link>
        </div>
      </div>
    </main>
  );
}
