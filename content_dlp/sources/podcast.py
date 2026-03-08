import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import podcastparser

from ..cache import content_dir
from ..models import ContentMetadata


def _generate_episode_id(guid: str) -> str:
    hash_val = hashlib.sha256(guid.encode()).hexdigest()[:12]
    return f"pod_{hash_val}"


def _mime_to_ext(mime_type: str, url: str) -> str:
    mime_map = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/aac": ".aac",
        "audio/ogg": ".ogg",
        "audio/opus": ".opus",
        "audio/wav": ".wav",
        "audio/flac": ".flac",
    }
    if mime_type and mime_type.lower() in mime_map:
        return mime_map[mime_type.lower()]
    # Try URL path extension
    from urllib.parse import urlparse
    path = urlparse(url).path
    for ext in (".mp3", ".m4a", ".ogg", ".opus", ".aac", ".wav", ".flac"):
        if path.lower().endswith(ext):
            return ext
    return ".mp3"


def fetch(feed_url: str, config: dict, num_episodes: int = 1) -> list[ContentMetadata]:
    user_agent = config.get("podcast", {}).get("user_agent", "content-dlp/0.1")
    download_dir = config["download_dir"]

    print("Fetching feed...", file=sys.stderr)
    req = urllib.request.Request(feed_url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req) as response:
        parsed = podcastparser.parse(feed_url, response)

    episodes = sorted(parsed.get("episodes", []), key=lambda e: e.get("published", 0), reverse=True)
    episodes = episodes[:num_episodes]

    results = []
    for ep in episodes:
        # Determine GUID, falling back to enclosure URL
        enclosures = ep.get("enclosures", [])
        enclosure_url = enclosures[0]["url"] if enclosures else ""
        guid = ep.get("guid", enclosure_url)
        if not guid:
            guid = ep.get("title", "")

        content_id = _generate_episode_id(guid)

        # Parse published timestamp
        published_date = None
        if ep.get("published"):
            published_date = datetime.fromtimestamp(ep["published"], tz=timezone.utc).isoformat()

        metadata = ContentMetadata(
            content_id=content_id,
            source_type="podcast",
            url=enclosure_url or feed_url,
            title=ep.get("title", ""),
            description=ep.get("description", None),
            author=parsed.get("author", None) or ep.get("author", None),
            published_date=published_date,
            duration_seconds=ep.get("total_time", None),
            thumbnail_url=parsed.get("cover_url", None),
            fetched_at=datetime.now(timezone.utc).isoformat(),
            extras={
                "feed_url": feed_url,
                "feed_title": parsed.get("title", ""),
                "episode_guid": guid,
                "season": ep.get("season", None),
                "episode_number": ep.get("episode", None),
                "enclosure_url": enclosure_url,
                "enclosure_mime_type": enclosures[0].get("mime_type", "") if enclosures else "",
                "enclosure_file_size": enclosures[0].get("file_size", 0) if enclosures else 0,
            },
        )

        folder = content_dir(download_dir, content_id)
        metadata_dict = {k: v for k, v in metadata.__dict__.items()}
        from dataclasses import asdict
        metadata_dict = asdict(metadata)
        with open(folder / "metadata.json", "w") as f:
            json.dump(metadata_dict, f, indent=2)

        # Save source metadata (raw episode + feed-level info)
        source_meta = {"feed": {k: v for k, v in parsed.items() if k != "episodes"}, "episode": ep}
        with open(folder / "source_metadata.json", "w") as f:
            json.dump(source_meta, f, indent=2, default=str)

        results.append(metadata)

    return results


def download_audio(content_id: str, enclosure_url: str, mime_type: str, config: dict, force: bool = False) -> Path:
    download_dir = config["download_dir"]
    folder = content_dir(download_dir, content_id)

    # Check cache
    if not force:
        existing = _find_audio_file(folder)
        if existing:
            print(f"Audio already downloaded: {existing.name}", file=sys.stderr)
            return existing

    ext = _mime_to_ext(mime_type, enclosure_url)
    audio_path = folder / f"audio{ext}"

    print("Downloading audio...", file=sys.stderr)
    req = urllib.request.Request(enclosure_url, headers={
        "User-Agent": config.get("podcast", {}).get("user_agent", "content-dlp/0.1"),
    })
    with urllib.request.urlopen(req) as response, open(audio_path, "wb") as out:
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            out.write(chunk)

    print(f"Audio saved: {audio_path.name}", file=sys.stderr)
    return audio_path


def _find_audio_file(folder: Path) -> Path | None:
    for ext in ("mp3", "m4a", "ogg", "opus", "aac", "wav", "flac"):
        path = folder / f"audio.{ext}"
        if path.exists():
            return path
    return None
