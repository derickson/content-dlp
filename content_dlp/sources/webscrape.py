import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from ..cache import content_dir, generate_content_id
from ..models import ContentMetadata


def fetch(url: str, config: dict) -> ContentMetadata:
    ws_config = config.get("webscrape", {})
    timeout = ws_config.get("timeout", 30)
    api_key = ws_config.get("jina_api_key")

    print("Fetching page via Jina Reader...", file=sys.stderr)

    headers = {
        "Accept": "application/json",
        "x-timeout": str(timeout),
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=timeout + 10)
    resp.raise_for_status()
    jina_data = resp.json()["data"]

    content_id = generate_content_id("webscrape", url)

    parsed = urlparse(url)
    word_count = len(jina_data.get("content", "").split())

    metadata = ContentMetadata(
        content_id=content_id,
        source_type="webscrape",
        url=url,
        title=jina_data.get("title", ""),
        description=jina_data.get("description"),
        author=None,
        published_date=None,
        duration_seconds=None,
        tags=[],
        thumbnail_url=None,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        extras={
            "domain": parsed.netloc,
            "path": parsed.path,
            "links": jina_data.get("links"),
            "images": jina_data.get("images"),
            "word_count": word_count,
        },
    )

    # Save source metadata (full Jina response including markdown content)
    download_dir = config["download_dir"]
    folder = content_dir(download_dir, content_id)
    with open(folder / "source_metadata.json", "w") as f:
        json.dump(jina_data, f, indent=2, default=str)

    return metadata


def save_content(content_id: str, config: dict, force: bool = False) -> Path:
    """Save page markdown to content.md. Returns path to file."""
    download_dir = config["download_dir"]
    folder = content_dir(download_dir, content_id)
    content_path = folder / "content.md"

    if not force and content_path.exists():
        print("Content already saved.", file=sys.stderr)
        return content_path

    # Read markdown from cached source metadata
    with open(folder / "source_metadata.json") as f:
        source_data = json.load(f)

    markdown = source_data.get("content", "")
    content_path.write_text(markdown, encoding="utf-8")
    print(f"Content saved: {content_path.name}", file=sys.stderr)
    return content_path
