#!/usr/bin/env python3
"""Probe what actually refuses the QS ranking API, one variable at a time.

Why this exists
---------------
Every QS run currently lands on ``failure_classification="upstream_blocked"``
and falls back to a snapshot. That label used to be produced by a rule in
``fetcher.py`` that treated *any* HTTP 403 as a Cloudflare challenge, so it
could not distinguish:

  * Cloudflare serving a JS interstitial   -> needs a browser engine
  * Cloudflare denying on bot score        -> needs a matching TLS/h2 fingerprint
  * Cloudflare rate limiting               -> needs to slow down
  * the QS origin itself saying no         -> needs none of the above

``fetcher._classify_block_reason`` now answers that question, and this script
exercises it against the live endpoint under four (optionally five) controlled
conditions so the answer is evidence rather than inference.

The variants isolate one suspect each
-------------------------------------
  baseline        exactly what the pipeline sends today: the mixed
                  "Chrome/122 ... CrawlerNest/1.0" User-Agent, XHR headers,
                  straight at the JSON API with an empty cookie jar.
  clean_ua        same request with the self-identifying CrawlerNest suffix
                  removed. Isolates User-Agent consistency.
  warm_cookie     current UA, but loads the HTML ranking page first so the
                  session holds __cf_bm / cf_clearance before the API call.
                  Isolates the cold-cookie-jar hypothesis.
  clean_ua_warm   both of the above. Isolates "Phase 1 is enough".
  curl_cffi       Chrome TLS + HTTP/2 fingerprint via curl_cffi, warmed the
                  same way. Isolates the fingerprint hypothesis, i.e. answers
                  whether Phase 2 is worth building. Skipped (not failed) when
                  curl_cffi is not installed.

Politeness
----------
QS publishes ``crawl-delay: 10``. This script honours it globally, across
variants, by default. At the default settings a full run makes at most 8
requests and takes roughly 80 seconds. ``--delay`` is offered for completeness
but lowering it against topuniversities.com breaks the robots contract the rest
of this codebase deliberately keeps.

Usage
-----
    python3 scripts/probe_qs_block.py --dry-run          # show the plan, no network
    python3 scripts/probe_qs_block.py                    # run it
    python3 scripts/probe_qs_block.py --out probe.json   # keep the evidence
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = REPO_ROOT / "crawlernest"

# Same sys.path recipe crawlernest-tests/run_tests.py uses.
for _mod in ("crawlernest-core", "crawlernest-extractors"):
    _p = PACKAGE_ROOT / _mod
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import requests  # noqa: E402

from config import Config  # noqa: E402
from fetcher import (  # noqa: E402
    _block_evidence,
    _classify_block_reason,
    _classify_qs_http_response,
    BLOCK_REASON_CF_JS_CHALLENGE,
    BLOCK_REASON_CF_RATE_LIMITED,
    BLOCK_REASON_CF_WAF_DENY,
    BLOCK_REASON_ORIGIN_DENY,
)

# The universe the checked-in crawl_meta recorded as blocked, so the probe
# reproduces a known failure rather than inventing a new one.
DEFAULT_RANKING_ID = "3990755"
DEFAULT_PAGE_URL = "https://www.topuniversities.com/asia-university-rankings"

# config.Config.user_agent with the self-identifying suffix taken off. Kept as a
# literal rather than a string operation so that a future edit to the config UA
# cannot silently make "clean_ua" identical to "baseline".
CLEAN_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


# -- global politeness gate ----------------------------------------------------

class _Pacer:
    """One shared crawl-delay across every variant, not per session."""

    def __init__(self, delay: float) -> None:
        self.delay = max(0.0, float(delay))
        self._last = 0.0
        self.requests_made = 0

    def wait(self) -> None:
        if self.delay <= 0:
            return
        remaining = self.delay - (time.monotonic() - self._last)
        if remaining > 0 and self._last > 0.0:
            time.sleep(remaining)
        self._last = time.monotonic()


# -- result records ------------------------------------------------------------

@dataclass
class StepResult:
    label: str
    url: str
    status: Optional[int] = None
    elapsed_ms: Optional[int] = None
    classification: str = ""
    block_reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    cookies_after: List[str] = field(default_factory=list)
    http_version: str = ""
    error: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "url": self.url,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "classification": self.classification,
            "block_reason": self.block_reason,
            "evidence": self.evidence,
            "cookies_after": self.cookies_after,
            "http_version": self.http_version,
            "error": self.error,
        }


@dataclass
class VariantResult:
    name: str
    description: str
    steps: List[StepResult] = field(default_factory=list)
    skipped: str = ""

    @property
    def final(self) -> Optional[StepResult]:
        return self.steps[-1] if self.steps else None

    @property
    def succeeded(self) -> bool:
        last = self.final
        return bool(last and last.classification == "live_ok")

    @property
    def url_label(self) -> str:
        last = self.final
        return last.label if last and last.label else self.name

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "skipped": self.skipped,
            "steps": [s.as_dict() for s in self.steps],
            "succeeded": self.succeeded,
        }


# -- request execution ---------------------------------------------------------

def _classify(url: str, status: int, text: str, headers: Dict[str, str]) -> StepResult:
    cls, _msg = _classify_qs_http_response(url, status, text, headers)
    reason = _classify_block_reason(status, text, headers)
    return StepResult(
        label="",
        url=url,
        status=status,
        classification=cls,
        block_reason=reason,
        # Evidence is recorded for every response, not only refusals -- a 200
        # that still shows cf-mitigated is worth seeing.
        evidence=_block_evidence(status, text, headers),
    )


def _run_requests_step(
    session: Any,
    *,
    label: str,
    url: str,
    headers: Dict[str, str],
    timeout: float,
    pacer: _Pacer,
) -> StepResult:
    pacer.wait()
    started = time.monotonic()
    try:
        resp = session.get(url, headers=headers, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - a probe reports failures, never raises
        return StepResult(
            label=label,
            url=url,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        pacer.requests_made += 1

    text = getattr(resp, "text", "") or ""
    hdrs = {str(k): str(v) for k, v in (resp.headers or {}).items()}
    step = _classify(url, resp.status_code, text, hdrs)
    step.label = label
    step.elapsed_ms = int((time.monotonic() - started) * 1000)
    step.http_version = _http_version_of(resp)
    try:
        step.cookies_after = sorted(session.cookies.get_dict().keys())
    except Exception:  # noqa: BLE001
        step.cookies_after = []
    return step


def _http_version_of(resp: Any) -> str:
    """Best-effort protocol version. requests is always 1.1; curl_cffi reports h2."""
    raw = getattr(resp, "http_version", None)
    if raw:
        return str(raw)
    version = getattr(getattr(resp, "raw", None), "version", None)
    if version == 20:
        return "HTTP/2"
    if version == 11:
        return "HTTP/1.1"
    if version == 10:
        return "HTTP/1.0"
    return "unknown"


# -- variants ------------------------------------------------------------------

def _api_url(ranking_id: str) -> str:
    return f"https://www.topuniversities.com/rankings/api/ranking/{ranking_id}"


def _headers_for(user_agent: str, page_url: str, context: str) -> Dict[str, str]:
    """Reuse Config.get_headers so the probe sends what the pipeline sends."""
    cfg = Config()
    cfg.user_agent = user_agent
    cfg.ranking_page_url = page_url
    return cfg.get_headers(context)  # type: ignore[arg-type]


def _probe_requests_variant(
    *,
    name: str,
    description: str,
    user_agent: str,
    warm: bool,
    api_url: str,
    page_url: str,
    timeout: float,
    pacer: _Pacer,
) -> VariantResult:
    result = VariantResult(name=name, description=description)
    session = requests.Session()
    try:
        if warm:
            result.steps.append(
                _run_requests_step(
                    session,
                    label="warmup_html_page",
                    url=page_url,
                    headers=_headers_for(user_agent, page_url, "page"),
                    timeout=timeout,
                    pacer=pacer,
                )
            )
        result.steps.append(
            _run_requests_step(
                session,
                label="ranking_api",
                url=api_url,
                headers=_headers_for(user_agent, page_url, "api"),
                timeout=timeout,
                pacer=pacer,
            )
        )
    finally:
        session.close()
    return result


def _probe_curl_cffi_variant(
    *,
    api_url: str,
    page_url: str,
    timeout: float,
    pacer: _Pacer,
    impersonate: str,
) -> VariantResult:
    result = VariantResult(
        name="curl_cffi",
        description=f"Chrome TLS+h2 fingerprint (impersonate={impersonate}), warmed",
    )
    try:
        from curl_cffi import requests as curl_requests  # type: ignore
    except ImportError:
        result.skipped = (
            "curl_cffi not installed. This is the variant that decides whether "
            "Phase 2 is worth building -- install it with `pip install curl_cffi` "
            "and re-run before choosing a client."
        )
        return result

    session = curl_requests.Session(impersonate=impersonate)
    try:
        # curl_cffi drives the header set itself for the impersonated profile;
        # sending Config.get_headers() here would re-introduce the very header
        # ordering mismatch the variant exists to eliminate.
        result.steps.append(
            _run_requests_step(
                session,
                label="warmup_html_page",
                url=page_url,
                headers={},
                timeout=timeout,
                pacer=pacer,
            )
        )
        result.steps.append(
            _run_requests_step(
                session,
                label="ranking_api",
                url=api_url,
                headers={"Accept": "application/json, text/plain, */*", "Referer": page_url},
                timeout=timeout,
                pacer=pacer,
            )
        )
    finally:
        try:
            session.close()
        except Exception:  # noqa: BLE001
            pass
    return result


def _variant_from_dict(payload: Dict[str, Any]) -> VariantResult:
    v = VariantResult(
        name=str(payload.get("name", "")),
        description=str(payload.get("description", "")),
        skipped=str(payload.get("skipped", "") or ""),
    )
    for raw in payload.get("steps", []) or []:
        v.steps.append(
            StepResult(
                label=str(raw.get("label", "")),
                url=str(raw.get("url", "")),
                status=raw.get("status"),
                elapsed_ms=raw.get("elapsed_ms"),
                classification=str(raw.get("classification", "") or ""),
                block_reason=str(raw.get("block_reason", "") or ""),
                evidence=dict(raw.get("evidence", {}) or {}),
                cookies_after=list(raw.get("cookies_after", []) or []),
                http_version=str(raw.get("http_version", "") or ""),
                error=str(raw.get("error", "") or ""),
            )
        )
    return v


def _replay(path: Path) -> int:
    """Re-derive the report and verdict from saved evidence, with no network.

    The verdict is interpretation, and interpretation gets revised. Being able
    to re-run it over an artifact means a change to the reasoning does not cost
    another eight requests against topuniversities.com.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    variants = [_variant_from_dict(v) for v in payload.get("variants", [])]
    pacer = _Pacer(float(payload.get("delay_seconds", 0.0) or 0.0))
    pacer.requests_made = int(payload.get("requests_made", 0) or 0)
    print()
    print(f"REPLAY of {path} (probed_at {payload.get('probed_at', 'unknown')}) -- no requests sent.")
    _print_report(variants, pacer)
    return 0 if any(v.succeeded for v in variants) else 1


