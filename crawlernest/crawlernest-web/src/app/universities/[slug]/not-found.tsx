import Link from "next/link";

/** Rendered when the API answers 404 for the slug. An API that cannot answer gets the page's own error state instead. */
export default function UniversityNotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center max-w-md p-8 bg-white border border-slate-200 rounded-lg shadow-lg">
        <h1 className="text-2xl font-bold text-slate-900 mb-4">University Not Found</h1>
        <p className="text-slate-600 mb-6">This university could not be located in our database.</p>
        <Link href="/" className="inline-block px-6 py-2 bg-blue-600 text-white font-bold rounded hover:bg-blue-700 transition-colors">
          Back to Rankings
        </Link>
      </div>
    </div>
  );
}
