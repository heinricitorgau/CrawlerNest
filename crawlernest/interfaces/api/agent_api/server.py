from __future__ import annotations

"""Agent API entry point and the helpers its routes share.

    python -m crawlernest.interfaces.api.agent_api --host 127.0.0.1 --port 8090

The routes live in :mod:`.app`, an ASGI application served by Uvicorn. This
module parses the command line, applies the production settings, and refuses a
configuration that would serve wrong answers (see :func:`check_worker_config`).
"""

import argparse
import logging
import os
import re
import sys
from typing import Any

from crawlernest.agent.web_agent.generation.response_generator import generation_stats
from crawlernest.agent.web_agent.generation.verification import verification_stats

APP_FACTORY = "crawlernest.interfaces.api.agent_api.app:create_app"
WORKERS_ENV = "CRAWLERNEST_AGENT_API_WORKERS"


def max_request_bytes() -> int:
    return int(os.environ.get("CRAWLERNEST_AGENT_API_MAX_REQUEST_BYTES", "131072"))


def configure_logging(stream: Any = None, level: str | None = None) -> None:
    """Send this process's logs to stdout, at INFO by default.

    Without this the agent API configures no handler at all, so Python falls back
    to ``logging.lastResort`` -- which writes to **stderr** and drops anything
    below WARNING. Two consequences, both wrong for a service whose logs are read
    from stdout: the dark-judge warning lands on the wrong stream, and the
    recovery message that lets it be closed never appears.

    Unit tests could not have caught it. ``assertLogs`` attaches its own handler,
    so it passes whether or not the process has one.

    Uvicorn's own loggers are left unconfigured (``log_config=None``) and
    propagate here, so server and application lines share one format.
    """
    logging.basicConfig(
        stream=stream if stream is not None else sys.stdout,
        level=(level or os.getenv("CRAWLERNEST_AGENT_API_LOG_LEVEL", "INFO")).upper(),
        format="%(asctime)s %(levelname)s [pid %(process)d] %(name)s: %(message)s",
        force=True,
    )


#: Roughly a word or two per frame. Small enough that the reader sees text
#: arriving rather than appearing, large enough that a long explanation does not
#: become hundreds of writes.
_STREAM_CHUNK_CHARS = 24


def _split_for_stream(text: str, chunk_chars: int = _STREAM_CHUNK_CHARS) -> list[str]:
    """Split *text* into delta frames that rejoin to exactly *text*.

    Splitting happens at whitespace so a chunk boundary never lands inside a
    word, and never inside a multi-byte character. The concatenation property is
    what the tests assert: a reader that joins every delta must end up with the
    same string the non-streaming route would have returned, or the two
    transports are showing different answers.

    CJK text has no spaces to split on, so a long run without whitespace is cut
    at ``chunk_chars`` by index. Python slices by code point, so that is still
    safe -- it is the byte-level split that would corrupt a character, and this
    never does one.
    """
    if not text:
        return []

    chunks: list[str] = []
    current = ""
    # Keep the separators: rejoining the pieces has to reproduce the original
    # whitespace, not a normalized version of it.
    for piece in re.split(r"(\s+)", text):
        if not piece:
            continue
        if len(current) + len(piece) <= chunk_chars:
            current += piece
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(piece) > chunk_chars:
            chunks.append(piece[:chunk_chars])
            piece = piece[chunk_chars:]
        current = piece
    if current:
        chunks.append(current)
    return chunks


def _rate(numerator: int, denominator: int) -> float | None:
    """A proportion, or ``None`` when there is nothing to divide by.

    Zero would read as "this never happens" when the truth is "this has not been
    observed yet", and those call for opposite reactions.
    """
    return round(numerator / denominator, 4) if denominator else None


def configured_workers() -> int:
    try:
        return max(1, int(os.environ.get(WORKERS_ENV, "1")))
    except ValueError:
        return 1


