#!/usr/bin/env python3
"""
transcription_cli.py

Command-line entry point for local audio/video transcription with faster-whisper.
This file keeps argument parsing and output handling separate from the shared
transcription engine in `transcription_core.py`.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from transcription_core import find_single_audio_file, transcribe_with_faster_whisper


# Build the CLI parser while keeping the accepted flags explicit and local.
def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcribe a local MP3 or MP4 file with faster-whisper."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input MP3/MP4 path. If omitted, find exactly one supported file in this directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output TXT path (default: the input basename).",
    )
    parser.add_argument(
        "--lang",
        default="it",
        help="Language code, such as it or en (default: it).",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Optional context prompt for specific terminology.",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="Whisper model name (default: small).",
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "balanced", "accurate"],
        default="fast",
        help="Speed/quality mode (default: fast).",
    )
    parser.add_argument(
        "--model-cache-dir",
        type=Path,
        default=Path.cwd() / "models" / "faster-whisper",
        help="Local model download/cache directory.",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Use only local model files; refuse downloads.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Also print the transcription to standard output.",
    )
    return parser


# Resolve the input file from the CLI flags or the current working directory.
def resolve_input_audio_path(input_path: Path | None) -> Path:
    if input_path is not None:
        return input_path
    return find_single_audio_file(Path.cwd())


# Replace an export on the same filesystem without truncating previous data on failure.
def write_transcript(path: Path, text: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(text + "\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


# Run one CLI transcription and return a process exit code.
def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        audio_path = resolve_input_audio_path(args.input)
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not audio_path.exists():
        print(f"File not found: {audio_path}", file=sys.stderr)
        return 1

    output_path = args.output or audio_path.with_suffix(".txt")

    print(
        f"Local transcription via faster-whisper (model={args.model}, mode={args.mode})..."
    )
    try:
        args.model_cache_dir.mkdir(parents=True, exist_ok=True)
        text = transcribe_with_faster_whisper(
            audio_path=audio_path,
            language=args.lang,
            prompt=args.prompt,
            model_name=args.model,
            mode=args.mode,
            model_cache_dir=args.model_cache_dir,
            local_files_only=args.local_files_only,
        )
    except Exception as exc:
        print(f"Transcription failed: {exc}", file=sys.stderr)
        return 1

    if not text:
        print("The transcription is empty.", file=sys.stderr)
        return 2

    try:
        write_transcript(output_path, text)
    except OSError as exc:
        print(f"Cannot save the transcription: {exc}", file=sys.stderr)
        return 1
    print(f"Transcription saved: {output_path}")
    if args.stdout:
        print("=== TRANSCRIPTION START ===")
        print(text)
        print("=== TRANSCRIPTION END ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
