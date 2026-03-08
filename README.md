# content-dlp

CLI tool for AI agents to harvest context from web sources (YouTube, podcasts, web pages). Outputs normalized JSON to stdout for easy piping.

## Setup

Requires Python 3.12+ and ffmpeg.

```bash
# Create venv and install
uv venv ~/.venvs/content-dlp
uv pip install yt-dlp pyyaml

# Symlink .venv to the shared venv location
ln -s ~/.venvs/content-dlp .venv

# Make the wrapper executable
chmod +x content-dlp
```

## Usage

```bash
# Fetch metadata + download audio (default)
./content-dlp youtube "https://www.youtube.com/watch?v=VIDEO_ID"

# Metadata only, no audio download
./content-dlp youtube --no-audio "https://www.youtube.com/watch?v=VIDEO_ID"

# Pipe JSON output to jq
./content-dlp youtube "https://www.youtube.com/watch?v=VIDEO_ID" | jq .title

# Force re-fetch (bypass cache)
./content-dlp youtube --force "https://www.youtube.com/watch?v=VIDEO_ID"

# Override download directory
./content-dlp --download-dir /tmp/test youtube "https://www.youtube.com/watch?v=VIDEO_ID"
```

Status/progress messages go to stderr so they don't pollute the JSON stream.

## Output

JSON to stdout with these fields:

```json
{
  "content_id": "yt_dQw4w9WgXcQ",
  "source_type": "youtube",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "...",
  "description": "...",
  "author": "...",
  "published_date": "2009-10-25",
  "duration_seconds": 213,
  "tags": [],
  "thumbnail_url": "https://...",
  "fetched_at": "2026-03-08T16:09:14.726493+00:00",
  "extras": {
    "channel_id": "...",
    "channel_url": "...",
    "view_count": 1000000,
    "like_count": 50000,
    "categories": ["Music"]
  },
  "audio_file": "audio.opus"
}
```

The `audio_file` field is included when audio is downloaded (omitted with `--no-audio`).

## Storage

Each fetched item gets a folder under the download directory (default `~/content-dlp-data`):

```
~/content-dlp-data/
└── yt_dQw4w9WgXcQ/
    ├── metadata.json          # normalized metadata (cache marker)
    ├── source_metadata.json   # raw yt-dlp dump
    └── audio.opus             # downloaded audio
```

Caching is file-presence-based — if `metadata.json` exists, metadata is cached; if `audio.opus` exists, audio is cached. Use `--force` to bypass.

## Configuration

`settings.yaml` in the project root:

```yaml
download_dir: ~/content-dlp-data

youtube:
  ytdlp_path: null    # null = use yt-dlp from venv
```

Created with defaults on first run if missing. CLI `--download-dir` overrides the config value.

## Tests

```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v
```

Tests hit the real YouTube API — they require network access.
