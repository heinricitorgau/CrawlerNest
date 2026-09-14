"""Serve the agent API's ASGI app over a real socket for a test.

The route tests used to start a ThreadingHTTPServer. Starlette's TestClient
would avoid the socket, but it needs httpx (not a dependency) and it skips the
part worth covering: Uvicorn's HTTP handling, chunked streaming, and the thread
pool the synchronous handlers run on. So this runs the same server production
runs, on 127.0.0.1 and an ephemeral port, in a background thread.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Any

import uvicorn


class LiveAgentApi:
    def __init__(self, app: Any) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self.port = self._socket.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        config = uvicorn.Config(app, log_config=None, log_level="warning", access_log=False, lifespan="on")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, kwargs={"sockets": [self._socket]}, daemon=True)

    def __enter__(self) -> "LiveAgentApi":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def start(self) -> None:
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started:
            if not self._thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("the agent API did not start")
            time.sleep(0.01)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)
        self._socket.close()
