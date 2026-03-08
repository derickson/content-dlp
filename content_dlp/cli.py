import argparse
import json
import sys
from dataclasses import asdict

from .cache import content_dir, is_cached
from .config import load_config
from .sources import youtube


def main():
    parser = argparse.ArgumentParser(prog="content-dlp", description="Harvest context from web sources")
    parser.add_argument("--download-dir", help="Override download directory")
    sub = parser.add_subparsers(dest="command")

    yt_parser = sub.add_parser("youtube", help="Fetch YouTube video metadata and audio")
    yt_parser.add_argument("url", help="YouTube video URL")
    yt_parser.add_argument("--force", action="store_true", help="Bypass cache")
    yt_parser.add_argument("--no-audio", action="store_true", help="Skip audio download")
    yt_parser.add_argument("--video", action="store_true", help="Download video (480p max)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config()
    if args.download_dir:
        config["download_dir"] = args.download_dir

    if args.command == "youtube":
        _handle_youtube(args, config)


def _handle_youtube(args, config):
    from .cache import generate_content_id

    # Quick cache check before fetching metadata
    video_id = _extract_video_id(args.url)
    if video_id and not args.force:
        content_id = generate_content_id("youtube", args.url, extracted_id=video_id)
        if is_cached(config["download_dir"], content_id):
            print("Using cached metadata.", file=sys.stderr)
            cached_path = content_dir(config["download_dir"], content_id) / "metadata.json"
            with open(cached_path) as f:
                metadata_dict = json.load(f)
        else:
            metadata_dict = _fetch_and_save(args.url, config)
    else:
        metadata_dict = _fetch_and_save(args.url, config)

    # Download audio (default on, skip with --no-audio)
    if not args.no_audio:
        content_id = metadata_dict["content_id"]
        audio_path = youtube.download_audio(content_id, args.url, config, force=args.force)
        metadata_dict["audio_file"] = audio_path.name

    # Download video if requested
    if args.video:
        content_id = metadata_dict["content_id"]
        video_path = youtube.download_video(content_id, args.url, config, force=args.force)
        metadata_dict["video_file"] = video_path.name

    # Output JSON to stdout
    print(json.dumps(metadata_dict, indent=2))


def _fetch_and_save(url: str, config: dict) -> dict:
    metadata = youtube.fetch(url, config)
    folder = content_dir(config["download_dir"], metadata.content_id)
    metadata_dict = asdict(metadata)
    with open(folder / "metadata.json", "w") as f:
        json.dump(metadata_dict, f, indent=2)
    return metadata_dict


def _extract_video_id(url: str) -> str | None:
    """Try to extract video ID from URL for pre-fetch cache check."""
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)
    if "youtube.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        return qs.get("v", [None])[0]
    if "youtu.be" in parsed.netloc:
        return parsed.path.lstrip("/")
    return None
