"""Integration test: fetch a real podcast RSS feed and validate the returned metadata."""

import json
import subprocess
import sys
from pathlib import Path

# NPR Planet Money — stable, long-running public feed
FEED_URL = "https://feeds.npr.org/510289/podcast.xml"

PYTHON = sys.executable
TEST_DOWNLOAD_DIR = Path(__file__).parent / "test_output"



def run_cli(*args: str, timeout: int = 120) -> list[dict]:
    """Run content-dlp podcast and return parsed JSON output (always a list)."""
    result = subprocess.run(
        [PYTHON, "-m", "content_dlp", "--download-dir", str(TEST_DOWNLOAD_DIR), *args],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
        timeout=timeout,
    )
    assert result.returncode == 0, f"CLI failed:\nstderr: {result.stderr}\nstdout: {result.stdout}"
    return json.loads(result.stdout)


class TestPodcastMetadata:
    """Test metadata fetching (no audio download)."""

    def test_fetch_returns_valid_json_array(self):
        data = run_cli("podcast", "--no-audio", FEED_URL)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_array_length_matches_episodes_flag(self):
        data = run_cli("podcast", "--no-audio", "--episodes", "3", FEED_URL)
        assert len(data) == 3

    def test_content_id_prefix(self):
        data = run_cli("podcast", "--no-audio", FEED_URL)
        assert data[0]["content_id"].startswith("pod_")

    def test_source_type(self):
        data = run_cli("podcast", "--no-audio", FEED_URL)
        assert data[0]["source_type"] == "podcast"

    def test_title_present(self):
        data = run_cli("podcast", "--no-audio", FEED_URL)
        assert data[0]["title"] and len(data[0]["title"]) > 0

    def test_published_date_is_iso(self):
        from datetime import datetime

        data = run_cli("podcast", "--no-audio", FEED_URL)
        datetime.fromisoformat(data[0]["published_date"])

    def test_duration_positive(self):
        data = run_cli("podcast", "--no-audio", FEED_URL)
        assert isinstance(data[0]["duration_seconds"], int)
        assert data[0]["duration_seconds"] > 0

    def test_extras_contain_feed_title(self):
        data = run_cli("podcast", "--no-audio", FEED_URL)
        assert "feed_title" in data[0]["extras"]
        assert len(data[0]["extras"]["feed_title"]) > 0

    def test_extras_contain_enclosure_url(self):
        data = run_cli("podcast", "--no-audio", FEED_URL)
        assert "enclosure_url" in data[0]["extras"]
        assert data[0]["extras"]["enclosure_url"].startswith("http")

    def test_content_folder_created(self):
        data = run_cli("podcast", "--no-audio", FEED_URL)
        folder = TEST_DOWNLOAD_DIR / data[0]["content_id"]
        assert folder.is_dir()
        assert (folder / "metadata.json").exists()
        assert (folder / "source_metadata.json").exists()

    def test_cache_returns_same_data(self):
        first = run_cli("podcast", "--no-audio", FEED_URL)
        second = run_cli("podcast", "--no-audio", FEED_URL)
        assert first[0]["content_id"] == second[0]["content_id"]
        assert first[0]["title"] == second[0]["title"]

    def test_force_bypasses_cache(self):
        first = run_cli("podcast", "--no-audio", FEED_URL)
        forced = run_cli("podcast", "--no-audio", "--force", FEED_URL)
        assert forced[0]["content_id"] == first[0]["content_id"]
        assert forced[0]["fetched_at"] != first[0]["fetched_at"]


class TestPodcastAudio:
    """Test audio download (default behavior)."""

    def test_audio_file_downloaded(self):
        data = run_cli("podcast", FEED_URL)
        folder = TEST_DOWNLOAD_DIR / data[0]["content_id"]
        audio_files = list(folder.glob("audio.*"))
        assert len(audio_files) == 1, f"Expected 1 audio file, found: {audio_files}"

    def test_audio_file_has_content(self):
        data = run_cli("podcast", FEED_URL)
        folder = TEST_DOWNLOAD_DIR / data[0]["content_id"]
        audio_files = list(folder.glob("audio.*"))
        assert audio_files[0].stat().st_size > 1000, "Audio file is suspiciously small"

    def test_audio_file_name_in_output(self):
        data = run_cli("podcast", FEED_URL)
        assert "audio_file" in data[0]
        assert data[0]["audio_file"].startswith("audio.")

    def test_audio_cached_on_second_run(self):
        data = run_cli("podcast", FEED_URL)
        folder = TEST_DOWNLOAD_DIR / data[0]["content_id"]
        audio_files = list(folder.glob("audio.*"))
        first_mtime = audio_files[0].stat().st_mtime
        # Second run should reuse cached audio
        run_cli("podcast", FEED_URL)
        assert audio_files[0].stat().st_mtime == first_mtime


class TestPodcastTranscript:
    """Test transcript generation via whisper service."""

    def test_transcript_in_output(self):
        data = run_cli("podcast", "--transcript", FEED_URL, timeout=900)
        assert "transcript" in data[0]
        assert "text" in data[0]["transcript"]
        assert len(data[0]["transcript"]["text"]) > 100

    def test_transcript_cached_on_second_run(self):
        data = run_cli("podcast", "--transcript", FEED_URL, timeout=900)
        folder = TEST_DOWNLOAD_DIR / data[0]["content_id"]
        assert (folder / "transcript.json").exists()
        first_mtime = (folder / "transcript.json").stat().st_mtime
        run_cli("podcast", "--transcript", FEED_URL, timeout=900)
        assert (folder / "transcript.json").stat().st_mtime == first_mtime

    def test_transcript_requires_audio(self):
        result = subprocess.run(
            [PYTHON, "-m", "content_dlp", "--download-dir", str(TEST_DOWNLOAD_DIR),
             "podcast", "--transcript", "--no-audio", FEED_URL],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
            timeout=120,
        )
        assert result.returncode != 0
