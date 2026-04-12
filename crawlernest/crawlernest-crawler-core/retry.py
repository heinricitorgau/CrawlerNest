"""Retry helpers shared by crawler engines."""

from __future__ import annotations

import time
from typing import Callable, Iterable, TypeVar


T = TypeVar("T")


def retry_call(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    delay_seconds: float = 1.0,
    retriable_exceptions: Iterable[type[BaseException]] = (Exception,),
) -> T:
    """Retry a callable a small number of times before failing."""
    max_attempts = max(1, int(attempts))
    last_error: BaseException | None = None
    retriable = tuple(retriable_exceptions)

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except retriable as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            time.sleep(max(0.0, delay_seconds))

    assert last_error is not None
    raise last_error
