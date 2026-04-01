export default function RecommendationsLoading() {
  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-5xl px-6 py-10">
        {/* Header skeleton */}
        <div className="mb-6 flex items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="h-4 w-32 animate-pulse rounded bg-gray-200" />
            <div className="h-10 w-72 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-80 animate-pulse rounded bg-gray-200" />
          </div>
          <div className="h-9 w-36 animate-pulse rounded-full bg-gray-200" />
        </div>

        {/* Shortlist context skeleton */}
        <div className="mb-6 rounded-3xl border border-gray-200 bg-gray-50 p-6">
          <div className="h-5 w-48 animate-pulse rounded bg-gray-200" />
          <div className="mt-2 h-4 w-72 animate-pulse rounded bg-gray-100" />
          <div className="mt-4 space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-11 w-full animate-pulse rounded-2xl bg-gray-200"
              />
            ))}
          </div>
        </div>

        {/* Form skeleton */}
        <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex flex-col gap-2">
                <div className="h-4 w-24 animate-pulse rounded bg-gray-200" />
                <div className="h-12 w-full animate-pulse rounded-xl bg-gray-100" />
              </div>
            ))}
          </div>
          <div className="mt-5 flex gap-3">
            <div className="h-11 w-52 animate-pulse rounded-xl bg-gray-200" />
          </div>
        </div>
      </div>
    </main>
  );
}
