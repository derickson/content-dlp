import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

import requests as http_requests
from flask import Flask, jsonify, request

from .cli import (
    _handle_youtube,
    _handle_podcast,
    _handle_webscrape,
    _handle_transcribe,
)


def create_app(config: dict) -> Flask:
    app = Flask(__name__)

    cleanup_config = config.get("cleanup", {})
    if cleanup_config.get("run_on_startup", True):
        from .cleanup import cleanup
        cleanup(config["download_dir"], cleanup_config)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/youtube", methods=["POST"])
    def youtube():
        body = request.get_json(force=True)
        args = SimpleNamespace(
            url=body["url"],
            no_audio=body.get("no_audio", False),
            video=body.get("video", False),
            transcript=body.get("transcript", False),
            force=body.get("force", False),
        )
        return _run(_handle_youtube, args, config)

    @app.route("/podcast", methods=["POST"])
    def podcast():
        body = request.get_json(force=True)
        args = SimpleNamespace(
            url=body["url"],
            episodes=body.get("episodes", 1),
            no_audio=body.get("no_audio", False),
            transcript=body.get("transcript", False),
            force=body.get("force", False),
        )
        return _run(_handle_podcast, args, config)

    @app.route("/webscrape", methods=["POST"])
    def webscrape():
        body = request.get_json(force=True)
        args = SimpleNamespace(
            url=body["url"],
            no_content=body.get("no_content", False),
            force=body.get("force", False),
        )
        return _run(_handle_webscrape, args, config)

    @app.route("/transcribe", methods=["POST"])
    def transcribe():
        body = request.get_json(force=True)
        audio_url = body.get("audio_url")
        file_path = body.get("file_path")

        if not audio_url and not file_path:
            return jsonify({"error": "either file_path or audio_url is required"}), 400

        if audio_url:
            return _transcribe_from_url(audio_url, body, config)

        args = SimpleNamespace(
            audio_file=file_path,
            force=body.get("force", False),
            output_dir=body.get("output_dir"),
        )
        return _run(_handle_transcribe, args, config)

    return app


def _transcribe_from_url(audio_url, body, config):
    """Download remote audio to a temp file, transcribe, then clean up."""
    import sys
    from .cache import generate_content_id, content_dir

    # Generate a unique output dir per audio URL for proper caching
    content_id = generate_content_id("podcast", audio_url)
    output = str(content_dir(config["download_dir"], f"{content_id}_transcript"))

    suffix = Path(audio_url.split("?")[0]).suffix or ".mp3"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_path = Path(tmp.name)
    try:
        print(f"Downloading audio from URL: {audio_url[:100]}...", file=sys.stderr)
        resp = http_requests.get(audio_url, stream=True, timeout=600)
        resp.raise_for_status()
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded {tmp_path.stat().st_size / 1_000_000:.1f}MB to temp file.", file=sys.stderr)

        args = SimpleNamespace(
            audio_file=str(tmp_path),
            force=body.get("force", False),
            output_dir=output,
        )
        return _run(_handle_transcribe, args, config)
    except http_requests.RequestException as e:
        return jsonify({"error": f"failed to download audio: {e}"}), 400
    finally:
        tmp_path.unlink(missing_ok=True)


def _run(handler, args, config):
    try:
        result = handler(args, config)
        return jsonify(result)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
