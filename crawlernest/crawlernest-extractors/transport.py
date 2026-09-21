"""HTTP transport selection for the QS fetchers.

Why this layer exists
---------------------
A controlled probe against topuniversities.com (scripts/probe_qs_block.py)
established that Cloudflare's decision is driven by the TLS/HTTP2 fingerprint and
by nothing else we control:

    baseline        403  cf_js_challenge   (mixed "Chrome/122 ... CrawlerNest/1.0" UA)
    clean_ua        403  cf_js_challenge   (plain Chrome UA -- no difference)
    warm_cookie     403  cf_js_challenge   (warm-up request is itself challenged,
                                            so no cookie is ever obtained)
    clean_ua_warm   403  cf_js_challenge
    curl_cffi       200  --                (Chrome fingerprint, HTTP/3, no challenge
                                            offered at all)

So the User-Agent string is a dead end, and a headless browser is unnecessary:
curl_cffi is never shown the interstitial for a page request. What is needed is a
swappable transport, because the fetchers have two parallel implementations (sync
`requests` and async `aiohttp`) and both are blocked.

One correction to the reading above, found later against the live endpoint. The
warm_cookie row does NOT show that warming is useless -- it shows that on the
`requests` stack the warm-up request is itself challenged, so no warming ever
happens. Once the fingerprint is right, warming becomes both possible and
required:

    curl_cffi, cold, straight to /rankings/endpoint ... 403, "Just a moment"
    curl_cffi, after one GET of the ranking page ..... 200, 813 KB of JSON

Fingerprint alone is not sufficient for the JSON endpoint; it needs a document
request on the same session first. UniversityFetcher._warm_session_for_endpoint
is what guarantees that, and it matters most on runs that take the ranking id
from the resolution cache and would otherwise never touch a page.

Design
------
curl_cffi mirrors the `requests` API closely enough that the synchronous side is
a genuine drop-in -- same ``Session.get`` signature, same response attributes,
and an exception hierarchy with the same names. The synchronous swap is therefore
just a different session object.

The asynchronous side is not a drop-in: aiohttp's ``session.get()`` returns an
async context manager whose ``.text()`` is a coroutine and whose status lives on
``.status``, while curl_cffi's is a coroutine returning a response with a plain
``.text`` property and ``.status_code``. `AiohttpShapedSession` below adapts the
latter to the former, so `AsyncUniversityFetcher` keeps its aiohttp-shaped call
sites unchanged.

Selection
---------
``CRAWLERNEST_HTTP_BACKEND`` = ``auto`` (default) | ``requests`` | ``curl_cffi``.
``auto`` prefers curl_cffi when it is importable and falls back to the stdlib
stack otherwise, so an environment without the dependency still runs -- it just
runs blocked, and says so.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests

# crawlernest-core, on sys.path via bootstrap_module_paths. Shared with
# crawlernest-crawler-core/http_client.py on purpose: the two fetch paths used
# to disagree about the same bytes because each had its own idea of the default.
from http_text import decode_http_text

logger = logging.getLogger("UniversityFetcher.transport")

BACKEND_REQUESTS = "requests"
BACKEND_CURL_CFFI = "curl_cffi"
BACKEND_AUTO = "auto"

#: Chrome profile curl_cffi impersonates. Kept close to the User-Agent the config
#: advertises so the fingerprint and the string do not contradict each other.
DEFAULT_IMPERSONATE = "chrome124"

try:  # pragma: no cover - presence depends on the environment
    from curl_cffi import requests as curl_requests
    from curl_cffi.requests import exceptions as curl_exceptions

    CURL_CFFI_AVAILABLE = True
except ImportError:  # pragma: no cover
    curl_requests = None  # type: ignore[assignment]
    curl_exceptions = None  # type: ignore[assignment]
    CURL_CFFI_AVAILABLE = False


# -- unified exception sets ----------------------------------------------------
#
# Both backends raise their own hierarchies. Classification code should not have
# to know which session produced an exception, so the tuples below union whatever
# is importable. curl_cffi's names mirror requests' deliberately.

def _union(*candidates: Any) -> Tuple[type[BaseException], ...]:
    out: list[type[BaseException]] = []
    for c in candidates:
        if isinstance(c, type) and issubclass(c, BaseException) and c not in out:
            out.append(c)
    return tuple(out)


TIMEOUT_ERRORS = _union(
    requests.Timeout,
    getattr(curl_exceptions, "Timeout", None),
)
CONNECTION_ERRORS = _union(
    requests.ConnectionError,
    getattr(curl_exceptions, "ConnectionError", None),
)
REQUEST_ERRORS = _union(
    requests.RequestException,
    getattr(curl_exceptions, "RequestException", None),
)
#: Transport-level failures worth retrying. HTTP status codes are never in here.
TRANSIENT_ERRORS = _union(*TIMEOUT_ERRORS, *CONNECTION_ERRORS)


@dataclass(frozen=True)
class TransportChoice:
    backend: str
    impersonate: str
    reason: str

    @property
    def is_fingerprinted(self) -> bool:
        return self.backend == BACKEND_CURL_CFFI

    def as_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "impersonate": self.impersonate if self.is_fingerprinted else "",
            "reason": self.reason,
        }


def _requested_backend(config: Optional[Any] = None) -> str:
    raw = str(getattr(config, "http_backend", "") or "").strip().lower()
    if not raw:
        raw = str(os.getenv("CRAWLERNEST_HTTP_BACKEND", "") or "").strip().lower()
    return raw or BACKEND_AUTO


def _requested_impersonate(config: Optional[Any] = None) -> str:
    raw = str(getattr(config, "http_impersonate", "") or "").strip()
    if not raw:
        raw = str(os.getenv("CRAWLERNEST_HTTP_IMPERSONATE", "") or "").strip()
    return raw or DEFAULT_IMPERSONATE


def resolve_backend(config: Optional[Any] = None) -> TransportChoice:
    """Decide which HTTP stack to use, and record why."""
    requested = _requested_backend(config)
    impersonate = _requested_impersonate(config)

    if requested == BACKEND_REQUESTS:
        return TransportChoice(BACKEND_REQUESTS, impersonate, "explicitly requested")

    if requested == BACKEND_CURL_CFFI:
        if not CURL_CFFI_AVAILABLE:
            # Explicit means explicit: silently downgrading would produce a run
            # that is blocked for a reason the operator already tried to fix.
            raise RuntimeError(
                "CRAWLERNEST_HTTP_BACKEND=curl_cffi but curl_cffi is not installed. "
                "Install it (pip install curl_cffi) or unset the variable."
            )
        return TransportChoice(BACKEND_CURL_CFFI, impersonate, "explicitly requested")

    if requested != BACKEND_AUTO:
        raise ValueError(
            f"Unknown CRAWLERNEST_HTTP_BACKEND {requested!r}; "
            f"expected one of: {BACKEND_AUTO}, {BACKEND_REQUESTS}, {BACKEND_CURL_CFFI}"
        )

    if CURL_CFFI_AVAILABLE:
        return TransportChoice(BACKEND_CURL_CFFI, impersonate, "auto: curl_cffi available")
    return TransportChoice(
        BACKEND_REQUESTS,
        impersonate,
        "auto: curl_cffi not installed -- QS requests will be challenged by Cloudflare",
    )


# -- request headers -----------------------------------------------------------
#
# Config.get_headers() hand-builds a browser-looking header set: User-Agent,
# Accept-Encoding, Connection, Cache-Control, Pragma, Origin, Upgrade-Insecure-
# Requests and the Sec-Fetch-* family. That set exists to make `requests` pass for
# a browser, which the probe showed it never did.
#
# Sent through an impersonated stack it is actively harmful. Measured against
# topuniversities.com with impersonate=chrome124:
#
#     no extra headers ............................. 200
#     User-Agent only .............................. 200      (so the UA is not the tell)
#     Accept / Accept-Language / Cache-Control /
#       Origin / Pragma / Referer, each alone ...... 200
#     all six together ............................. 403 challenge
#     the full Config.get_headers("page") set ...... 403 challenge
#     Accept + Referer + X-Requested-With .......... 200
#
# No single header trips it; the combination does. Chrome's header *order* is part
# of what is being matched, and merging a large custom set into the profile's
# disturbs it. So on a fingerprinted transport we send only headers carrying
# meaning the profile cannot supply, and let the profile own the rest.

#: Headers that say something about *this request* rather than about the client.
SEMANTIC_HEADERS = frozenset({"accept", "referer", "x-requested-with"})


def request_headers(choice: TransportChoice, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Per-request headers appropriate to the chosen backend.

    On `requests` the hand-built set is all we have, so it passes through
    untouched. On curl_cffi it is reduced to the semantic subset above.
    """
    if not headers:
        return {}
    if not choice.is_fingerprinted:
        return dict(headers)
    return {k: v for k, v in headers.items() if k.lower() in SEMANTIC_HEADERS}


