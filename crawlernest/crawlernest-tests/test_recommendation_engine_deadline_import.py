"""The recommender must be able to read deadlines when nothing else has set up the import path.

``recommendation_engine.engine`` imports ``crawlernest_admission_crawler.deadline_interpretation`` inside a ``try`` that falls
back to ``None`` on ``ImportError``. A path that is wrong therefore does not fail: the recommender stops reading deadlines and
says nothing. The packages moved from the repository root to ``crawlernest/packages/``; this runs the import in a fresh
interpreter with only ``crawlernest-core`` on the path, which is the least any caller provides, and fails if the fallback was taken.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[1] / "crawlernest-core"


class TestTheDeadlineReaderIsFound(unittest.TestCase):
    def test_a_fresh_interpreter_with_only_the_core_on_the_path_finds_it(self):
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "import recommendation_engine.engine as e;"
            "assert e.interpret_deadline_decision is not None, 'the optional import silently fell back to None';"
            "print('found')"
        )
        result = subprocess.run([sys.executable, "-c", code, str(CORE_DIR)], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertIn("found", result.stdout)


if __name__ == "__main__":
    unittest.main()
