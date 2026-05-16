# UX Stabilization Notes

Covers the stabilization pass applied to the identity + user-owned feature UX in the CrawlerNest web frontend (Next.js). No new features were introduced; the goal was consistency across loading, error, session-expired, and backend-unavailable states.

---

## Stabilized UX States

### Auth Loading

**Before:** NavBar showed sign-in/sign-up links during the initial `useAuth()` fetch, then switched to the authenticated state — causing a visible flicker.

**After:** NavBar renders a pulse-skeleton placeholder while `loading=true`, then resolves to either the authenticated or unauthenticated state with no layout shift.

### Session Expired

**Before:** Session expiry mid-session caused silent failures (save operations reverted without user feedback; saved pages showed empty lists or errors with no explanation).

**After:** All surfaces that touch user-owned APIs detect `401` responses and route to a consistent sign-in prompt with the message defined in `AUTH_MESSAGES.sessionExpired`. The `useAuth().refresh()` callback is called to resync client auth state without a page reload.

Affected surfaces:
- `useSavedUniversities` hook (fetch + toggle)
- Saved Universities page (list fetch + remove)
- Saved Recommendations page (list fetch + delete + detail expand)
- Recommendations page (save plan action)
- Rankings page (via `useSavedUniversities`)

### Backend Unavailable

**Before:** Non-auth errors on saved-data endpoints produced no visible feedback or generic UI.

**After:** A distinct amber-toned `UnavailableBanner` is shown on the Saved Recommendations page for non-401 fetch failures. The Saved Universities page uses a similar error state via the hook's existing fallback. All error strings come from `AUTH_MESSAGES`.

### Save Button States

All save/remove actions use shared label constants from `AUTH_MESSAGES`:

| Key | Value |
|---|---|
| `save` | `+ Save` |
| `saved` | `Saved ✓` |
| `saving` | `Saving…` |
| `removing` | `Removing…` |
| `signInToSave` | `Sign in to save` |

### Auth Form

**Before:** Inline `switch` over HTTP status code produced error strings per-form.

**After:** `normalizeAuthError(status, data?)` in `src/lib/authMessages.ts` centralizes all auth error strings. The form retains one special case: `401` on sign-in maps to `"Invalid email or password."` (not the session-expired message, which would be confusing on the login form).

---

## Session Expiry Behavior

1. Any user-owned API call returns `401`.
2. The calling component/hook:
   - Sets its local UI to the sign-in prompt or session-expired state.
   - Calls `useAuth().refresh()` to re-fetch `/api/auth/me` and update global auth context.
3. The user sees a sign-in prompt with the `AUTH_MESSAGES.sessionExpired` string.
4. Signing in again restores normal access.

**No automatic token refresh or silent re-authentication is performed.** Session renewal is always user-initiated (sign in again).

**Callback stabilization:** The `onSessionExpired` callback passed to `useSavedUniversities` is stored in a `useRef` to prevent the callback reference from causing unnecessary re-renders or infinite fetch loops. This is an implementation detail; callers do not need to memoize the callback.

---

## Shared Auth Message Catalogue

All user-facing auth/save strings live in `src/lib/authMessages.ts`. The exported `AUTH_MESSAGES` object is `as const` — TypeScript enforces that only known keys are used. Adding a new string requires editing exactly one file.

Helper functions:
- `normalizeAuthError(status, data?)` — maps HTTP status code to a user-facing string, preferring server-supplied `error` or `message` fields when present.
- `sessionExpiredMessage()` — convenience alias for `AUTH_MESSAGES.sessionExpired`.
- `authUnavailableMessage()` — convenience alias for `AUTH_MESSAGES.backendUnavailable`.

---

## Known UX Limitations

- **No toast/notification system.** Error and success states are inline (adjacent to the triggering element or as a page-level banner). There is no global snackbar or toast queue.
- **Save optimism on rankings page.** The save toggle is optimistic: the button flips immediately and reverts on failure. If the revert triggers due to a session expiry, the user sees the session-expired sign-in prompt rather than a save-failed message. This is acceptable given the current session model.
- **No offline detection.** `AUTH_MESSAGES.networkError` exists but is only surfaced on explicit `fetch` throws (network-level failures). There is no connection-state listener.
- **NavBar mobile auth:** Sign-in is now visible on mobile breakpoints. Sign-out/email are still shown only at `sm:` and above; a full mobile menu is out of scope.
- **No per-item delete confirmation.** Delete on the Saved Recommendations page is immediate (no modal or undo). Consistent with the current UX simplicity target.

---

## Intentionally Avoided Complexity

The following were considered and explicitly excluded:

| Avoided | Reason |
|---|---|
| Auto-refresh / silent reauth | Requires token rotation or session ping infrastructure; not appropriate for in-memory `HttpSession` model |
| Global toast / notification system | Premature abstraction; inline errors are sufficient at current feature count |
| Route protection middleware | Not needed; unauthenticated users see sign-in prompts, not hard redirects |
| Dropdown menu / avatar system | Scope exceeds stabilization pass |
| E2E framework (Playwright/Cypress) | Auth flows require live backend; out of scope for this pass |
| RBAC / role-aware UI | No role model exists; single-user-owned data only |
| Real-time sync / WebSocket | No server-push infrastructure |

---

## Current Auth UX Boundaries

The session model is described in detail in [`AUTH_LIMITATIONS.md`](AUTH_LIMITATIONS.md). From a UX perspective:

- Sessions last 30 minutes of inactivity (Spring Boot default).
- There is no "remember me" or persistent login.
- Sessions do not survive server restart (in-memory store).
- The client has no way to know when the session will expire; it discovers expiry only on the next API call that returns `401`.
- All user-facing expiry messaging uses the single `AUTH_MESSAGES.sessionExpired` string for consistency.
