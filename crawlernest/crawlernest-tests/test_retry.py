"""Tests for the retry decorator in crawlernest-core/utils/retry.py.

Covers:
- Successful function needs no retry
- Function that fails once then succeeds
- Function that always fails exhausts max_attempts and re-raises
- Exponential backoff: delay doubles after each failure
- Custom exception types: only specified exceptions are caught
- log_attempt_failures / log_final_failure flags
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

for mod in ("crawlernest-core",):
    p = str(PACKAGE_ROOT / mod)
    if p not in sys.path:
        sys.path.insert(0, p)

from utils.retry import retry


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

class TestRetryBasic(unittest.TestCase):
    def test_success_on_first_attempt(self):
        call_count = [0]

        @retry(max_attempts=3, delay=0)
        def succeed():
            call_count[0] += 1
            return "ok"

        result = succeed()
        self.assertEqual(result, "ok")
        self.assertEqual(call_count[0], 1)

    def test_success_after_one_failure(self):
        call_count = [0]

        @retry(max_attempts=3, delay=0)
        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("transient")
            return "recovered"

        result = flaky()
        self.assertEqual(result, "recovered")
        self.assertEqual(call_count[0], 2)

    def test_exhausted_attempts_reraises(self):
        call_count = [0]

        @retry(max_attempts=3, delay=0)
        def always_fail():
            call_count[0] += 1
            raise ValueError("permanent")

        with self.assertRaises(ValueError):
            always_fail()
        self.assertEqual(call_count[0], 3)

    def test_return_value_preserved(self):
        @retry(max_attempts=2, delay=0)
        def give_42():
            return 42

        self.assertEqual(give_42(), 42)


# ---------------------------------------------------------------------------
# Backoff timing
# ---------------------------------------------------------------------------

class TestRetryBackoff(unittest.TestCase):
    def test_exponential_backoff_sleep_calls(self):
        """Verify that time.sleep is called with increasing delays."""
        call_count = [0]
        sleep_calls = []

        @retry(max_attempts=3, delay=1.0, backoff=2.0)
        def always_fail():
            call_count[0] += 1
            raise RuntimeError("fail")

        with patch("utils.retry.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with self.assertRaises(RuntimeError):
                always_fail()

        # Should have slept twice (after attempt 1 and 2; not after final attempt)
        self.assertEqual(len(sleep_calls), 2)
        self.assertAlmostEqual(sleep_calls[0], 1.0)
        self.assertAlmostEqual(sleep_calls[1], 2.0)

    def test_zero_delay_does_not_sleep(self):
        sleep_calls = []

        @retry(max_attempts=3, delay=0.0, backoff=2.0)
        def always_fail():
            raise RuntimeError("fail")

        with patch("utils.retry.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            with self.assertRaises(RuntimeError):
                always_fail()

        # delay=0 → sleep(0) still called but irrelevant; the key is no blocking
        # Some implementations skip sleep entirely when delay <= 0; accept either
        for s in sleep_calls:
            self.assertEqual(s, 0.0)


# ---------------------------------------------------------------------------
# Custom exception filtering
# ---------------------------------------------------------------------------

class TestRetryExceptionFilter(unittest.TestCase):
    def test_only_specified_exceptions_are_caught(self):
        call_count = [0]

        @retry(max_attempts=3, delay=0, exceptions=(ValueError,))
        def wrong_exc():
            call_count[0] += 1
            raise TypeError("unexpected")

        with self.assertRaises(TypeError):
            wrong_exc()
        # Should have called once then propagated (TypeError not in exceptions)
        self.assertEqual(call_count[0], 1)

    def test_specified_exception_is_retried(self):
        call_count = [0]

        @retry(max_attempts=3, delay=0, exceptions=(ValueError,))
        def right_exc():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("retryable")
            return "done"

        result = right_exc()
        self.assertEqual(result, "done")
        self.assertEqual(call_count[0], 3)

    def test_multiple_exception_types(self):
        call_count = [0]

        @retry(max_attempts=4, delay=0, exceptions=(ValueError, OSError))
        def alternating():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("val")
            if call_count[0] == 2:
                raise OSError("os")
            return "ok"

        result = alternating()
        self.assertEqual(result, "ok")
        self.assertEqual(call_count[0], 3)


# ---------------------------------------------------------------------------
# Logging flags
# ---------------------------------------------------------------------------

class TestRetryLogging(unittest.TestCase):
    def test_log_attempt_failures_false_suppresses_warnings(self):
        """log_attempt_failures=False should not call logger.warning."""
        @retry(max_attempts=2, delay=0, log_attempt_failures=False)
        def fail_once():
            raise RuntimeError("x")

        with patch("utils.retry.logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            with self.assertRaises(RuntimeError):
                fail_once()
            mock_logger.warning.assert_not_called()

    def test_log_final_failure_false_suppresses_error(self):
        """log_final_failure=False should not call logger.error."""
        @retry(max_attempts=1, delay=0, log_final_failure=False)
        def fail():
            raise RuntimeError("y")

        with patch("utils.retry.logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            with self.assertRaises(RuntimeError):
                fail()
            mock_logger.error.assert_not_called()


# ---------------------------------------------------------------------------
# Functools.wraps preservation
# ---------------------------------------------------------------------------

class TestRetryFunctoolsWraps(unittest.TestCase):
    def test_function_name_preserved(self):
        @retry(max_attempts=1, delay=0)
        def my_special_function():
            return True

        self.assertEqual(my_special_function.__name__, "my_special_function")

    def test_function_doc_preserved(self):
        @retry(max_attempts=1, delay=0)
        def documented():
            """I have docs."""
            return True

        self.assertEqual(documented.__doc__, "I have docs.")


if __name__ == "__main__":
    unittest.main()
