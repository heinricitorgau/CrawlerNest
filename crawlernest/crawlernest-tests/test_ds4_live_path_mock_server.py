"""Live-path integration tests against a mock OpenAI-compatible server.

These exercise the REAL HTTP round-trip that ds4 would serve: request encoding,
the /v1/chat/completions call, response parsing, and the source="llm" vs
"fallback" mapping. Only the model itself is mocked, so this runs anywhere (no
GPU, no ds4-server) and covers everything the offline unit tests cannot: the
actual network path through WebResponseGenerator.
"""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from crawlernest.agent.web_agent.generation.models import PromptPayload
from crawlernest.agent.web_agent.generation.ranking_explainer import RankingExplainer
from crawlernest.agent.web_agent.generation.recommendation_explainer import (
    RecommendationExplainer,
)
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator


class _MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence server logging
        pass

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8"))
        except ValueError:
            body = None
        # Record the request so the test can assert on what was sent.
        self.server.requests.append({"path": self.path, "method": "POST", "body": body})

        if self.server.next_sse is not None:
            self.send_response(self.server.next_status)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for frame in self.server.next_sse:
                self.wfile.write(f"data: {frame}\n\n".encode("utf-8"))
            self.wfile.flush()
            return

        status = self.server.next_status
        payload = json.dumps(self.server.next_body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _MockServer(ThreadingHTTPServer):
    def __init__(self, addr) -> None:
        super().__init__(addr, _MockHandler)
        self.requests: list[dict] = []
        self.next_status = 200
        self.next_body: dict = {}
        # When set, respond as text/event-stream with these raw `data:` frames.
        self.next_sse: list[str] | None = None


_ITEMS = [
    {
        "universityName": "National Taiwan University",
        "country": "Taiwan",
        "category": "target",
        "aggregatedRank": 68,
        "matchingScore": 0.82,
        "recommendationConfidence": "medium",
    }
]


class TestDs4LivePath(unittest.TestCase):
    def setUp(self) -> None:
        self.server = _MockServer(("127.0.0.1", 0))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self._env = mock.patch.dict(
            "os.environ",
            {
                "WEB_AGENT_DS4_BASE_URL": f"http://127.0.0.1:{self.port}",
                "WEB_AGENT_GENERATION_DISABLED": "",
                "WEB_AGENT_OPENAI_BASE_URL": "",
                "OPENAI_BASE_URL": "",
            },
            clear=False,
        )
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        self.server.shutdown()
        self.server.server_close()

    def _chat_response(self, content) -> dict:
        return {"choices": [{"message": {"content": content}}]}

    def test_success_recommendation_full_round_trip(self) -> None:
        self.server.next_status = 200
        self.server.next_body = self._chat_response("MOCK LLM REPLY")

        result = RecommendationExplainer(verify=False).explain(
            items=_ITEMS,
            profile={"country": "Taiwan"},
            query="recommend for me",
            caveats=["Only QS is available."],
            deterministic_reply="Rule-based reply.",
        )

        # Response parsing / mapping.
        self.assertEqual(result.source, "llm")
        self.assertEqual(result.text, "MOCK LLM REPLY")
        self.assertEqual(result.model_name, "deepseek-v4-flash")

        # Request encoding: the server actually received a well-formed call.
        self.assertEqual(len(self.server.requests), 1)
        req = self.server.requests[0]
        self.assertEqual(req["path"], "/v1/chat/completions")
        self.assertEqual(req["body"]["model"], "deepseek-v4-flash")
        messages = req["body"]["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("computed mechanically", messages[0]["content"])
        self.assertEqual(messages[-1]["role"], "user")
        # The grounded evidence reached the wire.
        self.assertIn("aggregated_rank=68", messages[-1]["content"])
        self.assertIn("Only QS is available.", messages[-1]["content"])

    def test_success_ranking_uses_same_network_path(self) -> None:
        self.server.next_status = 200
        self.server.next_body = self._chat_response("RANKING PROSE")

        result = RankingExplainer().explain(
            items=[{"universityName": "NTU", "aggregatedRank": 68, "primarySource": "QS"}],
            focus_entity="NTU",
            query="where does NTU rank",
            deterministic_reply="Rule-based ranking reply.",
        )

        self.assertEqual(result.source, "llm")
        self.assertEqual(result.text, "RANKING PROSE")
        self.assertEqual(self.server.requests[0]["path"], "/v1/chat/completions")

    def test_content_returned_as_text_blocks_is_joined(self) -> None:
        self.server.next_status = 200
        self.server.next_body = self._chat_response(
            [{"type": "text", "text": "BLOCK A"}, {"type": "text", "text": "BLOCK B"}]
        )

        result = RecommendationExplainer(verify=False).explain(
            items=_ITEMS, deterministic_reply="Rule-based reply."
        )

        self.assertEqual(result.source, "llm")
        self.assertEqual(result.text, "BLOCK A\n\nBLOCK B")
        self.assertEqual(result.paragraphs, ["BLOCK A", "BLOCK B"])

    def test_http_error_falls_back_to_deterministic(self) -> None:
        self.server.next_status = 500
        self.server.next_body = {"error": "boom"}

        result = RecommendationExplainer(verify=False).explain(
            items=_ITEMS, deterministic_reply="Rule-based reply."
        )

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Rule-based reply.")
        self.assertIsNotNone(result.warning)

    def test_generation_stats_track_llm_and_fallback(self) -> None:
        from crawlernest.agent.web_agent.generation.response_generator import (
            generation_stats,
            reset_generation_stats,
        )

        reset_generation_stats()

        self.server.next_status = 200
        self.server.next_body = self._chat_response("ok")
        RecommendationExplainer(verify=False).explain(items=_ITEMS, deterministic_reply="d")

        self.server.next_status = 500
        self.server.next_body = {"error": "boom"}
        RecommendationExplainer(verify=False).explain(items=_ITEMS, deterministic_reply="d")

        stats = generation_stats()
        self.assertEqual(stats["llm"], 1)
        self.assertEqual(stats["fallback"], 1)


class TestDs4Streaming(unittest.TestCase):
    """SSE streaming transport (WEB_AGENT_DS4_STREAM=1)."""

    def setUp(self) -> None:
        self.server = _MockServer(("127.0.0.1", 0))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self._env = mock.patch.dict(
            "os.environ",
            {
                "WEB_AGENT_DS4_BASE_URL": f"http://127.0.0.1:{self.port}",
                "WEB_AGENT_DS4_STREAM": "1",
                "WEB_AGENT_GENERATION_DISABLED": "",
                "WEB_AGENT_OPENAI_BASE_URL": "",
                "OPENAI_BASE_URL": "",
            },
            clear=False,
        )
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        self.server.shutdown()
        self.server.server_close()

    def _prompt(self) -> PromptPayload:
        return PromptPayload(
            system_instruction="sys",
            user_message="hi",
            context_block="evidence",
            response_constraints=["be honest"],
        )

    def test_stream_flag_is_advertised(self) -> None:
        status = WebResponseGenerator().inspect_provider_status()
        self.assertTrue(status["stream"])
        self.assertEqual(status["providerLabel"], "ds4")

    def test_streamed_deltas_accumulate_and_invoke_on_delta(self) -> None:
        self.server.next_sse = [
            json.dumps({"choices": [{"delta": {"role": "assistant"}}]}),
            json.dumps({"choices": [{"delta": {"content": "Hello "}}]}),
            json.dumps({"choices": [{"delta": {"content": "world"}}]}),
            "[DONE]",
        ]
        seen: list[str] = []

        result = WebResponseGenerator().generate_response(
            prompt=self._prompt(),
            fallback_text="Rule-based reply.",
            on_delta=seen.append,
        )

        self.assertEqual(result.source, "llm")
        self.assertEqual(result.reply_text, "Hello world")
        self.assertEqual(seen, ["Hello ", "world"])
        # The request actually asked for streaming.
        self.assertTrue(self.server.requests[0]["body"]["stream"])

    def test_finish_reason_terminates_without_done_sentinel(self) -> None:
        self.server.next_sse = [
            json.dumps({"choices": [{"delta": {"content": "Complete."}, "finish_reason": "stop"}]}),
        ]
        result = WebResponseGenerator().generate_response(
            prompt=self._prompt(), fallback_text="Rule-based reply."
        )
        self.assertEqual(result.source, "llm")
        self.assertEqual(result.reply_text, "Complete.")

    def test_truncated_stream_falls_back_instead_of_returning_partial_text(self) -> None:
        # No [DONE] and no finish_reason: the reply is incomplete, so returning
        # it could silently drop the caveats the honesty contract requires.
        self.server.next_sse = [
            json.dumps({"choices": [{"delta": {"content": "Partial answer that never"}}]}),
        ]
        result = WebResponseGenerator().generate_response(
            prompt=self._prompt(), fallback_text="Rule-based reply."
        )
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.reply_text, "Rule-based reply.")
        self.assertIn("ended before completion", result.warning or "")

    def test_non_streaming_server_response_still_parses(self) -> None:
        # Server ignores stream:true and answers with plain JSON.
        self.server.next_sse = None
        self.server.next_body = {"choices": [{"message": {"content": "PLAIN JSON REPLY"}}]}

        result = WebResponseGenerator().generate_response(
            prompt=self._prompt(), fallback_text="Rule-based reply."
        )
        self.assertEqual(result.source, "llm")
        self.assertEqual(result.reply_text, "PLAIN JSON REPLY")


if __name__ == "__main__":
    unittest.main()
