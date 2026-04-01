export default function RankingsLoading() {
  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-5xl px-6 py-10">
        {/* Header skeleton */}
        <div className="mb-6 flex items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="h-4 w-32 animate-pulse rounded bg-gray-200" />
            <div className="h-10 w-72 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-64 animate-pulse rounded bg-gray-200" />
          </div>
          <div className="h-9 w-36 animate-pulse rounded-full bg-gray-200" />
        </div>

        {/* Count summary skeleton */}
        <div className="mb-6 flex gap-2 overflow-x-auto pb-1">
          {Array.from({ length: 7 }).map((_, i) => (
            <div
              key={i}
              className="h-16 w-28 flex-shrink-0 animate-pulse rounded-2xl bg-gray-100"
            />
          ))}
        </div>

        {/* Filter controls skeleton */}
        <div className="mb-4 flex flex-wrap gap-3">
          <div className="h-10 w-56 animate-pulse rounded-xl bg-gray-200" />
          <div className="h-10 w-32 animate-pulse rounded-xl bg-gray-200" />
          <div className="h-10 w-32 animate-pulse rounded-xl bg-gray-200" />
          <div className="h-10 w-24 animate-pulse rounded-xl bg-gray-200" />
        </div>

        {/* Table skeleton */}
        <div className="rounded-3xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          {/* Table header */}
          <div className="bg-gray-50 px-6 py-3 flex gap-4 border-b border-gray-200">
            <div className="h-4 w-12 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-48 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-24 animate-pulse rounded bg-gray-200 ml-auto" />
            <div className="h-4 w-24 animate-pulse rounded bg-gray-200" />
          </div>
          {/* Table rows */}
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="px-6 py-4 border-b border-gray-100 flex items-center gap-4"
            >
              <div className="h-5 w-8 animate-pulse rounded bg-gray-100" />
              <div className="flex-1 space-y-1">
                <div className="h-5 w-64 animate-pulse rounded bg-gray-200" />
                <div className="h-4 w-32 animate-pulse rounded bg-gray-100" />
              </div>
              <div className="h-6 w-16 animate-pulse rounded bg-gray-100" />
              <div className="h-6 w-16 animate-pulse rounded bg-gray-100" />
            </div>
          ))}
        </div>

        {/* Pagination skeleton */}
        <div className="mt-4 flex items-center justify-between">
          <div className="h-4 w-32 animate-pulse rounded bg-gray-200" />
          <div className="flex gap-2">
            <div className="h-9 w-20 animate-pulse rounded-lg bg-gray-200" />
            <div className="h-9 w-20 animate-pulse rounded-lg bg-gray-200" />
          </div>
        </div>
      </div>
    </main>
  );
}
