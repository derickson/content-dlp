# content-dlp

CLI tool for AI agents to harvest context from web sources (YouTube, podcasts, web pages). Outputs normalized JSON to stdout for easy piping.

## Setup

Requires Python 3.12+ and ffmpeg. Transcript feature requires a GPU whisper service.

```bash
# Create venv and install
uv venv ~/.venvs/content-dlp
uv pip install yt-dlp pyyaml podcastparser requests

# Symlink .venv to the shared venv location
ln -s ~/.venvs/content-dlp .venv

# Make the wrapper executable
chmod +x content-dlp
```

## Usage

### YouTube

```bash
# Fetch metadata + download audio (default)
./content-dlp youtube "https://www.youtube.com/watch?v=VIDEO_ID"

# Metadata only, no audio download
./content-dlp youtube --no-audio "https://www.youtube.com/watch?v=VIDEO_ID"

# Download video (480p max)
./content-dlp youtube --video "https://www.youtube.com/watch?v=VIDEO_ID"

# Transcribe audio via GPU whisper service
./content-dlp youtube --transcript "https://www.youtube.com/watch?v=VIDEO_ID"

# Force re-fetch (bypass cache)
./content-dlp youtube --force "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Podcast

```bash
# Fetch latest episode with audio
./content-dlp podcast "https://feeds.example.com/podcast.xml"

# Fetch 3 most recent episodes, metadata only
./content-dlp podcast --episodes 3 --no-audio "https://feeds.example.com/podcast.xml"

# Fetch and transcribe
./content-dlp podcast --transcript "https://feeds.example.com/podcast.xml"
```

Podcast output is always a JSON array, even for a single episode.

### Webscrape

```bash
# Scrape page metadata + save markdown content
./content-dlp webscrape "https://example.com/page"

# Metadata only, skip saving markdown
./content-dlp webscrape --no-content "https://example.com/page"
```

Uses the [Jina Reader API](https://jina.ai/reader/) to extract page content as markdown.

### General options

```bash
# Pipe JSON output to jq
./content-dlp youtube "https://www.youtube.com/watch?v=VIDEO_ID" | jq .title

# Override download directory
./content-dlp --download-dir /tmp/test youtube "https://www.youtube.com/watch?v=VIDEO_ID"
```

Status/progress messages go to stderr so they don't pollute the JSON stream.

## Output

All sources output normalized JSON to stdout with a shared `ContentMetadata` schema:

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
  "extras": { ... },
  "audio_file": "audio.mp3",
  "video_file": "video.mp4",
  "transcript": { "text": "..." }
}
```

Optional fields by flag:
- `audio_file` — included by default for youtube/podcast (omitted with `--no-audio`)
- `video_file` — included with `--video` (youtube only)
- `transcript` — included with `--transcript` (youtube, podcast)
- `content_file` — included by default for webscrape (omitted with `--no-content`)

## Storage

Each fetched item gets a folder under the download directory (default `~/content-dlp-data`):

```
~/content-dlp-data/
├── yt_dQw4w9WgXcQ/
│   ├── metadata.json          # normalized metadata (cache marker)
│   ├── source_metadata.json   # raw yt-dlp dump
│   ├── audio.mp3              # downloaded audio
│   ├── video.mp4              # downloaded video (--video)
│   └── transcript.json        # whisper transcript (--transcript)
├── pod_0424974c6853/
│   ├── metadata.json
│   ├── source_metadata.json
│   ├── audio.mp3
│   └── transcript.json
└── web_a1b2c3d4e5f6/
    ├── metadata.json
    ├── source_metadata.json
    └── content.md             # page content as markdown
```

Caching is file-presence-based — each artifact is cached independently. Use `--force` to bypass all caches.

## Configuration

`settings.yaml` in the project root:

```yaml
download_dir: ~/content-dlp-data

youtube:
  ytdlp_path: null      # null = use yt-dlp from venv

podcast:
  user_agent: content-dlp/0.1

webscrape:
  jina_api_key: null    # optional, for higher rate limits
  timeout: 30
```

Created with defaults on first run if missing. CLI `--download-dir` overrides the config value.

## Tests

```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v
```

Tests hit real APIs (YouTube, NPR, Jina) — they require network access. Transcript tests also require the whisper service on `smaug:8100`.
