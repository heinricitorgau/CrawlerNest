"""Minimal HTTP client wrapper for crawler engines."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib import request
from urllib.error import HTTPError
from urllib.parse import urlparse

# crawlernest-core, which bootstrap_module_paths puts on sys.path for every
# pipeline command. The decode rule is shared with the extractor fetch path;
# two copies of it are how the two paths came to disagree about the same bytes.
from http_text import decode_http_text
from rate_limit import RateLimiter
from retry import retry_call


@dataclass(slots=True)
class RequestSpec:
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 15.0


@dataclass(slots=True)
class ResponsePayload:
    status_code: int
    url: str
    body: str
    headers: dict[str, str]
    #: Which codec read the body, and whether the response declared it. Carried
    #: so a caller can record a guess as a guess -- see http_text.DecodedText.
    encoding: str = "utf-8"
    encoding_source: str = "utf-8"

    def json(self) -> Any:
        return json.loads(self.body)


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


class HttpClient:
    """Tiny sync HTTP client with retry and per-host rate limiting."""

    def __init__(
        self,
        *,
        user_agent: str = "CrawlerNest/0.1",
        retry_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
        min_interval_seconds: float = 0.0,
    ) -> None:
        self.user_agent = user_agent
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.rate_limiter = RateLimiter(min_interval_seconds)

    def send(self, spec: RequestSpec) -> ResponsePayload:
        host = _host_of(spec.url)

        def _send_once() -> ResponsePayload:
            self.rate_limiter.wait(host)
            headers = {"User-Agent": self.user_agent, **spec.headers}
            req = request.Request(spec.url, method=spec.method.upper(), headers=headers)
            with request.urlopen(req, timeout=spec.timeout_seconds) as response:
                headers = dict(response.headers.items())
                # Was decode("utf-8", errors="replace"), which read a
                # Windows-1252 page as damage: every accented character, and
                # every en dash, became U+FFFD with nothing recording that it
                # had happened.
                decoded = decode_http_text(response.read(), headers.get("Content-Type"))
                return ResponsePayload(
                    status_code=getattr(response, "status", 200),
                    url=response.geturl(),
                    body=decoded.text,
                    headers=headers,
                    encoding=decoded.encoding,
                    encoding_source=decoded.source,
                )

        return retry_call(
            _send_once,
            attempts=self.retry_attempts,
            delay_seconds=self.retry_delay_seconds,
            # An HTTP status is the server's answer, not a failure to reach it.
            # This used to inherit retry_call's default of retrying every
            # Exception, so a 403 was re-sent three times with a sleep between --
            # hammering a site that had already said no, and turning one refusal
            # into three. Only transport failures are worth another attempt.
            non_retriable_exceptions=(HTTPError,),
        )

    def get_text(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        response = self.send(RequestSpec(url=url, headers=headers or {}))
        return response.body

    def get_json(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        response = self.send(RequestSpec(url=url, headers=headers or {}))
        return response.json()
