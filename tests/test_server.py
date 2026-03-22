"""Integration test: verify the content-dlp HTTP server is running on port 7055."""

from pathlib import Path

import pytest
import requests

SERVER_URL = "http://localhost:7055"
PAGE_URL = "https://azathought.com/community-gaming/"
VIDEO_URL = "https://www.youtube.com/watch?v=yLUKVHH3X8I"
CONTENT_ID = "yt_yLUKVHH3X8I"


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


class TestServerTranscribe:

    @pytest.fixture(scope="class")
    def audio_file_path(self, server_available):
        """Ensure audio exists by fetching via /youtube, return the audio file path."""
        resp = requests.post(
            f"{SERVER_URL}/youtube",
            json={"url": VIDEO_URL},
            timeout=600,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Resolve audio path from server's download dir
        from content_dlp.config import load_config
        download_dir = Path(load_config()["download_dir"])
        audio_path = download_dir / data["content_id"] / data["audio_file"]
        assert audio_path.exists(), f"Audio file not found: {audio_path}"
        return str(audio_path)

    def test_transcribe_returns_valid_json(self, server_available, audio_file_path):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"file_path": audio_file_path},
            timeout=600,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_transcribe_has_text(self, server_available, audio_file_path):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"file_path": audio_file_path},
            timeout=600,
        )
        data = resp.json()
        assert isinstance(data["text"], str)
        assert len(data["text"]) > 0

    def test_transcribe_has_chunks(self, server_available, audio_file_path):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"file_path": audio_file_path},
            timeout=600,
        )
        data = resp.json()
        assert isinstance(data["chunks"], list)
        assert len(data["chunks"]) > 0
        for chunk in data["chunks"]:
            assert "text" in chunk
            assert "start" in chunk
            assert "end" in chunk

    def test_transcribe_has_model(self, server_available, audio_file_path):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"file_path": audio_file_path},
            timeout=600,
        )
        data = resp.json()
        assert data["model"] == "nvidia/parakeet-tdt-0.6b-v3"

    def test_transcribe_missing_file_returns_error(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"file_path": "/nonexistent/audio.mp3"},
            timeout=30,
        )
        assert resp.status_code in (400, 500)
        assert "error" in resp.json()

    def test_transcribe_missing_both_returns_400(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={},
            timeout=30,
        )
        assert resp.status_code == 400
        assert "error" in resp.json()


class TestServerTranscribeAudioUrl:

    @pytest.fixture(scope="class")
    def audio_url(self, server_available):
        """Get a real audio URL from the podcast endpoint."""
        resp = requests.post(
            f"{SERVER_URL}/podcast",
            json={"url": "https://feeds.npr.org/510289/podcast.xml", "no_audio": True},
            timeout=120,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        url = data[0]["extras"].get("enclosure_url")
        assert url, "No enclosure_url in podcast episode"
        return url

    def test_transcribe_audio_url_returns_valid_json(self, server_available, audio_url):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"audio_url": audio_url, "force": True},
            timeout=600,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_transcribe_audio_url_has_text(self, server_available, audio_url):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"audio_url": audio_url},
            timeout=600,
        )
        data = resp.json()
        assert isinstance(data["text"], str)
        assert len(data["text"]) > 0

    def test_transcribe_audio_url_has_chunks(self, server_available, audio_url):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"audio_url": audio_url},
            timeout=600,
        )
        data = resp.json()
        assert isinstance(data["chunks"], list)
        assert len(data["chunks"]) > 0

    def test_transcribe_audio_url_has_model(self, server_available, audio_url):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"audio_url": audio_url},
            timeout=600,
        )
        data = resp.json()
        assert data["model"] == "nvidia/parakeet-tdt-0.6b-v3"

    def test_transcribe_bad_url_returns_error(self, server_available):
        resp = requests.post(
            f"{SERVER_URL}/transcribe",
            json={"audio_url": "https://example.com/nonexistent.mp3"},
            timeout=30,
        )
        assert resp.status_code in (400, 500)
        assert "error" in resp.json()
