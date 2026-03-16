import requests
import pytest

urls = [
    "https://www.topuniversities.com/europe-university-rankings",
    "https://www.topuniversities.com/latin-america-caribbean-rankings",
    "https://www.topuniversities.com/asia-university-rankings",
    "https://www.topuniversities.com/sub-saharan-africa-university-rankings",
]

headers = {"User-Agent": "Mozilla/5.0"}

@pytest.mark.parametrize("url", urls)
def test_region_pages_accessible(url):
    """Ensure each regional ranking page returns HTTP 200."""
    response = requests.get(url, headers=headers, timeout=5)
    assert response.status_code == 200