def build_stats_payload() -> dict[str, Any]:
    """Generation and verification counters, plus the rates worth watching.

    Raw counts alone leave the reader to do the division, and the two failure
    modes these counters exist for are only legible as rates: a judge flagging
    everything, and a judge that has quietly gone dark. Both are reported
    directly rather than left to be derived.
    """
    generation = generation_stats()
    verification = verification_stats()

    verified = verification["keep"] + verification["keep_with_warning"] + verification["use_fallback"]
    consulted = (
        verification["judge_agreed"]
        + verification["judge_flagged"]
        + verification["judge_no_opinion"]
    )

    caveats = [
        "Counters are process-local and start at zero on restart. They describe this "
        "process since it started, not the deployment, and not a time window.",
        "Judge rates are over consultations rather than over all explanations: when a "
        "mechanical signal fires it decides alone and the judge is never asked.",
        "rules_flag_rate and provenance_flag_rate can both apply to one explanation, so "
        "they may sum to more than mechanical_rejection_rate.",
    ]
    workers = configured_workers()
    if workers > 1:
        caveats.append(
            f"The agent API runs {workers} worker processes and this response came from one "
            "of them, so these counters cover only the requests that worker served. Two "
            "requests to this route can return different numbers."
        )
    if consulted == 0:
        caveats.append(
            "The judge has not been consulted. Either it is not configured "
            "(WEB_AGENT_JUDGE_BASE_URL unset) or no explanation has reached it yet, and "
            "these counters cannot tell those apart."
        )
    elif verification["judge_no_opinion"] == consulted:
        caveats.append(
            "Every judge consultation returned no opinion. A misconfigured or unreachable "
            "endpoint looks exactly like a healthy one from the responses alone."
        )

    return {
        "success": True,
        "generation": generation,
        "verification": verification,
        "signals": {
            "explanations_verified": verified,
            "mechanical_rejection_rate": _rate(verification["use_fallback"], verified),
            "rules_flag_rate": _rate(verification["rules_flagged"], verified),
            "provenance_flag_rate": _rate(verification["provenance_flagged"], verified),
            "judge_consulted": consulted,
            "judge_flag_rate": _rate(verification["judge_flagged"], consulted),
            "judge_no_opinion_rate": _rate(verification["judge_no_opinion"], consulted),
        },
        "process": {"pid": os.getpid(), "workers": workers},
        "caveats": caveats,
    }


def build_parser() -> argparse.ArgumentParser:
    env = os.environ.get
    parser = argparse.ArgumentParser(description="CrawlerNest agent API server (Uvicorn)")
    parser.add_argument("--host", default=env("CRAWLERNEST_AGENT_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(env("CRAWLERNEST_AGENT_API_PORT", "8090")))
    parser.add_argument(
        "--workers",
        type=int,
        default=configured_workers(),
        help="worker processes; more than 1 requires CRAWLERNEST_AGENT_STORE_BACKEND=postgres",
    )
    parser.add_argument(
        "--limit-concurrency",
        type=int,
        default=int(env("CRAWLERNEST_AGENT_API_LIMIT_CONCURRENCY", "64")),
        help="per worker; beyond it Uvicorn answers 503 instead of queueing without bound",
    )
    parser.add_argument(
        "--timeout-keep-alive", type=int, default=int(env("CRAWLERNEST_AGENT_API_KEEP_ALIVE_SECONDS", "5"))
    )
    parser.add_argument(
        "--graceful-timeout",
        type=int,
        default=int(env("CRAWLERNEST_AGENT_API_GRACEFUL_TIMEOUT_SECONDS", "30")),
        help="seconds in-flight requests get to finish on shutdown",
    )
    parser.add_argument(
        "--forwarded-allow-ips",
        default=env("CRAWLERNEST_AGENT_API_FORWARDED_ALLOW_IPS", "127.0.0.1"),
        help="proxies trusted for X-Forwarded-For/Proto; the Next.js proxy runs on this host",
    )
    parser.add_argument("--access-log", action="store_true", default=env("CRAWLERNEST_AGENT_API_ACCESS_LOG") == "1")
    return parser


def check_worker_config(workers: int, backend: str) -> str | None:
    """Why this worker count cannot run on this store backend, or None.

    With the JSON backend each worker holds its own conversation history and its
    own copy of every JSON file, rewriting the whole file on each change. More
    than one worker then answers a follow-up without the question before it,
    and silently loses whichever worker's write lands first.
    """
    if workers > 1 and backend != "postgres":
        return (
            f"--workers {workers} needs CRAWLERNEST_AGENT_STORE_BACKEND=postgres. With the "
            f"{backend} backend every worker keeps its own conversation history and rewrites "
            "the JSON stores whole, so follow-ups lose context and concurrent writes are lost."
        )
    return None


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    from crawlernest.agent.persistence.factory import AgentStoreConfigError, database_url, store_backend

    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging()
    try:
        backend = store_backend()
        if backend == "postgres":
            database_url()
    except AgentStoreConfigError as exc:
        parser.error(str(exc))
    problem = check_worker_config(args.workers, backend)
    if problem:
        parser.error(problem)

    # Children inherit the environment; the stats route reads it to disclose
    # that its counters describe one worker of several.
    os.environ[WORKERS_ENV] = str(args.workers)

    logging.getLogger("crawlernest.agent_api").info(
        "starting on http://%s:%s with %s worker(s), state backend %s",
        args.host,
        args.port,
        args.workers,
        backend,
    )
    uvicorn.run(
        APP_FACTORY,
        factory=True,
        host=args.host,
        port=args.port,
        workers=args.workers,
        limit_concurrency=args.limit_concurrency,
        timeout_keep_alive=args.timeout_keep_alive,
        timeout_graceful_shutdown=args.graceful_timeout,
        proxy_headers=True,
        forwarded_allow_ips=args.forwarded_allow_ips,
        server_header=False,
        access_log=args.access_log,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