# -- verdict -------------------------------------------------------------------

# Reasons that mean Cloudflare, not the origin, ended the request.
_CF_REFUSAL_REASONS = frozenset(
    {BLOCK_REASON_CF_JS_CHALLENGE, BLOCK_REASON_CF_WAF_DENY, BLOCK_REASON_CF_RATE_LIMITED}
)


def _cleared_cloudflare(v: VariantResult) -> bool:
    """Did any request in this variant actually reach the QS origin?

    This is deliberately separate from `succeeded`. A variant can walk straight
    through Cloudflare and still end on a 404 because the ranking id is dead --
    two independent failures that need two different fixes. Judging a variant
    only by its final step conflates them, and reading "curl_cffi did not
    succeed" as "curl_cffi did not get past Cloudflare" is exactly the wrong
    conclusion to draw from that.
    """
    return any(
        s.status is not None and s.block_reason not in _CF_REFUSAL_REASONS
        for s in v.steps
    )


def _verdict(variants: List[VariantResult]) -> List[str]:
    """Turn the observations into the one decision Phase 0 exists to make."""
    ran = [v for v in variants if not v.skipped and v.final is not None]
    if not ran:
        return ["No variant completed. Nothing can be concluded."]

    finals = [v.final for v in ran if v.final is not None]
    reasons = {f.block_reason for f in finals if f.block_reason}
    winners = [v.name for v in ran if v.succeeded]
    curl_variant = next((v for v in variants if v.name == "curl_cffi"), None)

    cleared = [v for v in ran if _cleared_cloudflare(v)]
    cleared_names = [v.name for v in cleared]
    no_dep_names = {"baseline", "clean_ua", "warm_cookie", "clean_ua_warm"}

    lines: List[str] = []

    # -- the Cloudflare question, answered on its own -------------------------
    if cleared and len(cleared) < len(ran):
        lines.append(f"Cloudflare was cleared by: {', '.join(cleared_names)}.")
        cf_blocked = [v.name for v in ran if v not in cleared]
        lines.append(f"Cloudflare refused: {', '.join(cf_blocked)}.")

        if cleared_names == ["curl_cffi"]:
            lines.append(
                "Only the fingerprint variant reached the origin, and every "
                "requests-based variant was refused identically regardless of "
                "User-Agent or cookie warm-up. The TLS/HTTP2 fingerprint is the "
                "discriminating variable: PHASE 2 (transport abstraction + "
                "curl_cffi) is confirmed."
            )
            if BLOCK_REASON_CF_JS_CHALLENGE in reasons:
                lines.append(
                    "The 'Just a moment' interstitial the other variants got does "
                    "NOT mean a browser is required -- curl_cffi was never shown "
                    "one. The challenge is triggered by the fingerprint, so Phase 3 "
                    "(Playwright) is NOT needed on this evidence."
                )
        elif set(cleared_names) & no_dep_names:
            lines.append(
                "A no-new-dependency variant reached the origin. Phase 1 (UA "
                "consistency + cookie warm-up) is sufficient for the Cloudflare "
                "layer. Do NOT introduce curl_cffi or Playwright on this evidence."
            )

        # -- the separate question: did the endpoint return data? -------------
        lines.extend(_origin_findings(cleared))
        return lines

    if winners:
        lines.append(f"Every variant reached the origin; data returned by: {', '.join(winners)}.")
        if "baseline" in winners:
            lines.append(
                "baseline succeeded -- the block is NOT reproducible right now. "
                "It was intermittent or has since been lifted. Do not pick a client "
                "off this run; re-probe when a run actually fails."
            )
        return lines

    if cleared and len(cleared) == len(ran):
        if reasons == {BLOCK_REASON_ORIGIN_DENY}:
            lines.append(
                "Every variant reached the origin. No Cloudflare header appeared on "
                "any refusal -- the QS origin itself is refusing. Client "
                "impersonation would change nothing. Check the ranking_id, the "
                "endpoint path, and whether this universe still exists before "
                "touching the network layer at all."
            )
            return lines
        lines.append(
            "Every variant reached the origin -- Cloudflare is not refusing anyone. "
            "Whatever is failing is not the network layer."
        )
        lines.extend(_origin_findings(cleared))
        return lines

    if BLOCK_REASON_CF_JS_CHALLENGE in reasons:
        if curl_variant is not None and curl_variant.skipped:
            lines.append(
                "Cloudflare is serving a JS interstitial to every variant that ran, "
                "but the curl_cffi variant did NOT run. A fingerprinted client is "
                "often never shown this challenge at all, so Phase 3 is not yet "
                "justified: install curl_cffi and re-run before reaching for a "
                "headless browser."
            )
        else:
            lines.append(
                "Cloudflare is serving a JS interstitial and a Chrome TLS+h2 "
                "fingerprint did not avoid it either. Phase 3 applies: a narrow "
                "Playwright challenge-solver that obtains cf_clearance once and "
                "hands the cookie to the normal client. Keep the browser off the "
                "detail-page fan-out."
            )
    elif reasons == {BLOCK_REASON_ORIGIN_DENY}:
        lines.append(
            "No Cloudflare header appeared on any refusal -- the QS origin itself "
            "is refusing. Client impersonation would change nothing. Check the "
            "ranking_id, the endpoint path, and whether this universe still exists "
            "before touching the network layer at all."
        )
    elif BLOCK_REASON_CF_RATE_LIMITED in reasons:
        lines.append(
            "Rate limited, not fingerprinted. Raise the delay and back off; "
            "changing client would make this worse, not better."
        )
    elif BLOCK_REASON_CF_WAF_DENY in reasons:
        if curl_variant is not None and curl_variant.skipped:
            lines.append(
                "Cloudflare WAF deny with no challenge offered -- consistent with a "
                "bot-score / fingerprint block, which is what curl_cffi addresses. "
                "The curl_cffi variant did not run, so this is not yet confirmed: "
                "install curl_cffi and re-run before committing to Phase 2."
            )
        else:
            lines.append(
                "Cloudflare WAF deny, and a Chrome TLS+h2 fingerprint did not help "
                "either. Fingerprint is not the remaining variable -- IP reputation "
                "is. Phase 2 will not fix this on its own; egress/proxy is the next "
                "thing to test."
            )
    else:
        lines.append("Refusals recorded, but no block_reason matched. Inspect the raw evidence below.")

    if len(reasons) > 1:
        lines.append(f"Note: variants disagreed on the reason ({', '.join(sorted(reasons))}).")
    return lines


