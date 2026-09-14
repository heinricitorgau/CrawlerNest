"""The explain route's ``text/event-stream`` transport, over a real socket.

The one property worth protecting here is that the two transports say the same
thing. A reader that joins every delta must end up with exactly the string the
JSON route would have returned; if they can differ, the page shows one answer
and the API reports another, and only one of them was verified.

The second is what is *not* streamed. ``verify_explanation`` runs after
generation and can replace the model's answer with the deterministic one --
that is the check that catches a fabricated figure or a dropped caveat. So the
stream carries the verified text, and carries no deltas at all when the answer
came back as the fallback. A test that only asserted "deltas arrived" would
pass on an implementation that streamed the rejected text.
"""

from __future__ import annotations

import json
import sys
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_api_live_server import LiveAgentApi  # noqa: E402
from crawlernest.interfaces.api.agent_api.app import create_app  # noqa: E402
from crawlernest.interfaces.api.agent_api.server import _split_for_stream  # noqa: E402

_ITEMS = [
    {
        "universityName": "National Taiwan University",
        "country": "Taiwan",
        "aggregatedRank": 68,
    }
]

_EXPLANATION = (
    "National Taiwan University sits at aggregated rank 68 in the 2026 table. "
    "Only QS ranks it here, so the absence of a THE rank is this platform's gap."
)


def _explain_response(*, source: str, explanation: str = _EXPLANATION, warning=None):
    """Stand in for AgentApiHandler.handle_explain with a fixed verdict."""

    def _handler(payload):
        return 200, {
            "success": True,
            "data": {
                "taskKind": "recommendation",
                "explanation": explanation,
                "paragraphs": [explanation],
                "source": source,
                "modelName": "deepseek-v4-flash" if source == "llm" else None,
                "warning": warning,
            },
        }

    return _handler


class TestSplitForStream(unittest.TestCase):
    """Chunking is only correct if rejoining is lossless."""

    def test_chunks_rejoin_to_the_original_exactly(self) -> None:
        for text in (
            _EXPLANATION,
            "one",
            "  leading and trailing  ",
            "double  spaces\nand\n\nnewlines",
            "",
        ):
            with self.subTest(text=text[:24]):
                self.assertEqual("".join(_split_for_stream(text)), text)

    def test_a_long_unbroken_run_is_still_split(self) -> None:
        # CJK has no spaces to split on. Slicing is by code point, so a chunk
        # boundary cannot land inside a character -- a byte-level split would.
        text = "臺灣大學在二〇二六年的綜合排名為第六十八名並且只有一個來源收錄它" * 3
        chunks = _split_for_stream(text, chunk_chars=8)

        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c) <= 8 for c in chunks))
        self.assertGreater(len(chunks), 1)

    def test_empty_text_produces_no_frames(self) -> None:
        self.assertEqual(_split_for_stream(""), [])


class _StubApiHandler:
    """Stands in for AgentApiHandler; each test patches handle_explain."""

    def handle_explain(self, payload):  # pragma: no cover - always patched
        raise AssertionError("handle_explain was not patched")

    def handle_task(self, payload):  # pragma: no cover
        raise AssertionError("handle_task was not patched")


class _StubGenerator:
    def inspect_provider_status(self):
        return {"configured": False}