# -- synchronous ---------------------------------------------------------------

def build_sync_session(choice: TransportChoice, *, user_agent: str, extra_headers: Dict[str, str]):
    """A requests-compatible session for the chosen backend.

    curl_cffi's Session takes the same arguments and returns responses with the
    same attributes, so callers keep using ``.get()``, ``.status_code``, ``.text``,
    ``.headers``, ``.json()`` and ``.raise_for_status()`` unchanged.
    """
    if choice.backend == BACKEND_CURL_CFFI:
        if curl_requests is None:  # pragma: no cover - guarded by resolve_backend
            raise RuntimeError("curl_cffi is not installed")
        session = curl_requests.Session(impersonate=choice.impersonate)
        # Do NOT set User-Agent here. The impersonation profile supplies a
        # complete, internally consistent header set; overriding one member of it
        # re-introduces the mismatch this backend exists to remove.
        session.headers.update(extra_headers)
        return session

    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, **extra_headers})
    return session


def response_text(response: Any) -> str:
    """The body as text, read with the charset the response declares.

    Replaces ``response.text`` at every call site that parses names out of a
    page. The libraries disagree about what to do when nothing is declared:
    ``requests`` returns ISO-8859-1 for ``text/html`` -- which maps 0x80-0x9F to
    C1 controls and mangles every accent -- while curl_cffi returns UTF-8, so the
    same page yielded different names depending on which backend was available.
    ``http_text.decode_http_text`` decides once, for both.

    Falls back to whatever the library produced only when the body cannot be
    read as bytes, which is the shape a test double usually has.
    """
    body = getattr(response, "content", None)
    if not isinstance(body, (bytes, bytearray)):
        return getattr(response, "text", "") or ""
    headers = getattr(response, "headers", None) or {}
    try:
        content_type = headers.get("Content-Type") or headers.get("content-type")
    except AttributeError:
        content_type = None
    return decode_http_text(bytes(body), content_type).text