def _origin_findings(cleared: List[VariantResult]) -> List[str]:
    """What the origin said once Cloudflare was out of the way.

    Reaching the origin and getting the data are different results, and the
    second one failing is a different bug report than the first.
    """
    lines: List[str] = []
    seen: set[tuple[Any, ...]] = set()
    for v in cleared:
        final = v.final
        if final is None or final.classification == "live_ok":
            continue
        key = (final.label, final.status)
        if key in seen:
            continue
        seen.add(key)
        ct = (final.evidence or {}).get("headers", {}).get("content-type", "")
        html_body = "text/html" in ct.lower()
        if final.status == 404:
            lines.append(
                f"SEPARATE PROBLEM: past Cloudflare, {v.url_label} returned HTTP 404"
                + (" with an HTML error page, not JSON." if html_body else ".")
            )
            lines.append(
                "  The ranking id / API path is dead. This is an origin-side data "
                "problem, independent of the network layer, and it was hidden "
                "behind the Cloudflare 403 until now. Re-resolve the ranking id "
                "before judging whether Phase 2 actually restores the feed."
            )
        elif final.status is not None and final.status >= 400:
            lines.append(
                f"SEPARATE PROBLEM: past Cloudflare, {v.url_label} returned HTTP "
                f"{final.status}. That is an origin-side failure, not a block."
            )
    return lines


