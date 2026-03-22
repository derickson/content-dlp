import traceback
from types import SimpleNamespace

from flask import Flask, jsonify, request

from .cli import (
    _handle_youtube,
    _handle_podcast,
    _handle_webscrape,
    _handle_transcribe,
)


def create_app(config: dict) -> Flask:
    app = Flask(__name__)

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
        args = SimpleNamespace(
            audio_file=body["file_path"],
            force=body.get("force", False),
            output_dir=body.get("output_dir"),
        )
        return _run(_handle_transcribe, args, config)

    return app


def _run(handler, args, config):
    try:
        result = handler(args, config)
        return jsonify(result)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
