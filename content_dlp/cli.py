import argparse
import json
import sys
from dataclasses import asdict

from .cache import content_dir, is_cached
from .config import load_config
from .sources import youtube, podcast, webscrape


def main():
    parser = argparse.ArgumentParser(prog="content-dlp", description="Harvest context from web sources")
    parser.add_argument("--download-dir", help="Override download directory")
    sub = parser.add_subparsers(dest="command")

    yt_parser = sub.add_parser("youtube", help="Fetch YouTube video metadata and audio")
    yt_parser.add_argument("url", help="YouTube video URL")
    yt_parser.add_argument("--force", action="store_true", help="Bypass cache")
    yt_parser.add_argument("--no-audio", action="store_true", help="Skip audio download")
    yt_parser.add_argument("--video", action="store_true", help="Download video (480p max)")
    yt_parser.add_argument("--transcript", action="store_true", help="Transcribe audio via whisper service")

    pod_parser = sub.add_parser("podcast", help="Fetch podcast episode metadata and audio from RSS feed")
    pod_parser.add_argument("url", help="Podcast RSS feed URL")
    pod_parser.add_argument("--episodes", type=int, default=1, help="Number of recent episodes (default: 1)")
    pod_parser.add_argument("--force", action="store_true", help="Bypass cache")
    pod_parser.add_argument("--no-audio", action="store_true", help="Skip audio download")
    pod_parser.add_argument("--transcript", action="store_true", help="Transcribe audio via whisper service")

    ws_parser = sub.add_parser("webscrape", help="Scrape a web page")
    ws_parser.add_argument("url", help="URL to scrape")
    ws_parser.add_argument("--force", action="store_true", help="Bypass cache")
    ws_parser.add_argument("--no-content", action="store_true", help="Skip saving markdown")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config()
    if args.download_dir:
        config["download_dir"] = args.download_dir

    if args.command == "youtube":
        _handle_youtube(args, config)
    elif args.command == "podcast":
        _handle_podcast(args, config)
    elif args.command == "webscrape":
        _handle_webscrape(args, config)


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

    # Transcribe audio if requested
    if args.transcript:
        if args.no_audio:
            print("Error: --transcript requires audio (cannot use with --no-audio)", file=sys.stderr)
            sys.exit(1)
        from .transcribe import transcribe
        content_id = metadata_dict["content_id"]
        folder = content_dir(config["download_dir"], content_id)
        transcript = transcribe(audio_path, folder, force=args.force)
        metadata_dict["transcript"] = transcript

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


def _handle_podcast(args, config):
    episodes = []
    # Always need to parse feed to discover episodes (can't do pre-fetch cache)
    metadata_list = podcast.fetch(args.url, config, num_episodes=args.episodes)

    for metadata in metadata_list:
        metadata_dict = asdict(metadata)

        if not args.no_audio:
            enclosure_url = metadata.extras.get("enclosure_url", "")
            mime_type = metadata.extras.get("enclosure_mime_type", "")
            if enclosure_url:
                audio_path = podcast.download_audio(
                    metadata.content_id, enclosure_url, mime_type, config, force=args.force
                )
                metadata_dict["audio_file"] = audio_path.name

        if args.transcript:
            if args.no_audio or "audio_file" not in metadata_dict:
                print("Error: --transcript requires audio", file=sys.stderr)
                sys.exit(1)
            from .transcribe import transcribe
            folder = content_dir(config["download_dir"], metadata.content_id)
            transcript = transcribe(audio_path, folder, force=args.force)
            metadata_dict["transcript"] = transcript

        episodes.append(metadata_dict)

    print(json.dumps(episodes, indent=2))


def _handle_webscrape(args, config):
    from .cache import generate_content_id

    content_id = generate_content_id("webscrape", args.url)
    if not args.force and is_cached(config["download_dir"], content_id):
        print("Using cached metadata.", file=sys.stderr)
        cached_path = content_dir(config["download_dir"], content_id) / "metadata.json"
        with open(cached_path) as f:
            metadata_dict = json.load(f)
    else:
        metadata = webscrape.fetch(args.url, config)
        folder = content_dir(config["download_dir"], metadata.content_id)
        metadata_dict = asdict(metadata)
        with open(folder / "metadata.json", "w") as f:
            json.dump(metadata_dict, f, indent=2)

    if not args.no_content:
        content_id = metadata_dict["content_id"]
        webscrape.save_content(content_id, config, force=args.force)
        metadata_dict["content_file"] = "content.md"

    print(json.dumps(metadata_dict, indent=2))


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
