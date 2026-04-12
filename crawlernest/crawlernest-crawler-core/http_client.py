"""Minimal HTTP client wrapper for crawler engines."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib import request

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

    def json(self) -> Any:
        return json.loads(self.body)


class HttpClient:
    """Tiny sync HTTP client with retry and rate limiting."""

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
        def _send_once() -> ResponsePayload:
            self.rate_limiter.wait()
            headers = {"User-Agent": self.user_agent, **spec.headers}
            req = request.Request(spec.url, method=spec.method.upper(), headers=headers)
            with request.urlopen(req, timeout=spec.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                return ResponsePayload(
                    status_code=getattr(response, "status", 200),
                    url=response.geturl(),
                    body=body,
                    headers=dict(response.headers.items()),
                )

        return retry_call(
            _send_once,
            attempts=self.retry_attempts,
            delay_seconds=self.retry_delay_seconds,
        )

    def get_text(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        response = self.send(RequestSpec(url=url, headers=headers or {}))
        return response.body

    def get_json(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        response = self.send(RequestSpec(url=url, headers=headers or {}))
        return response.json()
