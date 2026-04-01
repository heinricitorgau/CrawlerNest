"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[CrawlerNest] Unhandled error:", error);
  }, [error]);

  return (
    <main className="min-h-screen bg-[#f5f3ee] flex items-center justify-center px-6">
      <div className="max-w-md w-full rounded-2xl border border-red-200 bg-white p-8 shadow-sm text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-50">
          <span className="text-xl text-red-600" aria-hidden="true">!</span>
        </div>
        <h2 className="text-lg font-bold text-[#1a1a1a]">Something went wrong</h2>
        <p className="mt-2 text-sm text-[#6b7068]">
          An unexpected error occurred. Please try again.
        </p>
        {error.digest && (
          <p className="mt-1 font-mono text-xs text-[#6b7068]">
            Error ID: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="mt-6 rounded-full bg-[#1a3d2e] px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
