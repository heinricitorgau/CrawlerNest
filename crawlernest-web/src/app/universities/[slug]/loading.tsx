export default function UniversityDetailLoading() {
  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="animate-pulse space-y-6">
          <div className="rounded-3xl border border-gray-200 bg-gray-50 p-8">
            <div className="h-4 w-32 rounded bg-gray-200" />
            <div className="mt-4 h-10 w-80 max-w-full rounded bg-gray-200" />
            <div className="mt-3 h-4 w-48 rounded bg-gray-200" />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-gray-200 bg-white p-6">
              <div className="h-5 w-32 rounded bg-gray-200" />
              <div className="mt-5 space-y-3">
                <div className="h-4 w-full rounded bg-gray-100" />
                <div className="h-4 w-full rounded bg-gray-100" />
                <div className="h-4 w-3/4 rounded bg-gray-100" />
              </div>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-6">
              <div className="h-5 w-36 rounded bg-gray-200" />
              <div className="mt-5 space-y-3">
                <div className="h-4 w-full rounded bg-gray-100" />
                <div className="h-4 w-5/6 rounded bg-gray-100" />
                <div className="h-4 w-2/3 rounded bg-gray-100" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
