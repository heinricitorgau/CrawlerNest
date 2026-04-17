"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function PreviewSearchPage() {
  const router = useRouter();
  const [canonicalUniversityId, setCanonicalUniversityId] = useState("");
  const [universityName, setUniversityName] = useState("");
  const [error, setError] = useState("");

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const id = canonicalUniversityId.trim();
    const name = universityName.trim();

    if (!id && !name) {
      setError("Please enter canonicalUniversityId or universityName");
      return;
    }

    if (id) {
      router.push(`/preview/university?canonicalUniversityId=${encodeURIComponent(id)}`);
    } else {
      router.push(`/preview/university?universityName=${encodeURIComponent(name)}`);
    }
  };

  const handleMitDemo = () => {
    router.push("/preview/university?canonicalUniversityId=2759");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">
            University Preview Search
          </h1>
          <p className="text-base text-slate-600">
            Enter a canonicalUniversityId or university name to preview the detailed university
            profile.
          </p>
        </div>

        {/* Search Card */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6 border border-slate-200">
          <form onSubmit={handleSearch} className="space-y-4">
            {/* canonicalUniversityId Field */}
            <div>
              <label htmlFor="id" className="block text-sm font-medium text-slate-700 mb-1">
                Canonical University ID
              </label>
              <input
                id="id"
                type="text"
                value={canonicalUniversityId}
                onChange={(e) => {
                  setCanonicalUniversityId(e.target.value);
                  setError("");
                }}
                placeholder="e.g., 2759"
                className="w-full px-4 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* universityName Field */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1">
                University Name
              </label>
              <input
                id="name"
                type="text"
                value={universityName}
                onChange={(e) => {
                  setUniversityName(e.target.value);
                  setError("");
                }}
                placeholder="e.g., Massachusetts Institute of Technology"
                className="w-full px-4 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Error Message */}
            {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">{error}</div>}

            {/* Submit Button */}
            <button
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors duration-200"
            >
              Open Preview
            </button>
          </form>
        </div>

        {/* Quick Demo Card */}
        <div className="bg-white rounded-lg shadow-md p-6 border border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Quick Demo</h2>
          <div className="space-y-3">
            {/* MIT */}
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-md border border-slate-200 hover:border-slate-300 transition-colors">
              <div>
                <p className="font-medium text-slate-900">MIT</p>
                <p className="text-sm text-slate-600">Massachusetts Institute of Technology</p>
              </div>
              <button
                onClick={handleMitDemo}
                className="bg-blue-100 hover:bg-blue-200 text-blue-700 font-medium py-2 px-4 rounded-md transition-colors duration-200 whitespace-nowrap"
              >
                Open
              </button>
            </div>

            {/* Oxford */}
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-md border border-slate-200 hover:border-slate-300 transition-colors">
              <div>
                <p className="font-medium text-slate-900">Oxford</p>
                <p className="text-sm text-slate-600">University of Oxford</p>
              </div>
              <button
                onClick={() => router.push("/preview/university?canonicalUniversityId=3")}
                className="bg-blue-100 hover:bg-blue-200 text-blue-700 font-medium py-2 px-4 rounded-md transition-colors duration-200 whitespace-nowrap"
              >
                Open
              </button>
            </div>

            {/* Harvard */}
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-md border border-slate-200 hover:border-slate-300 transition-colors">
              <div>
                <p className="font-medium text-slate-900">Harvard</p>
                <p className="text-sm text-slate-600">Harvard University</p>
              </div>
              <button
                onClick={() => router.push("/preview/university?canonicalUniversityId=4")}
                className="bg-blue-100 hover:bg-blue-200 text-blue-700 font-medium py-2 px-4 rounded-md transition-colors duration-200 whitespace-nowrap"
              >
                Open
              </button>
            </div>

            {/* Stanford */}
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-md border border-slate-200 hover:border-slate-300 transition-colors">
              <div>
                <p className="font-medium text-slate-900">Stanford</p>
                <p className="text-sm text-slate-600">Stanford University</p>
              </div>
              <button
                onClick={() => router.push("/preview/university?canonicalUniversityId=6")}
                className="bg-blue-100 hover:bg-blue-200 text-blue-700 font-medium py-2 px-4 rounded-md transition-colors duration-200 whitespace-nowrap"
              >
                Open
              </button>
            </div>

            {/* Cambridge */}
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-md border border-slate-200 hover:border-slate-300 transition-colors">
              <div>
                <p className="font-medium text-slate-900">Cambridge</p>
                <p className="text-sm text-slate-600">University of Cambridge</p>
              </div>
              <button
                onClick={() => router.push("/preview/university?canonicalUniversityId=5")}
                className="bg-blue-100 hover:bg-blue-200 text-blue-700 font-medium py-2 px-4 rounded-md transition-colors duration-200 whitespace-nowrap"
              >
                Open
              </button>
            </div>
          </div>
        </div>

        {/* Info Footer */}
        <div className="mt-8 text-center">
          <p className="text-sm text-slate-500">
            This is a preview mode for exploring university data profiles.
          </p>
        </div>
      </div>
    </div>
  );
}