# -- reporting -----------------------------------------------------------------

def _print_report(variants: List[VariantResult], pacer: _Pacer) -> None:
    print()
    print("=" * 100)
    print("QS block probe")
    print("=" * 100)
    header = f"{'variant':<16} {'step':<18} {'status':>6} {'classification':<20} {'block_reason':<16} {'ms':>7}"
    print(header)
    print("-" * 100)
    for v in variants:
        if v.skipped:
            print(f"{v.name:<16} SKIPPED: {v.skipped}")
            continue
        for s in v.steps:
            status = "-" if s.status is None else str(s.status)
            print(
                f"{v.name:<16} {s.label:<18} {status:>6} "
                f"{(s.classification or '-'):<20} {(s.block_reason or '-'):<16} "
                f"{(s.elapsed_ms if s.elapsed_ms is not None else 0):>7}"
            )
            if s.error:
                print(f"{'':<16}   error: {s.error}")

    print()
    print("Edge evidence (final step of each variant)")
    print("-" * 100)
    for v in variants:
        final = v.final
        if v.skipped or final is None:
            continue
        hdrs = (final.evidence or {}).get("headers") or {}
        on_cf = (final.evidence or {}).get("on_cloudflare")
        print(f"  {v.name}:")
        print(f"    on_cloudflare = {on_cf}   http_version = {final.http_version or 'unknown'}")
        print(f"    cookies       = {', '.join(final.cookies_after) or '(none)'}")
        for k in sorted(hdrs):
            print(f"    {k:<16} {hdrs[k]}")
        print(f"    body_preview  = {(final.evidence or {}).get('body_preview', '')!r}")
    print()
    print("Verdict")
    print("-" * 100)
    for line in _verdict(variants):
        print(f"  {line}")
    print()
    print(f"({pacer.requests_made} requests issued at {pacer.delay:.1f}s crawl-delay)")
    print()


