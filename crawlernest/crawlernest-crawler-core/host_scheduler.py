"""Run per-URL work concurrently across hosts, serially within a host.

Why a thread pool and not asyncio or a task queue
-------------------------------------------------
The admissions workload is 23 candidate URLs spread over 11 distinct hosts, at
most 3 URLs on any one host, and no host shared between universities. Two facts
follow from that shape:

* The floor on wall-clock time is the *longest single host chain* -- 3 requests --
  not the 23 requests. Concurrency across hosts is worth roughly 23/3, and going
  wider than the host count buys nothing at all.
* Requests to one host must stay serial and spaced. The delay is a promise to
  that server, and the only way to break it is to run two of its URLs at once.

So the useful axis of parallelism is exactly "one worker per host", and the
ceiling is a property of the data, not of the machine.

``asyncio.gather`` with a semaphore would express the same thing, but the fetch
path is blocking ``urllib`` inside a synchronous extractor; converting it would
mean rewriting the client, the crawler and everything that calls them, to reach
the same ceiling that eleven threads reach with none of that. A task queue like
Celery adds a broker, a worker deployment and at-least-once delivery semantics to
schedule 23 HTTP GETs on a timer -- the coordination would cost more than the work.

Threads are the right size for this. If the workload ever grows to thousands of
hosts, the ceiling moves and asyncio becomes the better answer; the interface
here is narrow enough to swap underneath.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, Sequence, TypeVar
from urllib.parse import urlparse

logger = logging.getLogger("crawlernest.host_scheduler")

T = TypeVar("T")
R = TypeVar("R")

#: Never open more than this many host workers, however many hosts appear.
DEFAULT_MAX_WORKERS = 12


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def group_by_host(items: Sequence[T], url_of: Callable[[T], str]) -> dict[str, list[T]]:
    """Bucket work items by hostname, preserving order inside each bucket."""
    groups: dict[str, list[T]] = {}
    for item in items:
        groups.setdefault(host_of(url_of(item)) or "_unknown", []).append(item)
    return groups


def run_grouped_by_host(
    items: Sequence[T],
    worker: Callable[[T], R],
    *,
    url_of: Callable[[T], str],
    max_workers: int = DEFAULT_MAX_WORKERS,
    serial: bool = False,
) -> list[R]:
    """Apply *worker* to every item, in parallel across hosts.

    Items sharing a host are processed one after another on the same thread, in
    their original relative order. Results come back in the order of *items*,
    so a caller can pair them with the input without tracking futures.

    ``serial=True`` runs everything on the calling thread. Tests and CI use it to
    get a deterministic ordering of side effects; it is also the honest way to
    disable concurrency in an incident without editing code.
    """
    if not items:
        return []

    indexed = list(enumerate(items))
    results: list[R | None] = [None] * len(indexed)

    if serial or len(items) == 1:
        for idx, item in indexed:
            results[idx] = worker(item)
        return [r for r in results]  # type: ignore[misc]

    groups = group_by_host(indexed, lambda pair: url_of(pair[1]))
    # A url_of that does not return parseable URLs puts everything in one bucket,
    # which runs the whole list on one thread and looks exactly like "concurrency
    # did not help". Say so instead of degrading quietly.
    if len(groups) == 1 and "_unknown" in groups and len(items) > 1:
        logger.warning(
            "All %d items grouped under an unparseable host; url_of must return a "
            "full URL. Falling back to serial execution.",
            len(items),
        )
    workers = max(1, min(int(max_workers), len(groups)))
    logger.info(
        "Fetching %d item(s) across %d host(s) with %d worker(s); "
        "longest single-host chain is %d",
        len(items),
        len(groups),
        workers,
        max(len(v) for v in groups.values()),
    )

    def _run_chain(chain: list[tuple[int, T]]) -> None:
        for idx, item in chain:
            results[idx] = worker(item)

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="crawl-host") as pool:
        # list() forces every future to be consumed, so an exception raised in a
        # chain surfaces here rather than being swallowed by the executor.
        list(pool.map(_run_chain, groups.values()))

    return [r for r in results]  # type: ignore[misc]
