import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp

from ..cache import content_dir, generate_content_id
from ..models import ContentMetadata


def _ydl_logger():
    return type("L", (), {
        "debug": lambda *a: None,
        "warning": lambda *a: None,
        "error": lambda s, m: print(m, file=sys.stderr),
    })()


def fetch(url: str, config: dict) -> ContentMetadata:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "logger": _ydl_logger(),
    }

    print("Fetching metadata...", file=sys.stderr)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    video_id = info["id"]
    content_id = generate_content_id("youtube", url, extracted_id=video_id)

    # Parse upload date
    published_date = None
    if info.get("upload_date"):
        d = info["upload_date"]
        published_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    metadata = ContentMetadata(
        content_id=content_id,
        source_type="youtube",
        url=info.get("webpage_url", url),
        title=info.get("title", ""),
        description=info.get("description"),
        author=info.get("uploader"),
        published_date=published_date,
        duration_seconds=info.get("duration"),
        tags=info.get("tags") or [],
        thumbnail_url=info.get("thumbnail"),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        extras={
            "channel_id": info.get("channel_id"),
            "channel_url": info.get("channel_url"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "categories": info.get("categories"),
        },
    )

    # Save source metadata (full dump minus bulky formats)
    download_dir = config["download_dir"]
    folder = content_dir(download_dir, content_id)
    source_info = {k: v for k, v in info.items() if k != "formats"}
    with open(folder / "source_metadata.json", "w") as f:
        json.dump(source_info, f, indent=2, default=str)

    return metadata


def download_audio(content_id: str, url: str, config: dict, force: bool = False) -> Path:
    """Download audio as opus into the content folder. Returns path to audio file."""
    download_dir = config["download_dir"]
    folder = content_dir(download_dir, content_id)

    # Check if audio already exists
    if not force:
        existing = _find_audio_file(folder)
        if existing:
            print("Audio already downloaded.", file=sys.stderr)
            return existing

    print("Downloading audio...", file=sys.stderr)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": _ydl_logger(),
        "format": "bestaudio/best",
        "outtmpl": str(folder / "audio.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    audio_path = _find_audio_file(folder)
    if not audio_path:
        raise RuntimeError("Audio download completed but no audio file found")
    print(f"Audio saved: {audio_path.name}", file=sys.stderr)
    return audio_path


def download_video(content_id: str, url: str, config: dict, force: bool = False) -> Path:
    """Download video at low resolution (480p max). Returns path to video file."""
    download_dir = config["download_dir"]
    folder = content_dir(download_dir, content_id)

    if not force:
        existing = _find_video_file(folder)
        if existing:
            print("Video already downloaded.", file=sys.stderr)
            return existing

    print("Downloading video (480p max)...", file=sys.stderr)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": _ydl_logger(),
        "format": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
        "outtmpl": str(folder / "video.%(ext)s"),
        "merge_output_format": "mp4",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    video_path = _find_video_file(folder)
    if not video_path:
        raise RuntimeError("Video download completed but no video file found")
    print(f"Video saved: {video_path.name}", file=sys.stderr)
    return video_path


def _find_audio_file(folder: Path) -> Path | None:
    """Find the audio file in a content folder."""
    for ext in ("mp3", "m4a", "webm", "opus", "ogg"):
        path = folder / f"audio.{ext}"
        if path.exists():
            return path
    return None


def _find_video_file(folder: Path) -> Path | None:
    """Find the video file in a content folder."""
    for ext in ("mp4", "mkv", "webm"):
        path = folder / f"video.{ext}"
        if path.exists():
            return path
    return None
