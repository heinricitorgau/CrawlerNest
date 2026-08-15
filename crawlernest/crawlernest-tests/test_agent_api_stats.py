"""The stats route, which is what makes the counters worth having.

Counting an event nobody reads is not observability. These tests cover the two
things the endpoint has to get right: the rates that make a failure legible, and
the honesty about what the numbers do not say.
"""

from __future__ import annotations

import io
import json
import logging
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from crawlernest.agent.web_agent.generation.judge import JudgeVerdict, LlmJudge
from crawlernest.agent.web_agent.generation.verification import (
    reset_judge_health,
    reset_verification_stats,
    verify_explanation,
)
from crawlernest.interfaces.api.agent_api.server import (
    _RequestHandler,
    build_stats_payload,
    configure_logging,
)

_ITEMS = [{"universityName": "National Taiwan University", "aggregatedRank": 68}]
_CAVEATS = ["Only the QS source is available; THE and ARWU ranks are null."]
_FAITHFUL = (
    "National Taiwan University sits at aggregated rank 68.\n\n"
    "Only the QS source is available; THE and ARWU ranks are null."
)
_INVENTS_A_RANK = (
    "National Taiwan University is ranked 12.\n\n"
    "Only the QS source is available; THE and ARWU ranks are null."
)


class _StubJudge(LlmJudge):
    def __init__(self, verdict: JudgeVerdict | None) -> None:
        super().__init__(base_url="http://stub", model_name="stub")
        self._verdict = verdict

    def review(self, **kwargs):  # type: ignore[override]
        return self._verdict


class TestStatsPayload(unittest.TestCase):
    def setUp(self) -> None:
        reset_verification_stats()

    def test_untouched_counters_report_none_rather_than_zero(self):
        """Zero would read as 'this never happens'; nothing has happened yet."""
        payload = build_stats_payload()
        signals = payload["signals"]

        self.assertEqual(signals["explanations_verified"], 0)
        self.assertIsNone(signals["mechanical_rejection_rate"])
        self.assertIsNone(signals["judge_flag_rate"])
        self.assertTrue(any("has not been consulted" in c for c in payload["caveats"]))

    def test_a_judge_flagging_everything_shows_as_a_rate(self):
        judge = _StubJudge(JudgeVerdict(faithful=False, reason="no", model_name="stub"))
        for _ in range(4):
            verify_explanation(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=judge)

        signals = build_stats_payload()["signals"]
        self.assertEqual(signals["judge_consulted"], 4)
        self.assertEqual(signals["judge_flag_rate"], 1.0)
        self.assertEqual(signals["judge_no_opinion_rate"], 0.0)

    def test_a_judge_gone_dark_is_called_out_in_the_caveats(self):
        """The responses look identical to a healthy run, so the text has to say it."""
        judge = _StubJudge(None)
        for _ in range(3):
            verify_explanation(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=judge)

        payload = build_stats_payload()
        self.assertEqual(payload["signals"]["judge_no_opinion_rate"], 1.0)
        self.assertTrue(any("no opinion" in c for c in payload["caveats"]))

    def test_judge_rates_are_over_consultations_not_over_explanations(self):
        """A rule violation never reaches the judge, so it must not dilute its rate."""
        judge = _StubJudge(JudgeVerdict(faithful=False, reason="no", model_name="stub"))
        verify_explanation(explanation=_INVENTS_A_RANK, items=_ITEMS, caveats=_CAVEATS, judge=judge)
        verify_explanation(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=judge)

        signals = build_stats_payload()["signals"]
        self.assertEqual(signals["explanations_verified"], 2)
        self.assertEqual(signals["mechanical_rejection_rate"], 0.5)
        self.assertEqual(signals["judge_consulted"], 1)
        self.assertEqual(signals["judge_flag_rate"], 1.0)

    def test_the_process_local_limit_is_always_disclosed(self):
        self.assertTrue(
            any("process-local" in c for c in build_stats_payload()["caveats"])
        )


class TestLoggingReachesStdout(unittest.TestCase):
    """Which stream, and at which level -- not merely that a record was emitted.

    assertLogs attaches its own handler, so it passes whether or not the process
    has one. It therefore could not catch the defect this covers: with no logging
    configured the agent API fell back to logging.lastResort, which writes to
    stderr and drops everything below WARNING, so the dark-judge warning went to
    the wrong stream and the recovery message that closes it never appeared at
    all.
    """

    def setUp(self) -> None:
        reset_verification_stats()
        reset_judge_health()
        self._saved = logging.getLogger().handlers[:]
        self._saved_level = logging.getLogger().level

    def tearDown(self) -> None:
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        for handler in self._saved:
            root.addHandler(handler)
        root.setLevel(self._saved_level)

    def test_a_warning_lands_on_the_configured_stream(self):
        stream = io.StringIO()
        configure_logging(stream=stream)
        judge = _StubJudge(None)
        for _ in range(5):
            verify_explanation(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=judge)

        self.assertIn("no opinion 5 times in a row", stream.getvalue())

    def test_the_recovery_message_survives_the_default_level(self):
        """It is logged at INFO, which lastResort would have discarded."""
        stream = io.StringIO()
        configure_logging(stream=stream)
        for _ in range(5):
            verify_explanation(
                explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=_StubJudge(None)
            )
        healthy = _StubJudge(JudgeVerdict(faithful=True, reason="ok", model_name="stub"))
        verify_explanation(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=healthy)

        self.assertIn("answering again", stream.getvalue())

    def test_a_judge_objecting_to_everything_is_reported_too(self):
        stream = io.StringIO()
        configure_logging(stream=stream)
        judge = _StubJudge(JudgeVerdict(faithful=False, reason="no", model_name="stub"))
        for _ in range(10):
            verify_explanation(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=judge)

        output = stream.getvalue()
        self.assertIn("objected to 10 explanations in a row", output)
        self.assertEqual(output.count("objected to"), 1)


class TestStatsRoute(unittest.TestCase):
    """Served over HTTP, not just constructed in-process."""

    def setUp(self) -> None:
        reset_verification_stats()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _RequestHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def _get(self, path: str):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_the_route_serves_the_counters(self):
        verify_explanation(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS)

        status, payload = self._get("/api/v1/agent/stats")
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["verification"]["keep"], 1)
        self.assertIn("generation", payload)
        self.assertTrue(payload["caveats"])

    def test_unknown_routes_still_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._get("/api/v1/agent/nope")
        self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
