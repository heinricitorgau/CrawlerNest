import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = REPO_ROOT / "crawlernest-jobs"
if str(JOBS_DIR) not in sys.path:
    sys.path.insert(0, str(JOBS_DIR))

from qs_universe_registry import QS_GLOBAL, get_qs_universe_spec


class TestQSUniverseRegistry(unittest.TestCase):
    def test_global_spec_uses_world_ranking_type(self):
        self.assertEqual(QS_GLOBAL.ranking_type, "world")

    def test_region_spec_uses_derived_ranking_type(self):
        spec = get_qs_universe_spec("region", "europe")
        self.assertEqual(spec.universe_type, "region")
        self.assertEqual(spec.universe_key, "europe")
        self.assertEqual(spec.ranking_type, "region:europe")

    def test_subject_spec_resolves_its_edition_from_a_page_not_a_pin(self):
        spec = get_qs_universe_spec("subject", "computer-science")
        self.assertIsNone(spec.ranking_id)
        self.assertTrue(spec.ranking_page_url.endswith("/computer-science-information-systems"))


if __name__ == "__main__":
    unittest.main()
