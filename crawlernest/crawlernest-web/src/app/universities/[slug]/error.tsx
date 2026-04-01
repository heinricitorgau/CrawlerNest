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
    <main className="min-h-screen bg-[#f5f3ee] flex items-center justify-center px-6">
      <div className="max-w-md w-full rounded-2xl border border-[#e0ddd8] bg-white p-8 shadow-sm text-center">
        <h2 className="text-lg font-bold text-[#1a1a1a]">Failed to load university</h2>
        <p className="mt-2 text-sm text-[#6b7068]">
          We couldn&apos;t fetch the university details. The backend may be unavailable.
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            onClick={reset}
            className="rounded-full bg-[#1a3d2e] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[#2a5a42]"
          >
            Retry
          </button>
          <Link
            href="/"
            className="rounded-full border border-[#e0ddd8] px-5 py-2 text-sm font-semibold text-[#1a1a1a] transition hover:border-[#1a3d2e]"
          >
            Back to Rankings
          </Link>
        </div>
      </div>
    </main>
  );
}
