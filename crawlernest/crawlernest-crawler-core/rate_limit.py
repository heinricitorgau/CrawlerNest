"""Simple rate limiting primitives."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Block until enough time has passed between requests to the same host.

    The interval is kept per host. A single clock shared by every host is wrong
    in both directions: it lets a burst hit one host whenever another host has
    been idle, and once requests run concurrently it serialises eleven unrelated
    university sites behind one another for no reason. Politeness is a promise to
    a *server*, so the bookkeeping belongs per server.

    ``wait()`` with no host keeps the original single-clock behaviour, which is
    what callers that never learned about hosts still expect.
    """

    def __init__(self, min_interval_seconds: float = 0.0) -> None:
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._lock = threading.Lock()
        self._last_request_at: dict[str, float] = {}

    def wait(self, host: str = "") -> None:
        if self.min_interval_seconds <= 0:
            return
        key = (host or "").strip().lower() or "_default"
        # The sleep happens outside the lock: holding it would make every host
        # queue behind whichever one is currently sleeping, recreating the global
        # clock this class exists to avoid.
        with self._lock:
            now = time.monotonic()
            last = self._last_request_at.get(key, 0.0)
            remaining = self.min_interval_seconds - (now - last) if last else 0.0
            # Reserve this host's slot before releasing, so two threads targeting
            # the same host cannot both decide they may go now.
            self._last_request_at[key] = now + max(0.0, remaining)
        if remaining > 0:
            time.sleep(remaining)

    @property
    def tracked_hosts(self) -> list[str]:
        with self._lock:
            return sorted(self._last_request_at)
