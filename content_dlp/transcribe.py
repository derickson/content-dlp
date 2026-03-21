"""Transcription via NVIDIA Parakeet TDT 0.6B v3 (local GPU)."""

import json
import logging
import sys
from contextlib import contextmanager
from pathlib import Path

MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v3"
CHUNK_DURATION_SEC = 300  # 5 minutes per chunk to fit in GPU memory
CHUNK_OVERLAP_SEC = 5  # overlap to avoid cutting words at boundaries
TIMESTAMP_CHUNK_SEC = 6  # group words into ~6-second chunks for output

_model = None


@contextmanager
def _redirect_stdout_to_stderr():
    """Redirect stdout to stderr to prevent NeMo logging from polluting JSON output."""
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    # Suppress NeMo's verbose logging to reduce noise
    nemo_logger = logging.getLogger("nemo")
    old_level = nemo_logger.level
    nemo_logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        sys.stdout = old_stdout
        nemo_logger.setLevel(old_level)


def _get_model():
    """Lazy-load the Parakeet TDT model on first use."""
    global _model
    if _model is not None:
        return _model

    print("Loading Parakeet TDT model (first run may download weights)...", file=sys.stderr)
    with _redirect_stdout_to_stderr():
        import nemo.collections.asr as nemo_asr
        _model = nemo_asr.models.ASRModel.from_pretrained(model_name=MODEL_NAME)
    _model.eval()
    print("Model loaded.", file=sys.stderr)
    return _model


def _prepare_audio(audio_path: Path, content_folder: Path) -> tuple[Path, float]:
    """Convert audio to 16kHz mono WAV for Parakeet. Returns (wav_path, duration_sec)."""
    from pydub import AudioSegment

    audio = AudioSegment.from_file(str(audio_path))
    audio = audio.set_channels(1).set_frame_rate(16000)
    duration_sec = len(audio) / 1000.0

    wav_path = content_folder / "_temp_16k.wav"
    audio.export(str(wav_path), format="wav")
    return wav_path, duration_sec


def _chunk_audio(audio_path: Path, content_folder: Path) -> list[tuple[Path, float]]:
    """Split audio into chunks if needed. Returns list of (chunk_path, offset_sec)."""
    from pydub import AudioSegment

    audio = AudioSegment.from_file(str(audio_path))
    duration_ms = len(audio)
    chunk_ms = CHUNK_DURATION_SEC * 1000
    overlap_ms = CHUNK_OVERLAP_SEC * 1000

    if duration_ms <= chunk_ms:
        return [(audio_path, 0.0)]

    chunks = []
    start_ms = 0
    idx = 0
    while start_ms < duration_ms:
        end_ms = min(start_ms + chunk_ms, duration_ms)
        chunk = audio[start_ms:end_ms]
        chunk_path = content_folder / f"_temp_chunk_{idx}.wav"
        chunk.export(str(chunk_path), format="wav")
        chunks.append((chunk_path, start_ms / 1000.0))
        start_ms += chunk_ms - overlap_ms
        idx += 1

    return chunks


def _chunk_by_duration(words: list[dict], chunk_sec: float = TIMESTAMP_CHUNK_SEC) -> list[dict]:
    """Group words into approximately chunk_sec-second chunks."""
    if not words:
        return []

    chunks = []
    current_words = []
    chunk_start = None

    for w in words:
        if chunk_start is None:
            chunk_start = w["start"]
        current_words.append(w["word"])

        if w["end"] - chunk_start >= chunk_sec:
            chunks.append({
                "text": " ".join(current_words),
                "start": chunk_start,
                "end": w["end"],
            })
            current_words = []
            chunk_start = None

    if current_words:
        chunks.append({
            "text": " ".join(current_words),
            "start": chunk_start,
            "end": words[-1]["end"],
        })

    return chunks


def _transcribe_single(model, wav_path: str) -> dict:
    """Transcribe a single audio file and return hypothesis data."""
    with _redirect_stdout_to_stderr():
        output = model.transcribe([wav_path], timestamps=True)
    hyp = output[0]

    words = []

    if hasattr(hyp, "timestamp") and hyp.timestamp is not None:
        ts = hyp.timestamp
        for w in ts.get("word", []):
            words.append({
                "word": w["word"],
                "start": w["start"],
                "end": w["end"],
            })

    return {"text": hyp.text, "words": words}


def _merge_chunk_results(chunk_results: list[tuple[dict, float]]) -> dict:
    """Merge transcription results from multiple chunks, adjusting timestamps by offset."""
    if len(chunk_results) == 1:
        return chunk_results[0][0]

    all_text = []
    all_words = []

    for i, (result, offset) in enumerate(chunk_results):
        # For overlapping chunks after the first, skip content from the overlap region
        # to avoid duplicated words
        overlap_cutoff = CHUNK_OVERLAP_SEC if i > 0 else 0

        if result["text"]:
            # For chunks after the first, we trim words that fall in the overlap
            if i > 0 and result["words"]:
                # Find first word after the overlap cutoff
                skip_until = 0
                for j, w in enumerate(result["words"]):
                    if w["start"] >= overlap_cutoff:
                        skip_until = j
                        break
                trimmed_words = result["words"][skip_until:]
                if trimmed_words:
                    all_text.append(" ".join(w["word"] for w in trimmed_words))
                    for w in trimmed_words:
                        all_words.append({
                            "word": w["word"],
                            "start": round(w["start"] + offset, 3),
                            "end": round(w["end"] + offset, 3),
                        })
            else:
                all_text.append(result["text"])
                for w in result["words"]:
                    all_words.append({
                        "word": w["word"],
                        "start": round(w["start"] + offset, 3),
                        "end": round(w["end"] + offset, 3),
                    })

    return {
        "text": " ".join(all_text),
        "words": all_words,
    }


def transcribe(audio_path: Path, content_folder: Path, force: bool = False) -> dict:
    """Transcribe audio via Parakeet TDT. Returns transcript dict.

    Caches result as transcript.json in the content folder.
    For audio longer than CHUNK_DURATION_SEC, splits into overlapping chunks.
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

    # Preprocess audio to 16kHz mono WAV
    print("Preparing audio for transcription...", file=sys.stderr)
    wav_path, duration_sec = _prepare_audio(audio_path, content_folder)

    temp_files = [wav_path]
    try:
        model = _get_model()

        if duration_sec <= CHUNK_DURATION_SEC:
            print("Transcribing audio (this may take a while)...", file=sys.stderr)
            merged = _transcribe_single(model, str(wav_path))
        else:
            # Chunk long audio to avoid GPU OOM
            print(f"Long audio ({duration_sec:.0f}s) — splitting into {CHUNK_DURATION_SEC}s chunks...", file=sys.stderr)
            chunks = _chunk_audio(wav_path, content_folder)
            temp_files.extend(path for path, _ in chunks if path != wav_path)

            chunk_results = []
            for i, (chunk_path, offset) in enumerate(chunks):
                print(f"Transcribing chunk {i + 1}/{len(chunks)}...", file=sys.stderr)
                result = _transcribe_single(model, str(chunk_path))
                chunk_results.append((result, offset))

            merged = _merge_chunk_results(chunk_results)

        result = {
            "text": merged["text"],
            "chunks": _chunk_by_duration(merged["words"]),
            "model": MODEL_NAME,
        }

    finally:
        # Clean up temp files
        for f in temp_files:
            f.unlink(missing_ok=True)

    # Cache the response
    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)
    print("Transcript saved.", file=sys.stderr)

    return result
