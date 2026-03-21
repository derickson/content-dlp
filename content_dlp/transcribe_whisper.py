"""Transcription via GPU-backed whisper service."""

import json
import shutil
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

WHISPER_URL = "http://smaug:8100/whisper-file"
DROP_FOLDER = Path("/home/dave/dev/dockerlab/shared_drop_folder")
CONTAINER_DROP_PREFIX = "/app/drop"


def transcribe(audio_path: Path, content_folder: Path, force: bool = False) -> dict:
    """Transcribe audio via whisper service. Returns transcript dict.

    Caches result as transcript.json in the content folder.
    """
    cache_path = content_folder / "transcript.json"

    if not force and cache_path.exists():
        print("Using cached transcript.", file=sys.stderr)
        with open(cache_path) as f:
            cached = json.load(f)
        # Handle legacy cache that stored raw string
        if isinstance(cached, str):
            cached = {"text": cached}
        return cached

    # Copy audio to the shared drop folder using content_id to avoid collisions
    staged_name = f"{content_folder.name}{audio_path.suffix}"
    drop_path = DROP_FOLDER / staged_name
    print("Staging audio for transcription...", file=sys.stderr)
    shutil.copy2(audio_path, drop_path)

    # Call whisper service
    container_path = f"{CONTAINER_DROP_PREFIX}/{staged_name}"
    payload = json.dumps({"file_path": container_path}).encode()
    req = Request(WHISPER_URL, data=payload, headers={"Content-Type": "application/json"})

    print("Transcribing audio (this may take a while)...", file=sys.stderr)
    try:
        with urlopen(req, timeout=600) as resp:
            result = json.loads(resp.read())
    except URLError as e:
        raise RuntimeError(f"Whisper service error: {e}") from e
    finally:
        # Clean up staged file
        drop_path.unlink(missing_ok=True)

    # Normalize: if whisper returns a plain string, wrap it
    if isinstance(result, str):
        result = {"text": result}

    # Cache the response
    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)
    print("Transcript saved.", file=sys.stderr)

    return result
