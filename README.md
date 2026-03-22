# content-dlp

CLI tool for AI agents to harvest context from web sources (YouTube, podcasts, web pages). Outputs normalized JSON to stdout for easy piping.

## Setup

Requires Python 3.12+ and ffmpeg. Transcript feature requires a CUDA-capable GPU (uses NVIDIA Parakeet TDT 0.6B v3 locally via NeMo toolkit).

```bash
# Create venv and install
uv venv ~/.venvs/content-dlp
uv pip install -e .

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

# Transcribe audio locally via Parakeet TDT
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

### Transcribe (standalone)

```bash
# Transcribe a local audio file
./content-dlp transcribe /path/to/audio.mp3

# Specify output directory for transcript.json
./content-dlp transcribe --output-dir /tmp/results /path/to/audio.mp3
```

Transcribes any audio file locally using NVIDIA Parakeet TDT 0.6B v3. Outputs JSON with full text and timestamped chunks (~6-second intervals).

### HTTP Server

```bash
# Start the REST API server (default port 7055)
./content-dlp serve

# Custom port and host
./content-dlp serve --port 8080 --host 127.0.0.1

# Run in the background
./content-dlp serve &

# Stop the server (foreground: Ctrl+C, background: kill by port)
kill $(lsof -t -i:7055)
```

Exposes the same functionality as the CLI over HTTP, useful when callers (e.g. Docker containers) can't invoke the CLI directly.

**Endpoints:**

| Method | Path | Body fields |
|--------|------|-------------|
| `GET` | `/health` | — |
| `POST` | `/youtube` | `url`, `no_audio?`, `video?`, `transcript?`, `force?` |
| `POST` | `/podcast` | `url`, `episodes?`, `no_audio?`, `transcript?`, `force?` |
| `POST` | `/webscrape` | `url`, `no_content?`, `force?` |
| `POST` | `/transcribe` | `file_path` or `audio_url`, `force?`, `output_dir?` |

```bash
# Example: scrape a page from a Docker container
curl -X POST http://host.docker.internal:7055/webscrape \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com/page"}'

# Example: transcribe a file on the host
curl -X POST http://localhost:7055/transcribe \
  -H 'Content-Type: application/json' \
  -d '{"file_path": "/home/user/audio.mp3"}'
```

Responses are the same JSON as the CLI output. Errors return `{"error": "..."}` with appropriate HTTP status codes (400 for validation errors, 500 for server errors).

**Install as a systemd service** (auto-start on boot, auto-restart on crash):

```bash
# Install and enable the service
sudo cp content-dlp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable content-dlp
sudo systemctl start content-dlp

# Check status and logs
sudo systemctl status content-dlp
journalctl -u content-dlp -f

# Restart / stop
sudo systemctl restart content-dlp
sudo systemctl stop content-dlp
```

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
  "transcript": {
    "text": "full transcript...",
    "chunks": [
      {"text": "~6s of text...", "start": 0.0, "end": 5.92},
      {"text": "next ~6s...", "start": 5.92, "end": 12.16}
    ],
    "model": "nvidia/parakeet-tdt-0.6b-v3"
  }
}
```

Optional fields by flag:
- `audio_file` — included by default for youtube/podcast (omitted with `--no-audio`)
- `video_file` — included with `--video` (youtube only)
- `transcript` — included with `--transcript` (youtube, podcast)
- `content_file` — included by default for webscrape (omitted with `--no-content`)
- `markdown` — full page text, included by default for webscrape (omitted with `--no-content`)

## Storage

Each fetched item gets a folder under the download directory (default `~/content-dlp-data`):

```
~/content-dlp-data/
├── yt_dQw4w9WgXcQ/
│   ├── metadata.json          # normalized metadata (cache marker)
│   ├── source_metadata.json   # raw yt-dlp dump
│   ├── audio.mp3              # downloaded audio
│   ├── video.mp4              # downloaded video (--video)
│   └── transcript.json        # Parakeet TDT transcript (--transcript)
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

transcribe:
  model: nvidia/parakeet-tdt-0.6b-v3
  long_audio_threshold: 480  # seconds; uses local attention for audio longer than this
```

Created with defaults on first run if missing. CLI `--download-dir` overrides the config value.

## Tests

```bash
# Run all tests
.venv/bin/python -m pytest tests/ -v
```

Tests hit real APIs (YouTube, NPR, Jina) — they require network access. Transcript tests require a CUDA-capable GPU with the Parakeet TDT model.
