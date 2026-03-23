import os
import unittest

import requests

urls = [
    "https://www.topuniversities.com/europe-university-rankings",
    "https://www.topuniversities.com/latin-america-caribbean-rankings",
    "https://www.topuniversities.com/asia-university-rankings",
    "https://www.topuniversities.com/sub-saharan-africa-university-rankings",
]

headers = {"User-Agent": "Mozilla/5.0"}

@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_LIVE_HTTP_TESTS") == "1",
    "Live HTTP tests are opt-in",
)
class TestRegionPages(unittest.TestCase):
    def test_region_pages_accessible(self):
        """Ensure each regional ranking page returns HTTP 200."""
        for url in urls:
            with self.subTest(url=url):
                response = requests.get(url, headers=headers, timeout=5)
                self.assertEqual(response.status_code, 200)
