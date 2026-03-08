# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

content-dlp is a CLI tool for AI agents to harvest normalized metadata and audio from web sources. It outputs JSON to stdout and status messages to stderr, making it pipeable (e.g., `./content-dlp youtube URL | jq .title`).

## Commands

```bash
# Run the CLI
./content-dlp youtube "https://www.youtube.com/watch?v=VIDEO_ID"
./content-dlp youtube --no-audio "https://www.youtube.com/watch?v=VIDEO_ID"
./content-dlp podcast "https://feeds.example.com/podcast.xml"
./content-dlp podcast --episodes 3 --no-audio "https://feeds.example.com/podcast.xml"

# Run all tests (requires network — hits real YouTube API)
.venv/bin/python -m pytest tests/ -v

# Run a single test
.venv/bin/python -m pytest tests/test_youtube.py::TestYouTubeMetadata::test_title -v

# Install deps into the project venv
uv pip install <package>
```

## Architecture

```
cli.py          argparse entry point, subcommand dispatch, cache check, JSON output
  → config.py   loads settings.yaml with defaults, expands paths
  → sources/    source-specific fetchers (youtube.py uses yt-dlp, podcast.py uses podcastparser)
  → models.py   ContentMetadata dataclass — normalized schema across all sources
  → cache.py    content ID generation, folder management, file-presence checks
```

**Data flow for `youtube` subcommand:**
1. Extract video ID from URL for pre-fetch cache lookup
2. If not cached (or `--force`), call `youtube.fetch()` → returns `ContentMetadata`
3. Save `metadata.json` (normalized) and `source_metadata.json` (raw yt-dlp dump) to content folder
4. Unless `--no-audio`, call `youtube.download_audio()` → downloads opus via ffmpeg
5. Print JSON to stdout

**Data flow for `podcast` subcommand:**
1. Fetch and parse RSS feed with `podcastparser`
2. Sort episodes by `published` descending, slice to `--episodes N`
3. For each episode: generate content_id from GUID hash (`pod_<hash12>`), map to `ContentMetadata`
4. Save `metadata.json` and `source_metadata.json` per episode
5. Unless `--no-audio`, stream-download enclosure audio (no transcoding)
6. Print JSON array to stdout (always an array, even for 1 episode)

## Key Patterns

- **Stdout/stderr separation:** JSON output goes to stdout only. All progress/status messages use `print(..., file=sys.stderr)`. This is critical for piping.
- **File-presence caching:** No database. Each content item gets a folder (`~/content-dlp-data/yt_VIDEO_ID/`). Metadata is cached if `metadata.json` exists; audio is cached if `audio.*` exists. `--force` bypasses both.
- **Content IDs:** YouTube uses native video ID (`yt_dQw4w9WgXcQ`). Podcast episodes hash the episode GUID (`pod_0424974c6853`).
- **yt-dlp as Python library:** Not invoked via subprocess. Uses `yt_dlp.YoutubeDL` directly with quiet mode and a custom logger that only surfaces errors to stderr.
- **Shell wrapper + `__main__.py`:** The `content-dlp` bash script finds the venv at `~/.venvs/content-dlp` and runs `python -m content_dlp`. The venv is symlinked as `.venv` in the project root.

## Adding a New Source

1. Create `content_dlp/sources/<name>.py` with a `fetch(url, config)` function returning `ContentMetadata`
2. Add a subcommand in `cli.py` with a `_handle_<name>` function
3. Add a source type prefix in `cache.py`'s `generate_content_id()`
4. Add integration tests in `tests/test_<name>.py`

## Testing

Tests are integration tests that call the CLI via `subprocess.run()` and parse JSON output. They use a fixture-managed `tests/test_output/` directory (cleaned before each test, kept after for inspection). All tests hit real APIs — no mocks.
