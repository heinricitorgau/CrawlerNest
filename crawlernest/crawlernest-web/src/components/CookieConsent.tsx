"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "crawlernest_cookie_consent";

type ConsentValue = "accepted" | "declined";

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      setVisible(true);
    }
  }, []);

  function handleAccept() {
    localStorage.setItem(STORAGE_KEY, "accepted");
    setVisible(false);
  }

  function handleDecline() {
    localStorage.setItem(STORAGE_KEY, "declined");
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Cookie consent"
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-white shadow-lg"
    >
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-4 sm:flex-row sm:items-center sm:justify-between lg:px-8">
        <div className="flex-1">
          <p className="text-sm font-semibold text-slate-900">
            This site uses cookies
          </p>
          <p className="mt-1 text-sm text-slate-500">
            We use session cookies to keep you signed in and remember your
            preferences. No tracking or advertising cookies are used.
          </p>
        </div>

        <div className="flex shrink-0 gap-3">
          <button
            type="button"
            onClick={handleDecline}
            className="h-9 border border-slate-300 px-4 text-sm font-medium text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-100"
          >
            Decline
          </button>
          <button
            type="button"
            onClick={handleAccept}
            className="h-9 bg-blue-600 px-4 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
          >
            Accept
          </button>
        </div>
      </div>
    </div>
  );
}