class _StreamTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.api_handler = _StubApiHandler()
        app = create_app(
            api_handler=self.api_handler,
            response_generator=_StubGenerator(),
            configure_process_logging=False,
        )
        self.server = LiveAgentApi(app)
        self.server.start()
        self.port = self.server.port

    def tearDown(self) -> None:
        self.server.stop()

    def _post(self, *, accept: str) -> tuple[str, list]:
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/v1/agent/explain",
            data=json.dumps({"taskKind": "recommendation", "items": _ITEMS}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": accept},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read().decode("utf-8")
        return content_type, raw

    @staticmethod
    def _frames(raw: str) -> list:
        """Parse `data:` frames; JSON where possible, raw for the sentinel."""
        out = []
        for line in raw.splitlines():
            if not line.startswith("data:"):
                continue
            body = line[len("data:") :].strip()
            try:
                out.append(json.loads(body))
            except ValueError:
                out.append(body)
        return out


class TestExplainStreamsWhenAsked(_StreamTestCase):
    def test_accept_header_selects_the_event_stream(self) -> None:
        with mock.patch.object(
            self.api_handler, "handle_explain", _explain_response(source="llm")
        ):
            content_type, raw = self._post(accept="text/event-stream")

        self.assertIn("text/event-stream", content_type)
        frames = self._frames(raw)
        self.assertEqual(frames[0], {"type": "status", "phase": "generating"})
        self.assertEqual(frames[-1], "[DONE]")

    def test_deltas_rejoin_to_the_verified_explanation(self) -> None:
        with mock.patch.object(
            self.api_handler, "handle_explain", _explain_response(source="llm")
        ):
            _, raw = self._post(accept="text/event-stream")

        frames = self._frames(raw)
        deltas = [f["text"] for f in frames if isinstance(f, dict) and f.get("type") == "delta"]

        self.assertGreater(len(deltas), 1, "a multi-sentence answer should arrive in pieces")
        self.assertEqual("".join(deltas), _EXPLANATION)

    def test_done_frame_carries_the_metadata_the_page_needs(self) -> None:
        with mock.patch.object(
            self.api_handler,
            "handle_explain",
            _explain_response(source="llm", warning="Judge flagged one clause."),
        ):
            _, raw = self._post(accept="text/event-stream")

        done = [
            f for f in self._frames(raw) if isinstance(f, dict) and f.get("type") == "done"
        ][0]

        self.assertTrue(done["success"])
        self.assertEqual(done["source"], "llm")
        self.assertEqual(done["modelName"], "deepseek-v4-flash")
        self.assertEqual(done["warning"], "Judge flagged one clause.")
        self.assertEqual(done["explanation"], _EXPLANATION)
        self.assertEqual(done["taskKind"], "recommendation")

    def test_fallback_answers_stream_no_deltas(self) -> None:
        # The deterministic reply is not model prose and the page does not show
        # it. Streaming it would put text on screen that the JSON route hides.
        with mock.patch.object(
            self.api_handler,
            "handle_explain",
            _explain_response(source="fallback", warning="Generation failed."),
        ):
            _, raw = self._post(accept="text/event-stream")

        frames = self._frames(raw)
        deltas = [f for f in frames if isinstance(f, dict) and f.get("type") == "delta"]
        done = [f for f in frames if isinstance(f, dict) and f.get("type") == "done"][0]

        self.assertEqual(deltas, [])
        self.assertEqual(done["source"], "fallback")
        self.assertEqual(frames[-1], "[DONE]")


class TestJsonRouteIsUnchanged(_StreamTestCase):
    def test_without_the_accept_header_the_route_still_answers_json(self) -> None:
        with mock.patch.object(
            self.api_handler, "handle_explain", _explain_response(source="llm")
        ):
            content_type, raw = self._post(accept="application/json")

        self.assertIn("application/json", content_type)
        body = json.loads(raw)
        self.assertEqual(body["data"]["explanation"], _EXPLANATION)

    def test_both_transports_return_the_same_text(self) -> None:
        # The property the whole design rests on: one verified answer, two ways
        # of reading it. If these can differ, one of them is unverified.
        with mock.patch.object(
            self.api_handler, "handle_explain", _explain_response(source="llm")
        ):
            _, json_raw = self._post(accept="application/json")
            _, sse_raw = self._post(accept="text/event-stream")

        from_json = json.loads(json_raw)["data"]["explanation"]
        deltas = [
            f["text"]
            for f in self._frames(sse_raw)
            if isinstance(f, dict) and f.get("type") == "delta"
        ]

        self.assertEqual("".join(deltas), from_json)


if __name__ == "__main__":
    unittest.main()
