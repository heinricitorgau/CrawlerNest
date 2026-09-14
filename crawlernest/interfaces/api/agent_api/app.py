from __future__ import annotations

"""The agent API as an ASGI application, served by Uvicorn.

It replaces a ``ThreadingHTTPServer`` handler with the same routes, status
codes and bodies. The reasons for the change are operational rather than
functional:

* one thread per connection with no limit, so a burst of slow LLM calls grew
  threads without bound, and there was no graceful shutdown: an in-flight
  explanation was cut off on restart;
* one process only, since state lived in that process;
* no keep-alive timeout, no proxy-header handling, and a 500 that closed the
  socket without a response.

Handlers stay synchronous -- generation is blocking HTTP to the model -- and run
on Starlette's worker thread pool, so the event loop keeps accepting and
streaming while they wait.
"""

import json
import logging
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Any, AsyncIterator

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect, Request
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route

from crawlernest.agent.persistence import factory as stores

logger = logging.getLogger("crawlernest.agent_api")


class _BodyTooLarge(Exception):
    pass


def _json_response(status: int, payload: dict[str, Any]) -> Response:
    # ensure_ascii=False, as before: explanations are often Chinese, and the
    # page reads the body as UTF-8 either way.
    return Response(
        json.dumps(payload, ensure_ascii=False),
        status_code=status,
        media_type="application/json; charset=utf-8",
    )


def _route_not_found() -> Response:
    return _json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "route not found"})


async def _read_limited_body(request: Request, limit: int) -> bytes:
    """The body, refused as soon as it passes *limit* -- declared or actual.

    Content-Length is checked first, but a chunked request declares none, so the
    stream is counted as it arrives rather than buffered whole and measured.
    """
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise _BodyTooLarge
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > limit:
            raise _BodyTooLarge
    return bytes(received)


def create_app(
    *,
    api_handler: Any = None,
    response_generator: Any = None,
    max_request_bytes: int | None = None,
    configure_process_logging: bool = True,
) -> Starlette:
    """Build the app. Uvicorn calls this once per worker process (``--factory``).

    ``api_handler`` and ``response_generator`` are injectable so tests can serve
    a stub over a real socket; production builds the real ones here, inside the
    worker, which is where their stores and connection pools must be created.
    """
    from . import server

    if configure_process_logging:
        server.configure_logging()

    if api_handler is None:
        from .handler import AgentApiHandler

        api_handler = AgentApiHandler()
    if response_generator is None:
        from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator

        response_generator = WebResponseGenerator()
    limit = max_request_bytes if max_request_bytes is not None else server.max_request_bytes()

    async def health(request: Request) -> Response:
        return _json_response(
            HTTPStatus.OK,
            {
                "success": True,
                "status": "ok",
                "generation": response_generator.inspect_provider_status(),
            },
        )

    async def ready(request: Request) -> Response:
        """Readiness: can this worker reach the state it needs to answer?

        /health stays a liveness check that never touches a dependency, so a
        database outage takes workers out of rotation instead of getting them
        restarted in a loop.
        """
        backend = stores.store_backend()
        state: dict[str, Any] = {"backend": backend, "reachable": True}
        if backend == stores.POSTGRES:
            try:
                await run_in_threadpool(stores.state_pool().ping)
            except Exception as exc:  # noqa: BLE001 -- reported, not raised
                state = {"backend": backend, "reachable": False, "error": type(exc).__name__}
        ok = bool(state["reachable"])
        return _json_response(
            HTTPStatus.OK if ok else HTTPStatus.SERVICE_UNAVAILABLE,
            {"success": ok, "status": "ready" if ok else "unavailable", "state": state},
        )

    async def stats(request: Request) -> Response:
        return _json_response(HTTPStatus.OK, server.build_stats_payload())

    async def post_task(request: Request) -> Response:
        payload = await _parse_json_body(request)
        if isinstance(payload, Response):
            return payload
        status_code, response = await run_in_threadpool(api_handler.handle_task, payload)
        return _json_response(status_code, response)

    async def post_explain(request: Request) -> Response:
        # /explain is a separate route rather than a task kind on purpose: it
        # must not reach the planner, the tools, or the warehouse. It only turns
        # rows the caller already has into prose.
        payload = await _parse_json_body(request)
        if isinstance(payload, Response):
            return payload
        status_code, response = await run_in_threadpool(api_handler.handle_explain, payload)
        if "text/event-stream" in (request.headers.get("accept") or "").lower():
            return _explain_stream(status_code, response)
        return _json_response(status_code, response)

    async def _parse_json_body(request: Request) -> dict[str, Any] | Response:
        try:
            raw = await _read_limited_body(request, limit)
        except _BodyTooLarge:
            return _json_response(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"success": False, "error": "request body too large", "limit_bytes": limit},
            )
        except ClientDisconnect:
            return Response(status_code=499)
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _json_response(HTTPStatus.BAD_REQUEST, {"success": False, "error": "invalid JSON body"})
        if not isinstance(payload, dict):
            return _json_response(
                HTTPStatus.BAD_REQUEST, {"success": False, "error": "JSON body must be an object"}
            )
        return payload

    async def not_found(request: Request, exc: Exception) -> Response:
        # 405 included: the old server answered a GET to a POST route with this
        # same 404, and the web proxy does not distinguish them.
        return _route_not_found()

    async def internal_error(request: Request, exc: Exception) -> Response:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return _json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"success": False, "error": "internal error"})

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        backend = stores.store_backend()
        if backend == stores.POSTGRES:
            # Fail the worker at start-up rather than on its first request.
            await run_in_threadpool(stores.state_pool().verify_schema)
        logger.info("agent API worker ready (state backend: %s)", backend)
        try:
            yield
        finally:
            if backend == stores.POSTGRES:
                from crawlernest.agent.persistence.postgres import close_all_pools

                close_all_pools()

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/health/ready", ready, methods=["GET"]),
            Route("/api/v1/agent/stats", stats, methods=["GET"]),
            Route("/api/v1/agent/tasks", post_task, methods=["POST"]),
            Route("/api/v1/agent/explain", post_explain, methods=["POST"]),
        ],
        exception_handlers={404: not_found, 405: not_found, Exception: internal_error},
        lifespan=lifespan,
    )


