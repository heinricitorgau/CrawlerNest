# Transient Network Retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Short network outages no longer fail a source in the weekly scheduled refresh.

**Architecture:** A typed `NetworkError` plus one request helper in the shared transport module. THE and ARWU use the helper; the QS scheduled runner maps `network_error` to it. `run_scheduled_refresh` reruns a source only when the failure carries `failure_class == "network_error"` (duck-typed, so the scheduler does not import the transport module).

**Tech Stack:** Python 3, requests / curl_cffi sessions, unittest (`run_tests.py`).

**Spec:** `docs/superpowers/specs/2026-11-09-transient-network-retry-design.md`

## Global Constraints

- Request retry: 3 attempts, sleeps 1 s then 3 s, `TRANSIENT_ERRORS` only; HTTP status codes are never retried.
- Scheduler retry: only on `failure_class == "network_error"`; waits 300 s then 900 s (3 attempts at most).
- No retry starts once the refresh has run 5400 s (90 min).
- Never rerun blocked / maintenance / edition mismatch / truncated table / snapshot regression.
- Existing status JSON fields keep their names and meaning.

## Review Focus

- A non-network exception raised on a *retry* attempt (network first, then edition mismatch) stops retrying and reports the last error → tested in Task 3.
- A runner that recovers on attempt 2 marks the source ok and lists both attempts → Task 3.
- A 4xx/5xx response through the helper is returned or raised unchanged, never retried → Task 1.
- ARWU payload request dropping raises `NetworkError`, not `TruncatedTableError` → Task 2.
- The 90-min cutoff: a network failure after the cutoff is reported without waiting → Task 3.

---

### Task 1: `NetworkError` and `get_with_transient_retry`

**Files:**
- Modify: `crawlernest/crawlernest-extractors/transport.py` (after `TRANSIENT_ERRORS`)
- Test: `crawlernest/crawlernest-tests/test_transient_retry.py` (new; register in `run_tests.py`)

**Interfaces:**
- Produces: `class NetworkError(RuntimeError)` with class attribute `failure_class = "network_error"`.
- Produces: `get_with_transient_retry(session, url: str, *, attempts: int = 3, sleeps: Sequence[float] = (1.0, 3.0), sleep: Callable[[float], None] = time.sleep, **request_kwargs) -> response` — calls `session.get(url, **request_kwargs)`; on `TRANSIENT_ERRORS` sleeps `sleeps[min(i, len-1)]` and retries; after the last attempt raises `NetworkError(f"{url}: {exc}")` from the last exception. Any other exception propagates on the first occurrence. Does not call `raise_for_status`.

- [ ] Tests: `test_recovers_after_two_drops` (session raises `requests.ConnectionError` twice then returns; sleeps recorded == [1.0, 3.0]); `test_raises_network_error_after_three` (3 `requests.Timeout` → `NetworkError`, `failure_class == "network_error"`, 3 calls); `test_http_error_is_not_retried` (session raises `requests.HTTPError` → propagates, 1 call); `test_non_200_response_returned_as_is` (response with status 503 returned after 1 call).
- [ ] Run, see them fail (import error).
- [ ] Implement.
- [ ] Run `python3 -m unittest test_transient_retry` in `crawlernest-tests`: OK.

### Task 2: THE and ARWU use the helper

**Files:**
- Modify: `crawlernest/crawlernest-jobs/the_crawler.py` (`_load_verified_edition`)
- Modify: `crawlernest/crawlernest-jobs/arwu_crawler.py` (edition-page fetch in `crawl_arwu_rankings`, `_request_text`)
- Test: `crawlernest/crawlernest-tests/test_transient_retry.py`

**Interfaces:**
- Consumes: Task 1.
- THE: transient failure → `NetworkError`; other `requests.RequestException` stays `EditionMismatchError`.
- ARWU: edition page and payload both via helper; `NetworkError` propagates out of `crawl_arwu_rankings`. HTTP errors keep today's behaviour (page: skip; payload: `None` → `TruncatedTableError`).

- [ ] Tests: `test_the_connection_drop_is_network_error_not_edition_mismatch`; `test_arwu_page_drop_raises_network_error`; `test_arwu_payload_drop_raises_network_error_and_keeps_file` (existing file content unchanged). Patch the helper's `sleep` via `transport.time.sleep` or pass-through so tests do not wait.
- [ ] Run, see them fail.
- [ ] Implement.
- [ ] Run new tests + `test_arwu_crawler test_the_crawler test_snapshot_guard`: OK.

### Task 3: Scheduler reruns network failures only

**Files:**
- Modify: `crawlernest/pipeline/commands/scheduled_refresh.py`
- Modify: `crawlernest/run_pipeline.py` (`_cmd_scheduled_refresh` QS runner)
- Test: `crawlernest/crawlernest-tests/test_scheduled_refresh.py`

**Interfaces:**
- `run_scheduled_refresh(..., network_retry_delays: Sequence[float] = (300.0, 900.0), retry_cutoff_seconds: float = 5400.0, sleep=time.sleep, clock=time.monotonic) -> int`.
- `SourceOutcome` gains `failure_class: str | None = None` and `attempts: list[dict] = []` (each `{"started_at", "finished_at", "error"}`; `error` None on success).
- Failure class = `getattr(exc, "failure_class", None) or type(exc).__name__`.
- QS runner: raise `NetworkError` (imported from `transport`) when `crawl_meta["failure_classification"] == "network_error"`; other cases unchanged.

- [ ] Tests (fake runner raising an exception class with `failure_class = "network_error"`; recording `sleep`; fake `clock`): `test_network_failure_is_retried_then_succeeds` (sleeps [300.0], ok, 2 attempts); `test_network_failure_gives_up_after_three_attempts` (sleeps [300.0, 900.0], ok False, failure_class "network_error", 3 attempts); `test_other_failures_are_not_retried` (RuntimeError → 1 attempt, failure_class "RuntimeError", no sleep); `test_switch_to_non_network_error_stops_retrying`; `test_no_retry_after_cutoff` (clock past 5400 → 1 attempt, no sleep). Existing tests stay green unchanged.
- [ ] Run, see them fail.
- [ ] Implement.
- [ ] Run `test_scheduled_refresh` + full `run_tests.py`: only the 7 known env errors (aiohttp/uvicorn missing).
- [ ] Commit spec, plan and code together.
