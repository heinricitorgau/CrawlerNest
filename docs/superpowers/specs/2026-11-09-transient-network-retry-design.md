# Transient network failures recover on their own

Date: 2026-11-09 · Status: approved, implemented

## Why

The weekly `scheduled-refresh` (systemd timer, `Persistent=true`) often runs
right after WSL boots, before the network is fully up. Goal: a short network
outage should not fail a source. Not a goal: working around sites that refuse us.

## What exists today

| Source | Request-level retry | What a dropped connection becomes |
|---|---|---|
| QS | 3 attempts, 1 s / 3 s, transport errors only | `failure_classification="network_error"`; scheduled runner raises `RuntimeError` |
| THE | none | `EditionMismatchError` (looks like a wrong edition) |
| ARWU | none | `RuntimeError("Unable to locate or parse…")`, or `TruncatedTableError` if the payload request drops (looks like a site change) |

`scheduled-refresh` runs each source once; a failure is one string in
`scheduled_refresh_latest.json`.

## Approaches

- **A. Request-level only**: THE and ARWU get QS's transport retry. It covers
  outages of a few seconds, not the minutes after boot.
- **B. Scheduler-level only**: rerun a failed source after a wait. It cannot tell
  a dropped connection from a block without A's typed error, and blind reruns
  hit sites that already refused.
- **C. Both, scheduler retry limited to network failures (chosen).**

## Design

1. **`NetworkError`** (in `crawlernest-extractors/transport.py`, next to
   `TRANSIENT_ERRORS`): raised when a request still fails with a timeout or
   connection error after its retries. HTTP status codes never count as network failures.
2. **`get_with_transient_retry(session, url, …)`** in the same module: 3 attempts,
   sleeps 1 s / 3 s (QS's schedule), retries `TRANSIENT_ERRORS` only, raises
   `NetworkError` when they run out. Other errors pass through unchanged.
3. **THE**: `_load_verified_edition` uses it. A network failure raises
   `NetworkError`, not `EditionMismatchError`.
4. **ARWU**: the edition page and the payload requests use it. A network failure
   raises `NetworkError`. It no longer falls through to "unable to parse" or `TruncatedTableError`.
5. **QS scheduled runner**: raises `NetworkError` when
   `failure_classification == "network_error"`. QS internals are unchanged.
6. **`run_scheduled_refresh`**: when a source raises `NetworkError`, wait 5 min
   and rerun that source, then 15 min and once more (3 attempts at most). Any
   other exception (blocked, maintenance, edition mismatch, truncated table,
   snapshot regression) is never rerun. No retry starts once the whole refresh
   has run 90 min, so the service's 2 h `TimeoutStartSec` cannot kill a write
   halfway through. The wait is injectable for tests.
7. **Status JSON**: each source records `failure_class` (`network_error` or the
   exception type name) and an `attempts` list (`started_at`, `finished_at`,
   `error`). Existing fields stay as they are.

## Non-goals / anti-goals

- No cross-run circuit breaker or per-week budget.
- Never retry a 403/429/challenge or any non-network failure. A retry that hits
  a site which already refused us makes this a failure even if it "works".
- No change to QS's internal retry or classification.

## Left to the builder

Exact log wording; whether the 5/15 min delays and 90 min cutoff become CLI
flags (default: constants).
