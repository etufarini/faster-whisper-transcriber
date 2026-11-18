#!/usr/bin/env python3
"""
worker.py

Execute one native request. Stdout contains only versioned JSON-lines messages;
all third-party output goes to stderr. No model is downloaded during inspection
or transcription, including when an inherited Hub environment enables networking.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import sys

from transcription_core import (
    download_missing_models,
    model_exists_in_cache,
    transcribe_with_faster_whisper,
)

PRESETS = json.loads(Path(__file__).with_name("presets.json").read_text(encoding="utf-8"))


# Flush one complete protocol message before any potentially blocking inference.
def emit(output, request_id: int, event: str, **values) -> None:
    output.write(json.dumps({"version": 1, "id": request_id, "event": event, **values}, ensure_ascii=False) + "\n")
    output.flush()


# Validate literal request data before file access or importing inference libraries.
def validate_request(request: object) -> dict:
    if not isinstance(request, dict) or type(request.get("version")) is not int or request["version"] != 1:
        raise ValueError("Unsupported worker protocol version.")
    if type(request.get("id")) is not int or request["id"] < 1:
        raise ValueError("Invalid operation identifier.")
    if request.get("action") not in ("inspect", "download", "transcribe"):
        raise ValueError("Unknown worker action.")
    cache = request.get("cacheDir")
    if not isinstance(cache, str) or not Path(cache).is_absolute():
        raise ValueError("The model cache must be an absolute path.")
    if request["action"] != "inspect" and request.get("preset") not in PRESETS:
        raise ValueError("Unknown transcription preset.")
    if request["action"] == "transcribe":
        media = request.get("input")
        if not isinstance(media, str) or not Path(media).is_absolute():
            raise ValueError("The input must be an absolute media path.")
        if Path(media).suffix.lower() not in (".mp3", ".mp4") or not Path(media).is_file():
            raise ValueError("Choose an existing MP3 or MP4 file.")
        if request.get("language") not in ("it", "en"):
            raise ValueError("Choose Italian or English.")
    return request


# Run the requested action with offline inspection/transcription and explicit download.
def execute(request: dict, output) -> dict:
    request_id = request["id"]
    cache = Path(request["cacheDir"])
    action = request["action"]
    os.environ["HF_HUB_OFFLINE"] = "0" if action == "download" else "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    if action == "inspect":
        return {"models": {name: model_exists_in_cache(preset["model"], cache) for name, preset in PRESETS.items()}}
    preset = PRESETS[request["preset"]]
    if action == "download":
        emit(output, request_id, "progress", phase="downloading", percent=None)
        download_missing_models([preset["model"]], cache)
        return {"available": True}
    if not model_exists_in_cache(preset["model"], cache):
        raise FileNotFoundError("The selected model is missing or incomplete. Download it first.")
    emit(output, request_id, "progress", phase="loading", percent=None)
    text = transcribe_with_faster_whisper(
        audio_path=Path(request["input"]), language=request["language"], prompt=None,
        model_name=preset["model"], mode=preset["mode"], model_cache_dir=cache,
        local_files_only=True,
        progress_callback=lambda value: emit(output, request_id, "progress", phase="transcribing", percent=value),
    )
    if not text:
        raise RuntimeError("No speech was transcribed from this file.")
    return {"text": text}


# Keep import noise away from stdout and convert failures to a single terminal event.
def main() -> int:
    output = sys.stdout
    request_id = 0
    try:
        line = sys.stdin.buffer.readline(65537)
        if len(line) > 65536:
            raise ValueError("Worker request exceeds the size limit.")
        decoded = json.loads(line)
        if isinstance(decoded, dict) and type(decoded.get("id")) is int and decoded["id"] > 0:
            request_id = decoded["id"]
        request = validate_request(decoded)
        with contextlib.redirect_stdout(sys.stderr):
            result = execute(request, output)
        emit(output, request_id, "result", **result)
        return 0
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        emit(output, request_id, "error", message=str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
