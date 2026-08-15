from __future__ import annotations

import argparse
import json
import logging
import os
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
        "Judge rates are over consultations rather than over all explanations: when the "
        "rules fire they decide alone and the judge is never asked.",
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
            "rules_rejection_rate": _rate(verification["use_fallback"], verified),
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
            status_code, response = self.api_handler.handle_explain(payload)
        else:
            status_code, response = self.api_handler.handle_task(payload)
        self._write_json(HTTPStatus(status_code), response)

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
