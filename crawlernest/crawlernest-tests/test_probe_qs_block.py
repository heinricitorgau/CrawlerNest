"""Tests for the QS block probe's verdict logic.

The verdict is the probe's only real output -- everything else is raw evidence.
Its first version judged each variant solely by its final step, so a variant that
walked straight through Cloudflare and then hit a 404 on a dead ranking id was
recorded as "did not get through". Against the real endpoint that produced the
exactly wrong recommendation: "Cloudflare is serving a JS interstitial, reach for
Playwright", when curl_cffi had in fact been served no challenge at all and the
404 was an unrelated origin-side problem.

These tests pin the distinction that mistake turned on: reaching the origin and
getting the data are two different results.
"""

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from probe_qs_block import (  # noqa: E402
    StepResult,
    VariantResult,
    _cleared_cloudflare,
    _verdict,
)


def step(
    label="ranking_api",
    status=200,
    classification="live_ok",
    block_reason="",
    content_type="application/json",
):
    return StepResult(
        label=label,
        url="https://www.topuniversities.com/x",
        status=status,
        elapsed_ms=10,
        classification=classification,
        block_reason=block_reason,
        evidence={"status": status, "headers": {"content-type": content_type}},
    )


def variant(name, *steps, skipped=""):
    v = VariantResult(name=name, description=name, skipped=skipped)
    v.steps.extend(steps)
    return v


CF_CHALLENGE = step(
    status=403,
    classification="upstream_blocked",
    block_reason="cf_js_challenge",
    content_type="text/html; charset=UTF-8",
)
WAF_DENY = step(
    status=403,
    classification="upstream_blocked",
    block_reason="cf_waf_deny",
    content_type="text/html; charset=UTF-8",
)
ORIGIN_DENY = step(
    status=403,
    classification="upstream_blocked",
    block_reason="origin_deny",
    content_type="text/html; charset=UTF-8",
)
OK_PAGE = step(label="warmup_html_page")
# A 404 behind Cloudflare: reached the origin, but the ranking id is dead.
# _classify_qs_http_response now calls this fetch_failed. It used to call it
# upstream_blocked, and artifacts recorded before that fix still carry the old
# label -- which --replay will happily load -- so the verdict must key on
# block_reason and not on the coarse classification.
API_404 = step(
    status=404,
    classification="fetch_failed",
    block_reason="",
    content_type="text/html; charset=UTF-8",
)
API_404_LEGACY_LABEL = step(
    status=404,
    classification="upstream_blocked",
    block_reason="",
    content_type="text/html; charset=UTF-8",
)


def joined(lines):
    return " ".join(lines)


class TestClearedCloudflare(unittest.TestCase):
    def test_a_variant_that_ends_on_404_still_cleared_cloudflare(self):
        """The regression. Its final step failed; it still reached the origin."""
        v = variant("curl_cffi", OK_PAGE, API_404)
        self.assertFalse(v.succeeded)
        self.assertTrue(_cleared_cloudflare(v))

    def test_a_challenged_variant_did_not_clear(self):
        self.assertFalse(_cleared_cloudflare(variant("baseline", CF_CHALLENGE)))

    def test_waf_deny_did_not_clear(self):
        self.assertFalse(_cleared_cloudflare(variant("baseline", WAF_DENY)))

    def test_a_transport_error_is_not_a_clearance(self):
        errored = StepResult(label="ranking_api", url="https://x", status=None, error="ConnectionError: boom")
        self.assertFalse(_cleared_cloudflare(variant("baseline", errored)))


