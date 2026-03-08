"""Integration test: scrape a real web page and validate the returned metadata."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PAGE_URL = "https://azathought.com/community-gaming/"

PYTHON = sys.executable
TEST_DOWNLOAD_DIR = Path(__file__).parent / "test_output"


@pytest.fixture(autouse=True)
def clean_test_output():
    """Remove test output dir before each test (keep after for inspection)."""
    if TEST_DOWNLOAD_DIR.exists():
        shutil.rmtree(TEST_DOWNLOAD_DIR)
    yield


def run_cli(*args: str, timeout: int = 120) -> dict:
    """Run content-dlp and return parsed JSON output."""
    result = subprocess.run(
        [PYTHON, "-m", "content_dlp", "--download-dir", str(TEST_DOWNLOAD_DIR), *args],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
        timeout=timeout,
    )
    assert result.returncode == 0, f"CLI failed:\nstderr: {result.stderr}\nstdout: {result.stdout}"
    return json.loads(result.stdout)


class TestWebscrapeMetadata:
    """Test metadata fetching (no content save)."""

    def test_fetch_returns_valid_json(self):
        data = run_cli("webscrape", "--no-content", PAGE_URL)
        assert isinstance(data, dict)

    def test_content_id_format(self):
        data = run_cli("webscrape", "--no-content", PAGE_URL)
        assert data["content_id"].startswith("web_")
        assert len(data["content_id"]) > 5

    def test_source_type(self):
        data = run_cli("webscrape", "--no-content", PAGE_URL)
        assert data["source_type"] == "webscrape"

    def test_title(self):
        data = run_cli("webscrape", "--no-content", PAGE_URL)
        assert data["title"] and len(data["title"]) > 0

    def test_fetched_at_is_iso(self):
        from datetime import datetime

        data = run_cli("webscrape", "--no-content", PAGE_URL)
        datetime.fromisoformat(data["fetched_at"])

    def test_extras_domain(self):
        data = run_cli("webscrape", "--no-content", PAGE_URL)
        assert data["extras"]["domain"] == "azathought.com"

    def test_extras_path(self):
        data = run_cli("webscrape", "--no-content", PAGE_URL)
        assert data["extras"]["path"] == "/community-gaming/"

    def test_content_folder_created(self):
        data = run_cli("webscrape", "--no-content", PAGE_URL)
        folder = TEST_DOWNLOAD_DIR / data["content_id"]
        assert folder.is_dir()
        assert (folder / "metadata.json").exists()
        assert (folder / "source_metadata.json").exists()

    def test_cache_returns_same_data(self):
        first = run_cli("webscrape", "--no-content", PAGE_URL)
        second = run_cli("webscrape", "--no-content", PAGE_URL)
        assert first["content_id"] == second["content_id"]
        assert first["title"] == second["title"]

    def test_force_bypasses_cache(self):
        first = run_cli("webscrape", "--no-content", PAGE_URL)
        forced = run_cli("webscrape", "--no-content", "--force", PAGE_URL)
        assert forced["content_id"] == first["content_id"]
        assert forced["fetched_at"] != first["fetched_at"]


class TestWebscrapeContent:
    """Test content (markdown) saving."""

    def test_content_file_saved(self):
        data = run_cli("webscrape", PAGE_URL)
        folder = TEST_DOWNLOAD_DIR / data["content_id"]
        assert (folder / "content.md").exists()

    def test_content_file_not_empty(self):
        data = run_cli("webscrape", PAGE_URL)
        folder = TEST_DOWNLOAD_DIR / data["content_id"]
        assert (folder / "content.md").stat().st_size > 100

    def test_content_file_in_output(self):
        data = run_cli("webscrape", PAGE_URL)
        assert data["content_file"] == "content.md"

    def test_no_content_skips_file(self):
        data = run_cli("webscrape", "--no-content", PAGE_URL)
        folder = TEST_DOWNLOAD_DIR / data["content_id"]
        assert not (folder / "content.md").exists()
        assert "content_file" not in data

    def test_content_cached_on_second_run(self):
        run_cli("webscrape", PAGE_URL)
        data = run_cli("webscrape", PAGE_URL)
        folder = TEST_DOWNLOAD_DIR / data["content_id"]
        assert (folder / "content.md").exists()
