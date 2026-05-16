export const AUTH_MESSAGES = {
  // Save button labels
  save: "+ Save",
  saved: "Saved ✓",
  saving: "Saving…",
  removing: "Removing…",
  signInToSave: "Sign in to save",

  // Auth form labels
  signingIn: "Signing in…",
  creatingAccount: "Creating account…",

  // Error states
  sessionExpired: "Your session has expired. Please sign in again.",
  backendUnavailable: "Service unavailable. Please try again later.",
  networkError: "Could not connect. Please check your connection.",
  saveFailed: "Could not save. Please try again.",
  loadFailed: "Could not load your data. Please try again.",
  deleteFailed: "Could not delete. Please try again.",
} as const;

function extractMessage(data: unknown): string | null {
  if (typeof data === "object" && data !== null && !Array.isArray(data)) {
    const d = data as Record<string, unknown>;
    if (typeof d.error === "string" && d.error) return d.error;
    if (typeof d.message === "string" && d.message) return d.message;
  }
  return null;
}

export function normalizeAuthError(status: number, data?: unknown): string {
  const msg = extractMessage(data);
  switch (status) {
    case 401:
      return AUTH_MESSAGES.sessionExpired;
    case 403:
      return "You don't have permission to do this.";
    case 409:
      return msg ?? "An account with this email already exists.";
    case 400:
      return msg ?? "Please check your input and try again.";
    case 503:
      return AUTH_MESSAGES.backendUnavailable;
    default:
      return msg ?? "Something went wrong. Please try again.";
  }
}

export function sessionExpiredMessage(): string {
  return AUTH_MESSAGES.sessionExpired;
}

export function authUnavailableMessage(): string {
  return AUTH_MESSAGES.backendUnavailable;
}