# -- asynchronous --------------------------------------------------------------

class _AiohttpShapedResponse:
    """curl_cffi response wearing aiohttp's shape.

    Only the surface `AsyncUniversityFetcher` actually touches: ``.status``,
    ``.headers``, ``await .text()``, ``.raise_for_status()``, and use as an async
    context manager.
    """

    def __init__(self, response: Any) -> None:
        self._response = response

    @property
    def status(self) -> int:
        return int(self._response.status_code)

    @property
    def status_code(self) -> int:
        return int(self._response.status_code)

    @property
    def headers(self) -> Any:
        return self._response.headers

    async def text(self) -> str:
        return response_text(self._response)

    def json(self) -> Any:
        return self._response.json()

    def raise_for_status(self) -> None:
        self._response.raise_for_status()

    async def __aenter__(self) -> "_AiohttpShapedResponse":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None


class _AiohttpShapedRequest:
    """Awaits the curl_cffi coroutine lazily, so ``async with session.get(...)`` works.

    aiohttp's ``session.get()`` returns a context manager immediately; curl_cffi's
    returns a coroutine. Deferring the await until ``__aenter__`` bridges the two
    without changing a single call site in the fetcher.
    """

    def __init__(self, coro: Any) -> None:
        self._coro = coro
        self._response: Optional[_AiohttpShapedResponse] = None

    async def __aenter__(self) -> "_AiohttpShapedResponse":
        self._response = _AiohttpShapedResponse(await self._coro)
        return self._response

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    def __await__(self):
        async def _inner() -> _AiohttpShapedResponse:
            return _AiohttpShapedResponse(await self._coro)

        return _inner().__await__()


class AiohttpShapedSession:
    """curl_cffi AsyncSession presented with aiohttp's call signature."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def get(self, url: str, **kwargs: Any) -> _AiohttpShapedRequest:
        return _AiohttpShapedRequest(self._session.get(url, **_translate_kwargs(kwargs)))

    async def close(self) -> None:
        await self._session.close()


def _translate_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Drop or convert aiohttp-only arguments.

    ``ssl=`` is an aiohttp connector concept with no curl_cffi equivalent -- the
    impersonated stack manages its own TLS. ``timeout=`` arrives as an
    aiohttp.ClientTimeout and has to become a number.
    """
    out = dict(kwargs)
    out.pop("ssl", None)
    timeout = out.get("timeout")
    if timeout is not None and not isinstance(timeout, (int, float)):
        total = getattr(timeout, "total", None)
        out["timeout"] = float(total) if total else 30.0
    params = out.get("params")
    if params is not None and not params:
        out.pop("params")
    return out


def build_async_session(
    choice: TransportChoice,
    *,
    aiohttp_module: Any,
    connector_factory: Any,
    headers: Dict[str, str],
):
    """An aiohttp-shaped async session for the chosen backend."""
    if choice.backend == BACKEND_CURL_CFFI:
        if curl_requests is None:  # pragma: no cover - guarded by resolve_backend
            raise RuntimeError("curl_cffi is not installed")
        # Same reasoning as the sync side: let the impersonation profile own the
        # headers it is responsible for.
        safe_headers = {k: v for k, v in headers.items() if k.lower() != "user-agent"}
        return AiohttpShapedSession(
            curl_requests.AsyncSession(impersonate=choice.impersonate, headers=safe_headers)
        )

    if aiohttp_module is None:
        raise RuntimeError("aiohttp is not installed")
    return aiohttp_module.ClientSession(connector=connector_factory(), headers=headers)


def log_choice(choice: TransportChoice, *, where: str) -> None:
    if choice.is_fingerprinted:
        logger.info(
            "HTTP transport (%s): %s impersonate=%s (%s)",
            where,
            choice.backend,
            choice.impersonate,
            choice.reason,
        )
        return
    logger.warning(
        "HTTP transport (%s): %s (%s). QS ranking requests are expected to be "
        "challenged by Cloudflare on this backend.",
        where,
        choice.backend,
        choice.reason,
    )