def _curl_cffi_status() -> tuple[bool, str]:
    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        return False, "NOT AVAILABLE"
    return True, f"available ({getattr(curl_cffi, '__version__', 'unknown')})"


def _print_env_banner(selected: List[str]) -> None:
    """Say which interpreter is running, up front.

    curl_cffi is easy to install into one interpreter and then run the probe
    with another -- the worktree has no .venv of its own, so `python3` resolves
    to the system one. That mismatch does not raise: the curl_cffi variant just
    reports itself skipped, and the run produces a clean-looking report missing
    the single variant that decides whether Phase 2 is worth building. Printing
    this makes the mismatch impossible to miss before the requests go out.
    """
    have_curl, curl_desc = _curl_cffi_status()
    print()
    print(f"  interpreter : {sys.executable}")
    print(f"  requests    : {requests.__version__}")
    print(f"  curl_cffi   : {curl_desc}")
    if "curl_cffi" in selected and not have_curl:
        print()
        print("  WARNING: the curl_cffi variant will be SKIPPED.")
        print("  It is the only variant that tests the TLS/HTTP2 fingerprint")
        print("  hypothesis, so this run cannot confirm or rule out Phase 2.")
        print("  Install it into THIS interpreter, or re-run with the one that has it:")
        print(f"      {sys.executable} -m pip install curl_cffi")


