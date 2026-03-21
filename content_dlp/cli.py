import argparse
import json
import sys
from dataclasses import asdict

from .cache import content_dir, is_cached
from .config import load_config
from .sources import youtube, podcast, webscrape


def main():
    parser = argparse.ArgumentParser(
        prog="content-dlp",
        description="Harvest normalized metadata, audio, video, and transcripts from web sources for AI agents.",
        epilog="""examples:
  %(prog)s youtube "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  %(prog)s youtube --no-audio "https://www.youtube.com/watch?v=VIDEO_ID"
  %(prog)s youtube --video --transcript "https://www.youtube.com/watch?v=VIDEO_ID"
  %(prog)s podcast "https://feeds.example.com/podcast.xml"
  %(prog)s podcast --episodes 3 --no-audio "https://feeds.example.com/podcast.xml"
  %(prog)s webscrape "https://example.com/page"
  %(prog)s transcribe /path/to/audio.mp3

output:
  JSON is printed to stdout; status messages go to stderr.
  Pipe into jq for field extraction: %(prog)s youtube URL | jq .title

caching:
  Results are cached in ~/content-dlp-data/ by content ID.
  Use --force on any subcommand to bypass the cache and re-fetch.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--download-dir", help="Override download directory (default: ~/content-dlp-data)")
    sub = parser.add_subparsers(dest="command", title="sources", metavar="SOURCE")

    yt_parser = sub.add_parser(
        "youtube",
        help="YouTube video — metadata, audio, video, transcript",
        description="Fetch metadata and optionally download audio, video, or transcript for a YouTube video.",
    )
    yt_parser.add_argument("url", help="YouTube video URL (youtube.com/watch?v= or youtu.be/ links)")
    yt_parser.add_argument("--force", action="store_true", help="Bypass cache and re-fetch everything")
    yt_parser.add_argument("--no-audio", action="store_true", help="Skip audio download (metadata only)")
    yt_parser.add_argument("--video", action="store_true", help="Download video (480p max, mp4)")
    yt_parser.add_argument("--transcript", action="store_true", help="Transcribe audio locally via Parakeet TDT (requires audio)")

    pod_parser = sub.add_parser(
        "podcast",
        help="Podcast RSS — episode metadata, audio, transcript",
        description="Parse a podcast RSS feed and fetch metadata/audio for recent episodes.",
    )
    pod_parser.add_argument("url", help="Podcast RSS feed URL")
    pod_parser.add_argument("--episodes", type=int, default=1, help="Number of most recent episodes to fetch (default: 1)")
    pod_parser.add_argument("--force", action="store_true", help="Bypass cache and re-fetch everything")
    pod_parser.add_argument("--no-audio", action="store_true", help="Skip audio download (metadata only)")
    pod_parser.add_argument("--transcript", action="store_true", help="Transcribe audio locally via Parakeet TDT (requires audio)")

    ws_parser = sub.add_parser(
        "webscrape",
        help="Web page — content as markdown",
        description="Scrape a web page and save its content as markdown via Jina Reader API.",
    )
    ws_parser.add_argument("url", help="URL of the page to scrape")
    ws_parser.add_argument("--force", action="store_true", help="Bypass cache and re-fetch")
    ws_parser.add_argument("--no-content", action="store_true", help="Skip saving page markdown (metadata only)")

    tr_parser = sub.add_parser(
        "transcribe",
        help="Transcribe a local audio file via Parakeet TDT",
        description="Transcribe a local audio file and output JSON with text, segments, and word timestamps.",
    )
    tr_parser.add_argument("audio_file", help="Path to local audio file (mp3, wav, m4a, etc.)")
    tr_parser.add_argument("--force", action="store_true", help="Bypass cache and re-transcribe")
    tr_parser.add_argument("--output-dir", help="Directory to save transcript (default: same dir as audio file)")

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
    elif args.command == "transcribe":
        _handle_transcribe(args, config)


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


def _handle_transcribe(args, config):
    from pathlib import Path
    from .transcribe import transcribe

    audio_path = Path(args.audio_file).resolve()
    if not audio_path.exists():
        print(f"Error: audio file not found: {audio_path}", file=sys.stderr)
        sys.exit(1)

    if args.output_dir:
        output_folder = Path(args.output_dir).resolve()
        output_folder.mkdir(parents=True, exist_ok=True)
    else:
        output_folder = audio_path.parent

    result = transcribe(audio_path, output_folder, force=args.force)
    print(json.dumps(result, indent=2))


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
