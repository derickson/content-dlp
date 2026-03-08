# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

content-dlp is a CLI tool for AI agents to harvest normalized metadata, audio, video, and transcripts from web sources. It outputs JSON to stdout and status messages to stderr, making it pipeable (e.g., `./content-dlp youtube URL | jq .title`).

## Commands

```bash
# Run the CLI — YouTube
./content-dlp youtube "https://www.youtube.com/watch?v=VIDEO_ID"
./content-dlp youtube --no-audio "https://www.youtube.com/watch?v=VIDEO_ID"
./content-dlp youtube --video "https://www.youtube.com/watch?v=VIDEO_ID"
./content-dlp youtube --transcript "https://www.youtube.com/watch?v=VIDEO_ID"

# Run the CLI — Podcast
./content-dlp podcast "https://feeds.example.com/podcast.xml"
./content-dlp podcast --episodes 3 --no-audio "https://feeds.example.com/podcast.xml"
./content-dlp podcast --transcript "https://feeds.example.com/podcast.xml"

# Run the CLI — Webscrape
./content-dlp webscrape "https://example.com/page"
./content-dlp webscrape --no-content "https://example.com/page"

# Run all tests (requires network — hits real APIs and whisper service)
.venv/bin/python -m pytest tests/ -v

# Run a single test
.venv/bin/python -m pytest tests/test_youtube.py::TestYouTubeMetadata::test_title -v

# Install deps into the project venv
uv pip install <package>
```

## Architecture

```
cli.py            argparse entry point, subcommand dispatch, cache check, JSON output
  → config.py     loads settings.yaml with defaults, expands paths
  → sources/      source-specific fetchers
      youtube.py  yt-dlp for metadata, audio (mp3), and video (480p mp4)
      podcast.py  podcastparser for RSS feeds, stream-download audio
      webscrape.py Jina Reader API for page content as markdown
  → transcribe.py GPU whisper service client (shared by youtube & podcast)
  → models.py     ContentMetadata dataclass — normalized schema across all sources
  → cache.py      content ID generation, folder management, file-presence checks
```

**Data flow for `youtube` subcommand:**
1. Extract video ID from URL for pre-fetch cache lookup
2. If not cached (or `--force`), call `youtube.fetch()` → returns `ContentMetadata`
3. Save `metadata.json` (normalized) and `source_metadata.json` (raw yt-dlp dump) to content folder
4. Unless `--no-audio`, call `youtube.download_audio()` → downloads mp3 via ffmpeg
5. If `--video`, call `youtube.download_video()` → downloads 480p max mp4
6. If `--transcript`, transcribe audio via whisper service → adds `transcript` to output
7. Print JSON to stdout

**Data flow for `podcast` subcommand:**
1. Fetch and parse RSS feed with `podcastparser`
2. Sort episodes by `published` descending, slice to `--episodes N`
3. For each episode: generate content_id from GUID hash (`pod_<hash12>`), map to `ContentMetadata`
4. Save `metadata.json` and `source_metadata.json` per episode
5. Unless `--no-audio`, stream-download enclosure audio (no transcoding)
6. If `--transcript`, transcribe audio via whisper service → adds `transcript` to output
7. Print JSON array to stdout (always an array, even for 1 episode)

**Data flow for `webscrape` subcommand:**
1. Generate content_id from URL hash (`web_<hash12>`)
2. If not cached (or `--force`), call `webscrape.fetch()` via Jina Reader API → returns `ContentMetadata`
3. Save `metadata.json` and `source_metadata.json` (full Jina response) to content folder
4. Unless `--no-content`, save page markdown as `content.md`
5. Print JSON to stdout

## Key Patterns

- **Stdout/stderr separation:** JSON output goes to stdout only. All progress/status messages use `print(..., file=sys.stderr)`. This is critical for piping.
- **File-presence caching:** No database. Each content item gets a folder (`~/content-dlp-data/yt_VIDEO_ID/`). Metadata is cached if `metadata.json` exists; audio is cached if `audio.*` exists; video if `video.*` exists; transcript if `transcript.json` exists. `--force` bypasses all.
- **Content IDs:** YouTube uses native video ID (`yt_dQw4w9WgXcQ`). Podcast episodes hash the episode GUID (`pod_0424974c6853`). Webscrape hashes the URL (`web_a1b2c3d4e5f6`).
- **Transcription:** Shared `transcribe.py` module used by both youtube and podcast. Stages audio to `/home/dave/dev/dockerlab/shared_drop_folder`, calls GPU whisper service at `smaug:8100`, caches result as `transcript.json`.
- **yt-dlp as Python library:** Not invoked via subprocess. Uses `yt_dlp.YoutubeDL` directly with quiet mode and a custom logger that only surfaces errors to stderr.
- **Shell wrapper + `__main__.py`:** The `content-dlp` bash script finds the venv at `~/.venvs/content-dlp` and runs `python -m content_dlp`. The venv is symlinked as `.venv` in the project root.

## Adding a New Source

1. Create `content_dlp/sources/<name>.py` with a `fetch(url, config)` function returning `ContentMetadata`
2. Add a subcommand in `cli.py` with a `_handle_<name>` function
3. Add a source type prefix in `cache.py`'s `generate_content_id()`
4. Add integration tests in `tests/test_<name>.py`

## Testing

Tests are integration tests that call the CLI via `subprocess.run()` and parse JSON output. A `conftest.py` clears the `tests/test_output/` directory once at session start (kept after for inspection). All tests hit real APIs — no mocks. Transcript tests require the whisper service on `smaug:8100` to be running.
