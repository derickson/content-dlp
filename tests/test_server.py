"""Integration test: verify the content-dlp HTTP server is running on port 7055."""

import pytest
import requests

SERVER_URL = "http://localhost:7055"
PAGE_URL = "https://azathought.com/community-gaming/"


@pytest.fixture(scope="module")
def server_available():
    """Skip all tests if the server is not reachable."""
    try:
        resp = requests.get(f"{SERVER_URL}/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip("content-dlp server not healthy")
    except requests.ConnectionError:
        pytest.skip("content-dlp server not running on port 7055")


class TestServerHealth:

    def test_health_endpoint(self, server_available):
        resp = requests.get(f"{SERVER_URL}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestServerWebscrape:

    def test_webscrape_returns_valid_json(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/webscrape",
            json={"url": PAGE_URL},
            timeout=120,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_webscrape_content_id(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/webscrape",
            json={"url": PAGE_URL},
            timeout=120,
        )
        data = resp.json()
        assert data["content_id"].startswith("web_")

    def test_webscrape_source_type(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/webscrape",
            json={"url": PAGE_URL},
            timeout=120,
        )
        data = resp.json()
        assert data["source_type"] == "webscrape"

    def test_webscrape_has_title(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/webscrape",
            json={"url": PAGE_URL},
            timeout=120,
        )
        data = resp.json()
        assert data["title"] and len(data["title"]) > 0

    def test_webscrape_has_markdown(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/webscrape",
            json={"url": PAGE_URL},
            timeout=120,
        )
        data = resp.json()
        assert "markdown" in data
        assert len(data["markdown"]) > 100

    def test_webscrape_missing_url_returns_400(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/webscrape",
            json={},
            timeout=30,
        )
        assert resp.status_code in (400, 500)

    def test_webscrape_no_content(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/webscrape",
            json={"url": PAGE_URL, "no_content": True},
            timeout=120,
        )
        data = resp.json()
        assert "markdown" not in data
        assert "content_file" not in data
