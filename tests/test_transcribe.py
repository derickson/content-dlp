"""Integration tests for Parakeet TDT transcription."""

import json
import subprocess
import sys
from pathlib import Path

# Short YouTube video for transcription tests
VIDEO_URL = "https://www.youtube.com/watch?v=yLUKVHH3X8I"
CONTENT_ID = "yt_yLUKVHH3X8I"

PYTHON = sys.executable
TEST_DOWNLOAD_DIR = Path(__file__).parent / "test_output"
PROJECT_ROOT = Path(__file__).parent.parent


def run_cli(*args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run content-dlp and return the completed process."""
    return subprocess.run(
        [PYTHON, "-m", "content_dlp", "--download-dir", str(TEST_DOWNLOAD_DIR), *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=timeout,
    )


def run_cli_json(*args: str, timeout: int = 600) -> dict:
    """Run content-dlp and return parsed JSON output."""
    result = run_cli(*args, timeout=timeout)
    assert result.returncode == 0, f"CLI failed:\nstderr: {result.stderr}\nstdout: {result.stdout}"
    return json.loads(result.stdout)


class TestPrepareAudio:
    """Test audio preprocessing."""

    def test_preprocess_audio(self):
        # First ensure we have audio downloaded
        run_cli_json("youtube", VIDEO_URL)
        audio_folder = TEST_DOWNLOAD_DIR / CONTENT_ID
        audio_files = list(audio_folder.glob("audio.*"))
        assert len(audio_files) == 1

        from content_dlp.transcribe import _prepare_audio
        wav_path, duration = _prepare_audio(audio_files[0], audio_folder)
        try:
            assert wav_path.exists()
            assert wav_path.suffix == ".wav"
            assert duration > 0

            # Verify 16kHz mono WAV
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(str(wav_path))
            assert audio.frame_rate == 16000
            assert audio.channels == 1
        finally:
            wav_path.unlink(missing_ok=True)


class TestTranscribeYouTube:
    """Test transcription via YouTube --transcript flag."""

    def test_transcribe_short_audio(self):
        data = run_cli_json("youtube", "--transcript", VIDEO_URL)
        assert "transcript" in data
        assert isinstance(data["transcript"]["text"], str)
        assert len(data["transcript"]["text"]) > 0

    def test_transcript_has_chunks(self):
        data = run_cli_json("youtube", "--transcript", VIDEO_URL)
        chunks = data["transcript"]["chunks"]
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert "text" in chunk
            assert "start" in chunk
            assert "end" in chunk
            assert isinstance(chunk["text"], str)
            assert len(chunk["text"]) > 0

    def test_transcript_model_field(self):
        data = run_cli_json("youtube", "--transcript", VIDEO_URL)
        assert data["transcript"]["model"] == "nvidia/parakeet-tdt-0.6b-v3"

    def test_transcript_cached(self):
        # First run — generates transcript
        run_cli_json("youtube", "--transcript", VIDEO_URL)
        cache_file = TEST_DOWNLOAD_DIR / CONTENT_ID / "transcript.json"
        assert cache_file.exists()
        first_mtime = cache_file.stat().st_mtime

        # Second run — should use cache
        result = run_cli("youtube", "--transcript", VIDEO_URL)
        assert result.returncode == 0
        assert "Using cached transcript" in result.stderr
        assert cache_file.stat().st_mtime == first_mtime

    def test_transcript_no_audio_error(self):
        result = run_cli("youtube", "--transcript", "--no-audio", VIDEO_URL)
        assert result.returncode != 0
        assert "requires audio" in result.stderr.lower()


class TestTranscribeSubcommand:
    """Test standalone transcribe subcommand."""

    def test_transcribe_local_file(self):
        # Ensure audio exists
        run_cli_json("youtube", VIDEO_URL)
        audio_files = list((TEST_DOWNLOAD_DIR / CONTENT_ID).glob("audio.*"))
        assert len(audio_files) == 1

        output_dir = TEST_DOWNLOAD_DIR / "transcribe_test"
        data = run_cli_json(
            "transcribe", "--output-dir", str(output_dir), str(audio_files[0])
        )
        assert isinstance(data["text"], str)
        assert len(data["text"]) > 0
        assert "chunks" in data

    def test_transcribe_missing_file(self):
        result = run_cli("transcribe", "/nonexistent/audio.mp3")
        assert result.returncode != 0
        assert "not found" in result.stderr.lower()
