from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from crawlernest.agent.web_agent.generation.response_generator import (
    WebResponseGenerator,
    generation_stats,
)
from crawlernest.agent.web_agent.generation.verification import verification_stats

from .handler import AgentApiHandler


_MAX_REQUEST_BYTES = int(os.environ.get("CRAWLERNEST_AGENT_API_MAX_REQUEST_BYTES", "131072"))


def configure_logging(stream: Any = None, level: str | None = None) -> None:
    """Send this process's logs to stdout, at INFO by default.

    Without this the agent API configures no handler at all, so Python falls back
    to ``logging.lastResort`` -- which writes to **stderr** and drops anything
    below WARNING. Two consequences, both wrong for a service whose logs are read
    from stdout: the dark-judge warning lands on the wrong stream, and the
    recovery message that lets it be closed never appears.

    Unit tests could not have caught it. ``assertLogs`` attaches its own handler,
    so it passes whether or not the process has one.
    """
    logging.basicConfig(
        stream=stream if stream is not None else sys.stdout,
        level=(level or os.getenv("CRAWLERNEST_AGENT_API_LOG_LEVEL", "INFO")).upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
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
        "caveats": caveats,
    }


class _RequestHandler(BaseHTTPRequestHandler):
    api_handler = AgentApiHandler()
    response_generator = WebResponseGenerator()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write_json(
                HTTPStatus.OK,
                {
                    "success": True,
                    "status": "ok",
                    "generation": self.response_generator.inspect_provider_status(),
                },
            )
            return

        if self.path == "/api/v1/agent/stats":
            self._write_json(HTTPStatus.OK, build_stats_payload())
            return

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"success": False, "error": "route not found"},
        )

    def do_POST(self) -> None:  # noqa: N802
        # /explain is a separate route rather than a task kind on purpose: it
        # must not reach the planner, the tools, or the warehouse. It only turns
        # rows the caller already has into prose.
        if self.path not in {"/api/v1/agent/tasks", "/api/v1/agent/explain"}:
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"success": False, "error": "route not found"},
            )
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > _MAX_REQUEST_BYTES:
            self._write_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {
                    "success": False,
                    "error": "request body too large",
                    "limit_bytes": _MAX_REQUEST_BYTES,
                },
            )
            return
        raw_body = self.rfile.read(content_length)
        if len(raw_body) > _MAX_REQUEST_BYTES:
            self._write_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {
                    "success": False,
                    "error": "request body too large",
                    "limit_bytes": _MAX_REQUEST_BYTES,
                },
            )
            return

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"success": False, "error": "invalid JSON body"},
            )
            return

        if self.path == "/api/v1/agent/explain":
            if self._wants_event_stream():
                self._write_explain_stream(payload)
                return
            status_code, response = self.api_handler.handle_explain(payload)
        else:
            status_code, response = self.api_handler.handle_task(payload)
        self._write_json(HTTPStatus(status_code), response)

    def _wants_event_stream(self) -> bool:
        return "text/event-stream" in (self.headers.get("Accept") or "").lower()

    def _write_explain_stream(self, payload: dict[str, Any]) -> None:
        """Stream the explanation as ``text/event-stream``.

        What is streamed is the *verified* text, not the model's tokens as they
        arrive. That is the whole design, and it is not a shortcut:
        ``verify_explanation`` runs after generation and, when it returns
        USE_FALLBACK, replaces the model's answer with the deterministic one --
        that is the check that catches a fabricated figure or a dropped caveat.
        Forwarding deltas live would put the rejected text on the reader's
        screen before the check that rejects it had run, and no later frame can
        unread it.

        So the cost is honest and worth naming: this buys no time-to-first-token.
        The model still has to finish and be checked before the first delta goes
        out. What it buys is the typewriter rendering, a live channel that shows
        the request is progressing, and a terminal frame carrying source,
        warning and model name in one place.

        Deltas are only emitted for model-written text. When the answer is the
        deterministic fallback the stream carries the terminal frame alone,
        which matches what the page already does with a JSON fallback response:
        it renders nothing.
        """
        status_code, response = self.api_handler.handle_explain(payload)
        data = response.get("data") or {}

        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Connection", "close")
        # Proxies that buffer a response defeat the point of sending one in
        # pieces; nginx honours this and it is inert everywhere else.
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        # Sent before the body so the reader can distinguish "connected, working"
        # from "connected, hung". The generation itself already happened above,
        # so this is the first thing the socket carries either way.
        self._write_sse_frame({"type": "status", "phase": "generating"})

        if response.get("success") and data.get("source") == "llm":
            for chunk in _split_for_stream(str(data.get("explanation") or "")):
                self._write_sse_frame({"type": "delta", "text": chunk})

        self._write_sse_frame(
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
        self._write_sse_frame("[DONE]")

    def _write_sse_frame(self, payload: dict[str, Any] | str) -> None:
        body = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        try:
            self.wfile.write(f"data: {body}\n\n".encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # The reader navigated away mid-stream. Nothing to recover and
            # nothing worth logging: an abandoned explanation is routine.
            pass

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CrawlerNest agent API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging()
    server = ThreadingHTTPServer((args.host, args.port), _RequestHandler)
    print(f"[agent-api] listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
