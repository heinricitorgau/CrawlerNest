"""The agent API under Uvicorn: the contract the old server kept, and what it lacked.

The route bodies are covered elsewhere (stats, explain, SSE). These cover the
transport the move to ASGI changed: limits, error shapes, not blocking the event
loop on a slow model, and refusing a worker count that would serve wrong
answers.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_api_live_server import LiveAgentApi  # noqa: E402
from crawlernest.agent.persistence import factory  # noqa: E402
from crawlernest.interfaces.api.agent_api import server  # noqa: E402
from crawlernest.interfaces.api.agent_api.app import create_app  # noqa: E402


class _Generator:
    def inspect_provider_status(self):
        return {"configured": False, "providerLabel": "stub"}


class _Handler:
    def __init__(self, delay: float = 0.0, fail: bool = False) -> None:
        self.delay = delay
        self.fail = fail
        self.payloads: list[dict] = []

    def handle_task(self, payload):
        if self.fail:
            raise RuntimeError("boom")
        time.sleep(self.delay)
        self.payloads.append(payload)
        return 200, {"success": True, "data": {"echo": payload}}

    def handle_explain(self, payload):
        time.sleep(self.delay)
        return 200, {"success": True, "data": {"source": "fallback", "explanation": ""}}


class _LiveCase(unittest.TestCase):
    handler_kwargs: dict = {}
    max_request_bytes = 256

    def setUp(self) -> None:
        self.handler = _Handler(**self.handler_kwargs)
        self._env = mock.patch.dict(os.environ, {factory.BACKEND_ENV: "json"})
        self._env.start()
        app = create_app(
            api_handler=self.handler,
            response_generator=_Generator(),
            max_request_bytes=self.max_request_bytes,
            configure_process_logging=False,
        )
        self.api = LiveAgentApi(app)
        self.api.start()

    def tearDown(self) -> None:
        self.api.stop()
        self._env.stop()

    def request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        req = urllib.request.Request(self.api.base_url + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()


class TestRoutesKeepTheirContract(_LiveCase):
    def test_health_is_unchanged(self):
        status, _, body = self.request("GET", "/health")
        self.assertEqual(200, status)
        self.assertEqual({"success": True, "status": "ok", "generation": _Generator().inspect_provider_status()},
                         json.loads(body))

    def test_readiness_reports_the_state_backend(self):
        status, _, body = self.request("GET", "/health/ready")
        self.assertEqual(200, status)
        self.assertEqual({"backend": "json", "reachable": True}, json.loads(body)["state"])

    def test_unknown_routes_and_wrong_methods_answer_the_same_404(self):
        for method, path in (("GET", "/nope"), ("GET", "/api/v1/agent/tasks"), ("POST", "/health")):
            with self.subTest(method=method, path=path):
                status, headers, body = self.request(method, path, body=b"{}" if method == "POST" else None)
                self.assertEqual(404, status)
                self.assertEqual({"success": False, "error": "route not found"}, json.loads(body))
                self.assertIn("application/json", headers.get("Content-Type"))

    def test_a_task_reaches_the_handler_and_non_ascii_survives(self):
        payload = {"userInput": "推薦英國大學", "kind": "recommendation"}
        status, headers, body = self.request(
            "POST", "/api/v1/agent/tasks", json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(200, status)
        self.assertEqual(payload, json.loads(body.decode("utf-8"))["data"]["echo"])
        self.assertIn("推薦", body.decode("utf-8"), "the body must not be ASCII-escaped")

    def test_invalid_and_non_object_json_are_400(self):
        for raw, error in ((b"{not json", "invalid JSON body"), (b"[1, 2]", "JSON body must be an object")):
            with self.subTest(raw=raw):
                status, _, body = self.request("POST", "/api/v1/agent/tasks", raw)
                self.assertEqual(400, status)
                self.assertEqual(error, json.loads(body)["error"])
        self.assertEqual([], self.handler.payloads)

    def test_an_oversized_body_is_refused_declared_or_chunked(self):
        big = json.dumps({"userInput": "x" * 1024}).encode("utf-8")
        status, _, body = self.request("POST", "/api/v1/agent/tasks", big)
        self.assertEqual(413, status)
        self.assertEqual(256, json.loads(body)["limit_bytes"])

        # No Content-Length: the limit has to be enforced on the stream itself.
        conn = http.client.HTTPConnection("127.0.0.1", self.api.port, timeout=10)
        conn.putrequest("POST", "/api/v1/agent/tasks")
        conn.putheader("Transfer-Encoding", "chunked")
        conn.endheaders()
        for start in range(0, len(big), 100):
            piece = big[start : start + 100]
            conn.send(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
        conn.send(b"0\r\n\r\n")
        response = conn.getresponse()
        self.assertEqual(413, response.status)
        conn.close()
        self.assertEqual([], self.handler.payloads)


class TestFailuresAnswerJson(_LiveCase):
    handler_kwargs = {"fail": True}

    def test_an_unhandled_error_is_a_json_500_not_a_dropped_socket(self):
        with self.assertLogs("crawlernest.agent_api", level="ERROR"):
            status, _, body = self.request("POST", "/api/v1/agent/tasks", b"{}")
        self.assertEqual(500, status)
        self.assertEqual({"success": False, "error": "internal error"}, json.loads(body))


class TestSlowGenerationDoesNotBlockTheServer(_LiveCase):
    handler_kwargs = {"delay": 0.6}

    def test_slow_requests_run_concurrently_and_health_stays_responsive(self):
        results: list[int] = []

        def call():
            status, _, _ = self.request("POST", "/api/v1/agent/explain", b"{}")
            results.append(status)

        started = time.monotonic()
        threads = [threading.Thread(target=call) for _ in range(4)]
        for thread in threads:
            thread.start()
        time.sleep(0.1)
        health_started = time.monotonic()
        status, _, _ = self.request("GET", "/health")
        health_seconds = time.monotonic() - health_started
        for thread in threads:
            thread.join()
        elapsed = time.monotonic() - started

        self.assertEqual(200, status)
        self.assertLess(health_seconds, 0.3, "the event loop waited on a blocking handler")
        self.assertEqual([200] * 4, results)
        self.assertLess(elapsed, 4 * 0.6, "the four slow requests ran one after another")


class TestWorkerConfiguration(unittest.TestCase):
    def test_several_workers_need_the_postgres_backend(self):
        self.assertIsNone(server.check_worker_config(1, "json"))
        self.assertIsNone(server.check_worker_config(4, "postgres"))
        self.assertIn("CRAWLERNEST_AGENT_STORE_BACKEND=postgres", server.check_worker_config(2, "json"))

    def test_main_refuses_before_starting_a_server(self):
        with mock.patch.dict(os.environ, {factory.BACKEND_ENV: "json"}), \
                mock.patch("uvicorn.run") as run, \
                mock.patch.object(server, "configure_logging"), \
                self.assertRaises(SystemExit):
            server.main(["--workers", "3"])
        run.assert_not_called()

    def test_postgres_without_a_database_url_is_refused(self):
        env = {factory.BACKEND_ENV: "postgres"}
        with mock.patch.dict(os.environ, env), mock.patch("uvicorn.run") as run, \
                mock.patch.object(server, "configure_logging"), self.assertRaises(SystemExit):
            os.environ.pop(factory.DATABASE_URL_ENV, None)
            server.main([])
        run.assert_not_called()

    def test_main_serves_the_factory_with_production_settings(self):
        with mock.patch.dict(os.environ, {factory.BACKEND_ENV: "json"}), \
                mock.patch("uvicorn.run") as run, mock.patch.object(server, "configure_logging"):
            server.main(["--port", "8123"])
        args, kwargs = run.call_args
        self.assertEqual(server.APP_FACTORY, args[0])
        self.assertTrue(kwargs["factory"])
        self.assertEqual(1, kwargs["workers"])
        self.assertEqual(8123, kwargs["port"])
        self.assertGreater(kwargs["timeout_graceful_shutdown"], 0)
        self.assertIsNotNone(kwargs["limit_concurrency"])


class TestStoreFactory(unittest.TestCase):
    def test_the_json_backend_no_longer_defaults_to_tmp(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(
            os.environ, {"HOME": home, "XDG_STATE_HOME": ""}, clear=False
        ):
            for key in (factory.STATE_DIR_ENV, factory.BACKEND_ENV, "CRAWLERNEST_STRATEGY_STORE_PATH"):
                os.environ.pop(key, None)
            path = Path(factory.strategy_store()._path)
            self.assertEqual(Path(home) / ".local" / "state" / "crawlernest" / "agent" / "strategies.json", path)

    def test_the_state_dir_and_per_store_overrides_are_honoured(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.dict(os.environ, {factory.STATE_DIR_ENV: root}):
            os.environ.pop("CRAWLERNEST_EXPERIENCE_STORE_PATH", None)
            self.assertEqual(Path(root) / "experiences.json", factory.experience_store()._path)
            with mock.patch.dict(os.environ, {"CRAWLERNEST_EXPERIENCE_STORE_PATH": f"{root}/x.json"}):
                self.assertEqual(Path(root) / "x.json", factory.experience_store()._path)

    def test_an_unknown_backend_is_an_error_not_a_silent_default(self):
        with mock.patch.dict(os.environ, {factory.BACKEND_ENV: "redis"}):
            with self.assertRaises(factory.AgentStoreConfigError):
                factory.conversation_store()

    def test_json_writes_are_atomic(self):
        from crawlernest.agent.self_rewrite.patch_store import PatchStore

        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "patches.json"
            store = PatchStore(path=str(path))
            store.append(task="t", patch_candidate={}, patch_validation={"valid": True}, patch_execution={})
            with mock.patch("os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    store.append(task="t2", patch_candidate={}, patch_validation={}, patch_execution={})
            # The earlier file is intact and no temp file is left behind.
            self.assertEqual(1, len(json.loads(path.read_text(encoding="utf-8"))["entries"]))
            self.assertEqual(["patches.json"], sorted(p.name for p in Path(root).iterdir()))


class TestOneServiceSharesItsStores(unittest.TestCase):
    def test_orchestrator_and_web_engine_read_one_conversation_history(self):
        from crawlernest.agent.service.agent_service import AgentService

        with tempfile.TemporaryDirectory() as root, mock.patch.dict(
            os.environ, {factory.STATE_DIR_ENV: root, factory.BACKEND_ENV: "json"}
        ):
            for key in ("CRAWLERNEST_LONG_TERM_MEMORY_PATH", "CRAWLERNEST_STRATEGY_STORE_PATH",
                        "CRAWLERNEST_EXPERIENCE_STORE_PATH", "CRAWLERNEST_PATCH_STORE_PATH"):
                os.environ.pop(key, None)
            service = AgentService()
        web = service._web_engine
        self.assertIs(web._memory, service._orchestrator._memory)
        self.assertIs(web._long_term_retriever._store, web._long_term_writer._store)


if __name__ == "__main__":
    unittest.main()
