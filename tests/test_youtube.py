"""Integration test: fetch a real YouTube video and validate the returned metadata."""

import json
import subprocess
import sys
from pathlib import Path

VIDEO_URL = "https://www.youtube.com/watch?v=yLUKVHH3X8I"
EXPECTED = {
    "content_id": "yt_yLUKVHH3X8I",
    "source_type": "youtube",
    "url": "https://www.youtube.com/watch?v=yLUKVHH3X8I",
    "title": "Community, Content, & Kitbashing",
    "author": "azathought",
    "published_date": "2021-03-03",
    "channel_id": "UCR09Pp2HUKR2GtKT6WgwlzA",
}

PYTHON = sys.executable
TEST_DOWNLOAD_DIR = Path(__file__).parent / "test_output"



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


class TestYouTubeMetadata:
    """Test metadata fetching (no audio download)."""

    def test_fetch_returns_valid_json(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert isinstance(data, dict)

    def test_content_id(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["content_id"] == EXPECTED["content_id"]

    def test_source_type(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["source_type"] == EXPECTED["source_type"]

    def test_url(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["url"] == EXPECTED["url"]

    def test_title(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["title"] == EXPECTED["title"]

    def test_author(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["author"] == EXPECTED["author"]

    def test_published_date(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["published_date"] == EXPECTED["published_date"]

    def test_duration_is_positive(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert isinstance(data["duration_seconds"], int)
        assert data["duration_seconds"] > 0

    def test_description_not_empty(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["description"] and len(data["description"]) > 0

    def test_fetched_at_is_iso(self):
        from datetime import datetime

        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        datetime.fromisoformat(data["fetched_at"])

    def test_extras_channel_id(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["extras"]["channel_id"] == EXPECTED["channel_id"]

    def test_thumbnail_url_present(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert data["thumbnail_url"] and data["thumbnail_url"].startswith("http")

    def test_content_folder_created(self):
        run_cli("youtube", "--no-audio", VIDEO_URL)
        folder = TEST_DOWNLOAD_DIR / EXPECTED["content_id"]
        assert folder.is_dir()
        assert (folder / "metadata.json").exists()
        assert (folder / "source_metadata.json").exists()

    def test_no_audio_flag_skips_download(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert "audio_file" not in data

    def test_cache_returns_same_data(self):
        first = run_cli("youtube", "--no-audio", VIDEO_URL)
        second = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert first["content_id"] == second["content_id"]
        assert first["title"] == second["title"]

    def test_force_bypasses_cache(self):
        first = run_cli("youtube", "--no-audio", VIDEO_URL)
        forced = run_cli("youtube", "--no-audio", "--force", VIDEO_URL)
        assert forced["content_id"] == first["content_id"]
        assert forced["fetched_at"] != first["fetched_at"]


class TestYouTubeAudio:
    """Test audio download (default behavior)."""

    def test_audio_file_downloaded(self):
        data = run_cli("youtube", VIDEO_URL)
        folder = TEST_DOWNLOAD_DIR / EXPECTED["content_id"]
        audio_files = list(folder.glob("audio.*"))
        assert len(audio_files) == 1, f"Expected 1 audio file, found: {audio_files}"

    def test_audio_file_has_content(self):
        run_cli("youtube", VIDEO_URL)
        folder = TEST_DOWNLOAD_DIR / EXPECTED["content_id"]
        audio_files = list(folder.glob("audio.*"))
        assert audio_files[0].stat().st_size > 1000, "Audio file is suspiciously small"

    def test_audio_file_name_in_output(self):
        data = run_cli("youtube", VIDEO_URL)
        assert "audio_file" in data
        assert data["audio_file"].startswith("audio.")

    def test_audio_cached_on_second_run(self):
        run_cli("youtube", VIDEO_URL)
        folder = TEST_DOWNLOAD_DIR / EXPECTED["content_id"]
        audio_files = list(folder.glob("audio.*"))
        first_mtime = audio_files[0].stat().st_mtime
        # Second run should reuse cached audio
        run_cli("youtube", VIDEO_URL)
        assert audio_files[0].stat().st_mtime == first_mtime

    def test_force_redownloads_audio(self):
        run_cli("youtube", VIDEO_URL)
        folder = TEST_DOWNLOAD_DIR / EXPECTED["content_id"]
        audio_files = list(folder.glob("audio.*"))
        first_mtime = audio_files[0].stat().st_mtime
        # Force should re-download
        import time
        time.sleep(1)  # ensure mtime differs
        run_cli("youtube", "--force", VIDEO_URL)
        audio_files = list(folder.glob("audio.*"))
        assert audio_files[0].stat().st_mtime > first_mtime


class TestYouTubeVideo:
    """Test video download (opt-in with --video)."""

    def test_video_not_downloaded_by_default(self):
        data = run_cli("youtube", "--no-audio", VIDEO_URL)
        assert "video_file" not in data

    def test_video_file_downloaded(self):
        data = run_cli("youtube", "--video", "--no-audio", VIDEO_URL)
        folder = TEST_DOWNLOAD_DIR / EXPECTED["content_id"]
        video_files = list(folder.glob("video.*"))
        assert len(video_files) == 1, f"Expected 1 video file, found: {video_files}"

    def test_video_file_has_content(self):
        run_cli("youtube", "--video", "--no-audio", VIDEO_URL)
        folder = TEST_DOWNLOAD_DIR / EXPECTED["content_id"]
        video_files = list(folder.glob("video.*"))
        assert video_files[0].stat().st_size > 1000, "Video file is suspiciously small"

    def test_video_file_name_in_output(self):
        data = run_cli("youtube", "--video", "--no-audio", VIDEO_URL)
        assert "video_file" in data
        assert data["video_file"].startswith("video.")

    def test_video_cached_on_second_run(self):
        run_cli("youtube", "--video", "--no-audio", VIDEO_URL)
        folder = TEST_DOWNLOAD_DIR / EXPECTED["content_id"]
        video_files = list(folder.glob("video.*"))
        first_mtime = video_files[0].stat().st_mtime
        run_cli("youtube", "--video", "--no-audio", VIDEO_URL)
        assert video_files[0].stat().st_mtime == first_mtime

    def test_video_with_audio(self):
        data = run_cli("youtube", "--video", VIDEO_URL)
        assert "video_file" in data
        assert "audio_file" in data
