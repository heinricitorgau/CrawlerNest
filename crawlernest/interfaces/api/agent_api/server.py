from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from crawlernest.agent.web_agent.generation.response_generator import (
    WebResponseGenerator,
)

from .handler import AgentApiHandler


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

        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"success": False, "error": "route not found"},
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/v1/agent/tasks":
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"success": False, "error": "route not found"},
            )
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"success": False, "error": "invalid JSON body"},
            )
            return

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
