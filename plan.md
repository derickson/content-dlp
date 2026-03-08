# content-dlp — Implementation Plan

## Context

Build a centralized CLI tool for AI agents to harvest context from web sources (YouTube, podcasts, web pages). Each source type is a subcommand. Per-content folders act as both storage and cache. Designed for a future enrichment pipeline (transcription via self-hosted Whisper, AI text enrichment) that is shared across all source types.

Only the `youtube` subcommand is implemented now.

## File Structure

```
/home/dave/dev/content-dlp/           # git repo (renamed from ytdlp-helper)
├── content-dlp                       # shell wrapper (executable, no extension)
├── content_dlp/                      # Python package
│   ├── __init__.py
│   ├── __main__.py                   # 2 lines: from .cli import main; main()
│   ├── cli.py                        # argparse + subcommand dispatch
│   ├── config.py                     # load settings.yaml, defaults
│   ├── models.py                     # ContentMetadata dataclass
│   ├── cache.py                      # content ID generation, folder mgmt, cache checks
│   └── sources/
│       ├── __init__.py
│       └── youtube.py                # yt-dlp integration (only source built now)
├── settings.yaml                     # user config
├── pyproject.toml                    # rename to content-dlp, add deps
└── .python-version
```

Delete `main.py` (the stub from `uv init`).

## Dependencies

```
uv add yt-dlp pyyaml
```

No CLI framework — argparse with subparsers.

## Content ID & Folder Strategy

| Source | ID format | Example |
|--------|-----------|---------|
| youtube | `yt_{video_id}` | `yt_dQw4w9WgXcQ` |
| podcast (future) | `pod_{sha256_12}` | `pod_0424974c6853` |
| webscrape (future) | `web_{sha256_12}` | `web_a3f8b2c1d4e5` |

YouTube uses the native video ID (clean, greppable). Other sources hash the normalized URL (strip tracking params, lowercase host, strip trailing slash) truncated to 12 hex chars.

### Per-Content Folder Layout

```
~/content-dlp-data/
└── yt_dQw4w9WgXcQ/
    ├── metadata.json              # normalized metadata (cache marker)
    ├── source_metadata.json       # raw yt-dlp dump (minus bulky `formats` array)
    # future enrichment artifacts:
    ├── audio.opus                 # downloaded audio
    ├── transcript.json            # whisper output
    └── enrichment.json            # AI enrichment output
```

`metadata.json` existing = fetch is cached. Each future enrichment step similarly checks for its output file before running. File-presence-based state machine — no database needed.

## Settings — `settings.yaml`

```yaml
download_dir: ~/content-dlp-data

youtube:
  ytdlp_path: null    # null = use yt-dlp from venv

# Future (reserved, not implemented):
# whisper_endpoint: http://localhost:9000/asr
# webscrape:
#   user_agent: "content-dlp/0.1"
```

- Loaded from project root (relative to package), with `~` expansion
- Created with defaults if missing on first run
- CLI `--download-dir` flag overrides

## Shell Wrapper — `content-dlp`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.venvs/ytdlp-helper"
[ -d "$VENV_DIR" ] || { echo "Error: venv not found at $VENV_DIR" >&2; exit 1; }
exec "$VENV_DIR/bin/python" -m content_dlp "$@"
```

Uses `python -m content_dlp` (invokes `__main__.py`). No venv activation needed — calls the venv Python directly.

## Python Modules

### `models.py` — ContentMetadata dataclass

```python
@dataclass
class ContentMetadata:
    content_id: str                # "yt_dQw4w9WgXcQ"
    source_type: str               # "youtube" | "podcast" | "webscrape"
    url: str                       # original URL
    title: str
    description: str | None
    author: str | None
    published_date: str | None     # ISO 8601
    duration_seconds: int | None
    tags: list[str]
    thumbnail_url: str | None
    fetched_at: str                # ISO 8601 timestamp
    extras: dict                   # source-specific overflow fields
```

### `cache.py` — Content ID + folder management

- `generate_content_id(source_type, url, extracted_id=None) -> str`
- `content_dir(download_dir, content_id) -> Path` (ensures dir exists)
- `is_cached(download_dir, content_id) -> bool` (checks for `metadata.json`)

### `config.py` — Settings loader

- `load_config() -> dict` — reads `settings.yaml`, expands `~`, applies defaults

### `sources/youtube.py` — YouTube fetch

- Uses `yt_dlp.YoutubeDL` as Python library (not subprocess)
- `fetch(url, config) -> ContentMetadata`
- Extracts video ID from `info["id"]`, maps fields to ContentMetadata
- Writes `source_metadata.json` (full dump minus `formats` array)

### `cli.py` — Entry point

- Subparsers: `youtube` (now), `podcast`/`webscrape` (future stubs)
- `youtube` subcommand: positional `url`, optional `--download-dir`, `--force` (bypass cache)
- **Default output: JSON to stdout** — normalized metadata JSON, ready for piping to AI agents
- Status/progress messages go to stderr so they don't pollute the JSON stream
- Flow: parse args → load config → generate content ID → check cache → fetch if needed → save → print JSON to stdout

## Implementation Steps

0. Rename repo directory: `mv ~/dev/ytdlp-helper ~/dev/content-dlp` + update venv symlink
1. Update `pyproject.toml` — rename to `content-dlp`, add deps, add `[project.scripts]` entry
2. `uv add yt-dlp pyyaml` — install deps
3. Create `content_dlp/` package: `__init__.py`, `__main__.py`
4. Implement `config.py` + create `settings.yaml`
5. Implement `models.py`
6. Implement `cache.py`
7. Implement `sources/youtube.py`
8. Implement `cli.py`
9. Create `content-dlp` shell wrapper, `chmod +x`
10. Delete `main.py`
11. Update `.gitignore`

## Verification

```bash
# Fetch metadata (prints JSON to stdout)
./content-dlp youtube "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Pipe to jq
./content-dlp youtube "https://www.youtube.com/watch?v=dQw4w9WgXcQ" | jq .title

# Verify cache: second run returns instantly (cached JSON)
./content-dlp youtube "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Check folder was created
ls ~/content-dlp-data/yt_dQw4w9WgXcQ/

# Force re-fetch (bypass cache)
./content-dlp youtube --force "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```