def _explain_stream(status_code: int, response: dict[str, Any]) -> StreamingResponse:
    """Stream the verified explanation as ``text/event-stream``.

    What is streamed is the *verified* text, not the model's tokens as they
    arrive. ``verify_explanation`` runs after generation and, when it returns
    USE_FALLBACK, replaces the model's answer with the deterministic one -- the
    check that catches a fabricated figure or a dropped caveat. Forwarding live
    deltas would put rejected text on screen before the check that rejects it.

    So this buys no time-to-first-token: the model finishes and is checked before
    the first delta. It buys the typewriter rendering, a channel that shows the
    request progressing, and one terminal frame carrying source, warning and
    model name. Deltas are only sent for model-written text; a deterministic
    fallback streams the terminal frame alone, which is what the page renders
    for the JSON fallback too.
    """
    from .server import _split_for_stream

    data = response.get("data") or {}

    def frame(payload: dict[str, Any] | str) -> str:
        body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return f"data: {body}\n\n"

    async def frames() -> AsyncIterator[str]:
        yield frame({"type": "status", "phase": "generating"})
        if response.get("success") and data.get("source") == "llm":
            for chunk in _split_for_stream(str(data.get("explanation") or "")):
                yield frame({"type": "delta", "text": chunk})
        yield frame(
            {
                "type": "done",
                "statusCode": status_code,
                "success": bool(response.get("success")),
                "taskKind": data.get("taskKind"),
                "source": data.get("source"),
                "modelName": data.get("modelName"),
                "warning": data.get("warning"),
                "paragraphs": data.get("paragraphs") or [],
                "explanation": data.get("explanation"),
            }
        )
        yield frame("[DONE]")

    return StreamingResponse(
        frames(),
        status_code=HTTPStatus.OK,
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            # Proxies that buffer a response defeat the point of sending it in
            # pieces; nginx honours this and it is inert everywhere else.
            "X-Accel-Buffering": "no",
        },
    )