def _print_plan(plan: List[str], pacer: _Pacer, api_url: str, page_url: str) -> None:
    print()
    print("DRY RUN -- no requests will be sent.")
    print(f"  ranking API : {api_url}")
    print(f"  ranking page: {page_url}")
    print(f"  crawl-delay : {pacer.delay:.1f}s (QS robots.txt says 10)")
    print("  variants:")
    for line in plan:
        print(f"    - {line}")
    print()


# -- entry point ---------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ranking-id", default=DEFAULT_RANKING_ID, help="QS ranking node id (default: %(default)s)")
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL, help="HTML ranking page used for warm-up")
    parser.add_argument(
        "--delay",
        type=float,
        default=10.0,
        help="Seconds between requests, shared across variants. QS robots.txt says 10 (default: %(default)s)",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout (default: %(default)s)")
    parser.add_argument("--impersonate", default="chrome124", help="curl_cffi profile (default: %(default)s)")
    parser.add_argument("--out", type=Path, default=None, help="Write the full evidence to this JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan and exit without touching the network")
    parser.add_argument(
        "--replay",
        type=Path,
        default=None,
        help="Re-render the report and verdict from a saved --out JSON, without sending any request",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated variant names to run (baseline, clean_ua, warm_cookie, clean_ua_warm, curl_cffi)",
    )
    args = parser.parse_args(argv)

    if args.replay is not None:
        return _replay(args.replay)

    api_url = _api_url(args.ranking_id)
    page_url = args.page_url
    pacer = _Pacer(args.delay)
    config_ua = Config().user_agent

    builders: Dict[str, tuple[str, Callable[[], VariantResult]]] = {
        "baseline": (
            "exactly what the pipeline sends today (mixed UA, cold cookie jar)",
            lambda: _probe_requests_variant(
                name="baseline",
                description="current pipeline request",
                user_agent=config_ua,
                warm=False,
                api_url=api_url,
                page_url=page_url,
                timeout=args.timeout,
                pacer=pacer,
            ),
        ),
        "clean_ua": (
            "same request, CrawlerNest suffix removed from the User-Agent",
            lambda: _probe_requests_variant(
                name="clean_ua",
                description="consistent Chrome User-Agent",
                user_agent=CLEAN_USER_AGENT,
                warm=False,
                api_url=api_url,
                page_url=page_url,
                timeout=args.timeout,
                pacer=pacer,
            ),
        ),
        "warm_cookie": (
            "current UA, HTML ranking page loaded first to seed CF cookies",
            lambda: _probe_requests_variant(
                name="warm_cookie",
                description="cookie warm-up before the API call",
                user_agent=config_ua,
                warm=True,
                api_url=api_url,
                page_url=page_url,
                timeout=args.timeout,
                pacer=pacer,
            ),
        ),
        "clean_ua_warm": (
            "clean UA + cookie warm-up (the whole of Phase 1)",
            lambda: _probe_requests_variant(
                name="clean_ua_warm",
                description="Phase 1 combined",
                user_agent=CLEAN_USER_AGENT,
                warm=True,
                api_url=api_url,
                page_url=page_url,
                timeout=args.timeout,
                pacer=pacer,
            ),
        ),
        "curl_cffi": (
            f"Chrome TLS+HTTP/2 fingerprint via curl_cffi (impersonate={args.impersonate})",
            lambda: _probe_curl_cffi_variant(
                api_url=api_url,
                page_url=page_url,
                timeout=args.timeout,
                pacer=pacer,
                impersonate=args.impersonate,
            ),
        ),
    }

    selected = [n.strip() for n in args.only.split(",") if n.strip()] or list(builders)
    unknown = [n for n in selected if n not in builders]
    if unknown:
        parser.error(f"unknown variant(s): {', '.join(unknown)}")

    _print_env_banner(selected)

    if args.dry_run:
        _print_plan([f"{n}: {builders[n][0]}" for n in selected], pacer, api_url, page_url)
        return 0

    variants: List[VariantResult] = []
    for name in selected:
        _desc, build = builders[name]
        print(f"[probe] running variant: {name}", flush=True)
        variants.append(build())

    _print_report(variants, pacer)

    if args.out:
        payload = {
            "probed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "api_url": api_url,
            "page_url": page_url,
            "delay_seconds": pacer.delay,
            "requests_made": pacer.requests_made,
            "config_user_agent": config_ua,
            "variants": [v.as_dict() for v in variants],
            "verdict": _verdict(variants),
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[probe] evidence written to {args.out}")

    # Exit non-zero when nothing got through, so a CI/cron caller can notice.
    return 0 if any(v.succeeded for v in variants) else 1


if __name__ == "__main__":
    sys.exit(main())
