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
    non_retriable_exceptions: Iterable[type[BaseException]] = (),
) -> T:
    """Retry a callable a small number of times before failing.

    ``non_retriable_exceptions`` is checked first and wins over
    ``retriable_exceptions``. It exists because the interesting cases are
    subclasses of the ones worth retrying -- ``urllib``'s ``HTTPError`` is a
    ``URLError``, so "retry connection problems but never retry a 403" cannot be
    expressed with an allow-tuple alone. Retrying a server that has already
    refused is the one thing a crawler must not do.
    """
    max_attempts = max(1, int(attempts))
    last_error: BaseException | None = None
    retriable = tuple(retriable_exceptions)
    non_retriable = tuple(non_retriable_exceptions)

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except non_retriable:
            raise
        except retriable as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            time.sleep(max(0.0, delay_seconds))

    assert last_error is not None
    raise last_error
