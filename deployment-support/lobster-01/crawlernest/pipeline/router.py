from __future__ import annotations

from typing import Any, Callable


def dispatch(args: Any, *, run_handler: Callable[[Any], int], query_handler: Callable[[Any], int],
             enrich_handler: Callable[[Any], int], fallback_handler: Callable[[Any], int]) -> int:
    if args.command == "run":
        return run_handler(args)
    if args.command == "query":
        return query_handler(args)
    if args.command == "enrich-details":
        return enrich_handler(args)
    return fallback_handler(args)
