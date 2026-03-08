import hashlib
from pathlib import Path
from urllib.parse import urlparse


def generate_content_id(source_type: str, url: str, extracted_id: str | None = None) -> str:
    prefix = {"youtube": "yt", "podcast": "pod", "webscrape": "web"}[source_type]
    if extracted_id:
        return f"{prefix}_{extracted_id}"
    parsed = urlparse(url.lower().rstrip("/"))
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    hash_val = hashlib.sha256(normalized.encode()).hexdigest()[:12]
    return f"{prefix}_{hash_val}"


def content_dir(download_dir: str, content_id: str) -> Path:
    path = Path(download_dir) / content_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_cached(download_dir: str, content_id: str) -> bool:
    return (Path(download_dir) / content_id / "metadata.json").exists()
