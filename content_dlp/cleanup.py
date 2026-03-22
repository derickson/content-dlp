"""Age-based cache cleanup for content-dlp data directories."""

import shutil
import sys
import time
from pathlib import Path

MEDIA_GLOBS = ["audio.*", "video.*"]
MIN_AGE_SECONDS = 60  # never delete files modified in the last 60 seconds


def cleanup(download_dir: str, cleanup_config: dict) -> dict:
    """Walk content directories and evict stale files.

    Two-tier eviction:
    - Media files (audio/video) older than media_max_age_days are deleted
    - Entire directories older than metadata_max_age_days are removed

    Returns summary dict with counts and bytes freed.
    """
    media_max_age = cleanup_config.get("media_max_age_days", 30) * 86400
    metadata_max_age = cleanup_config.get("metadata_max_age_days", 365) * 86400
    dry_run = cleanup_config.get("dry_run", False)

    now = time.time()
    media_deleted = 0
    dirs_deleted = 0
    bytes_freed = 0

    base = Path(download_dir)
    if not base.exists():
        return {"media_deleted": 0, "dirs_deleted": 0, "bytes_freed": 0}

    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        if not _is_content_dir(entry):
            continue

        # Check if entire directory should be removed
        age_file = entry / "metadata.json"
        if not age_file.exists():
            age_file = entry / "transcript.json"
        if age_file.exists():
            file_age = now - age_file.stat().st_mtime
            if file_age > metadata_max_age and file_age > MIN_AGE_SECONDS:
                dir_bytes = _dir_size(entry)
                if dry_run:
                    print(f"[dry-run] Would remove directory: {entry.name} ({dir_bytes / 1_000_000:.1f}MB)", file=sys.stderr)
                else:
                    try:
                        shutil.rmtree(entry)
                        print(f"Removed directory: {entry.name} ({dir_bytes / 1_000_000:.1f}MB)", file=sys.stderr)
                    except OSError as e:
                        print(f"Error removing {entry.name}: {e}", file=sys.stderr)
                        continue
                dirs_deleted += 1
                bytes_freed += dir_bytes
                continue

        # Check individual media files
        for glob in MEDIA_GLOBS:
            for media_file in entry.glob(glob):
                file_age = now - media_file.stat().st_mtime
                if file_age > media_max_age and file_age > MIN_AGE_SECONDS:
                    file_bytes = media_file.stat().st_size
                    if dry_run:
                        print(f"[dry-run] Would delete: {entry.name}/{media_file.name} ({file_bytes / 1_000_000:.1f}MB)", file=sys.stderr)
                    else:
                        try:
                            media_file.unlink()
                            print(f"Deleted: {entry.name}/{media_file.name} ({file_bytes / 1_000_000:.1f}MB)", file=sys.stderr)
                        except OSError as e:
                            print(f"Error deleting {media_file}: {e}", file=sys.stderr)
                            continue
                    media_deleted += 1
                    bytes_freed += file_bytes

    summary = {
        "media_deleted": media_deleted,
        "dirs_deleted": dirs_deleted,
        "bytes_freed": bytes_freed,
    }

    action = "Would free" if dry_run else "Freed"
    print(
        f"Cleanup: {media_deleted} media files, {dirs_deleted} directories. "
        f"{action} {bytes_freed / 1_000_000:.1f}MB.",
        file=sys.stderr,
    )
    return summary


def _is_content_dir(path: Path) -> bool:
    """True if path looks like a content-dlp content directory."""
    return (path / "metadata.json").exists() or (path / "transcript.json").exists()


def _dir_size(path: Path) -> int:
    """Total bytes of all files in directory."""
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
