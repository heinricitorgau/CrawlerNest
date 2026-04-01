"use client";

type ErrorBannerProps = {
  message: string;
  onDismiss: () => void;
};

export default function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      <span>{message}</span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss error"
        className="flex-shrink-0 font-medium text-red-500 transition hover:text-red-700"
      >
        Dismiss
      </button>
    </div>
  );
}