class TestVerdictOnTheRealObservation(unittest.TestCase):
    """The exact shape of the 2026-08 probe against topuniversities.com."""

    def setUp(self):
        self.variants = [
            variant("baseline", CF_CHALLENGE),
            variant("clean_ua", CF_CHALLENGE),
            variant("warm_cookie", CF_CHALLENGE, CF_CHALLENGE),
            variant("clean_ua_warm", CF_CHALLENGE, CF_CHALLENGE),
            variant("curl_cffi", OK_PAGE, API_404),
        ]
        self.text = joined(_verdict(self.variants))

    def test_it_confirms_phase_2(self):
        self.assertIn("PHASE 2", self.text)

    def test_it_explicitly_rules_out_phase_3(self):
        self.assertIn("Phase 3 (Playwright) is NOT needed", self.text)

    def test_it_names_curl_cffi_as_the_one_that_cleared(self):
        self.assertIn("Cloudflare was cleared by: curl_cffi", self.text)

    def test_it_reports_the_404_as_a_separate_problem(self):
        self.assertIn("SEPARATE PROBLEM", self.text)
        self.assertIn("404", self.text)
        self.assertIn("ranking id", self.text)

    def test_it_does_not_recommend_playwright(self):
        self.assertNotIn("Playwright challenge-solver", self.text)

    def test_a_replayed_pre_fix_artifact_reaches_the_same_verdict(self):
        """--replay must survive the classification change it post-dates.

        Evidence captured before _is_cf_challenge_signal stopped calling every
        >=400-with-a-cf-ray a challenge carries classification="upstream_blocked"
        on that 404. The verdict keys on block_reason, which was empty then and
        is empty now, so the conclusion has to be identical.
        """
        legacy = [
            variant("baseline", CF_CHALLENGE),
            variant("clean_ua", CF_CHALLENGE),
            variant("warm_cookie", CF_CHALLENGE, CF_CHALLENGE),
            variant("clean_ua_warm", CF_CHALLENGE, CF_CHALLENGE),
            variant("curl_cffi", OK_PAGE, API_404_LEGACY_LABEL),
        ]
        self.assertEqual(_verdict(legacy), _verdict(self.variants))


class TestVerdictOtherOutcomes(unittest.TestCase):
    def test_everything_blocked_including_curl_cffi_points_at_playwright(self):
        text = joined(
            _verdict([variant("baseline", CF_CHALLENGE), variant("curl_cffi", CF_CHALLENGE)])
        )
        self.assertIn("Phase 3 applies", text)

    def test_challenge_with_curl_cffi_skipped_does_not_jump_to_playwright(self):
        text = joined(
            _verdict(
                [
                    variant("baseline", CF_CHALLENGE),
                    variant("curl_cffi", skipped="curl_cffi not installed."),
                ]
            )
        )
        self.assertIn("did NOT run", text)
        self.assertNotIn("Phase 3 applies", text)

    def test_a_no_dependency_variant_clearing_means_phase_1_is_enough(self):
        text = joined(
            _verdict(
                [
                    variant("baseline", CF_CHALLENGE),
                    variant("clean_ua_warm", OK_PAGE, step()),
                    variant("curl_cffi", CF_CHALLENGE),
                ]
            )
        )
        self.assertIn("Phase 1", text)
        self.assertIn("Do NOT introduce curl_cffi or Playwright", text)

    def test_origin_deny_everywhere_says_it_is_not_cloudflare(self):
        text = joined(_verdict([variant("baseline", ORIGIN_DENY), variant("clean_ua", ORIGIN_DENY)]))
        self.assertIn("No Cloudflare header", text)
        self.assertIn("Client impersonation would change nothing", text)

    def test_rate_limited_says_slow_down(self):
        rate_limited = step(
            status=429,
            classification="upstream_blocked",
            block_reason="cf_rate_limited",
            content_type="text/html",
        )
        text = joined(_verdict([variant("baseline", rate_limited)]))
        self.assertIn("Rate limited", text)
        self.assertNotIn("PHASE 2", text)

    def test_baseline_succeeding_warns_the_block_is_not_reproducible(self):
        text = joined(_verdict([variant("baseline", step()), variant("clean_ua", step())]))
        self.assertIn("NOT reproducible", text)

    def test_no_variant_ran(self):
        text = joined(_verdict([variant("curl_cffi", skipped="not installed")]))
        self.assertIn("Nothing can be concluded", text)


if __name__ == "__main__":
    unittest.main()
