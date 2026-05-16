import { normalizeAuthError, AUTH_MESSAGES, sessionExpiredMessage, authUnavailableMessage } from "@/lib/authMessages";

describe("normalizeAuthError", () => {
  it("returns session expired message for 401", () => {
    expect(normalizeAuthError(401)).toBe(AUTH_MESSAGES.sessionExpired);
  });

  it("returns permission message for 403", () => {
    expect(normalizeAuthError(403)).toMatch(/permission/i);
  });

  it("returns default duplicate account message for 409 with no data", () => {
    expect(normalizeAuthError(409)).toMatch(/already exists/i);
  });

  it("returns server-provided message for 409 when present", () => {
    const result = normalizeAuthError(409, { error: "Custom conflict message" });
    expect(result).toBe("Custom conflict message");
  });

  it("returns default input error for 400 with no data", () => {
    expect(normalizeAuthError(400)).toMatch(/check your input/i);
  });

  it("returns server-provided message for 400 when present", () => {
    const result = normalizeAuthError(400, { error: "Title must be 200 characters or fewer." });
    expect(result).toBe("Title must be 200 characters or fewer.");
  });

  it("returns backend unavailable message for 503", () => {
    expect(normalizeAuthError(503)).toBe(AUTH_MESSAGES.backendUnavailable);
  });

  it("returns generic message for unknown status", () => {
    expect(normalizeAuthError(500)).toMatch(/something went wrong/i);
  });

  it("prefers data message over generic for unknown status", () => {
    const result = normalizeAuthError(500, { message: "Internal pipeline error" });
    expect(result).toBe("Internal pipeline error");
  });

  it("ignores empty string message fields", () => {
    const result = normalizeAuthError(400, { error: "" });
    expect(result).toMatch(/check your input/i);
  });
});

describe("sessionExpiredMessage", () => {
  it("returns the session expired string", () => {
    expect(sessionExpiredMessage()).toBe(AUTH_MESSAGES.sessionExpired);
  });
});

describe("authUnavailableMessage", () => {
  it("returns the backend unavailable string", () => {
    expect(authUnavailableMessage()).toBe(AUTH_MESSAGES.backendUnavailable);
  });
});
