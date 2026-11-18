#!/usr/bin/env python3
"""
transcription_cli.py

Command-line entry point for local audio/video transcription with faster-whisper.
This file keeps argument parsing and output handling separate from the shared
transcription engine in `transcription_core.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from transcription_core import find_single_audio_file, transcribe_with_faster_whisper


# Build the CLI parser while keeping the accepted flags explicit and local.
def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trascrive un file audio/video (.mp3, .mp4) offline con faster-whisper."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Percorso del file (.mp3, .mp4). Se omesso, cerca un solo file supportato nella cartella.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Percorso file di output .txt (default: stesso nome del file input).",
    )
    parser.add_argument(
        "--lang",
        default="it",
        help="Lingua ISO (es: it, en). Default: it.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Prompt contestuale opzionale per migliorare termini specifici.",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="Modello whisper (es: tiny, base, small, medium, large-v3). Default: small.",
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "balanced", "accurate"],
        default="fast",
        help="Preset velocità/qualità. Default: fast.",
    )
    parser.add_argument(
        "--model-cache-dir",
        type=Path,
        default=Path.cwd() / "models" / "faster-whisper",
        help="Cartella locale per scaricare/cache modelli.",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Usa solo file modello già locali (nessun download).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Stampa la trascrizione su stdout per copiarla fuori dalla CLI.",
    )
    return parser


# Resolve the input file from the CLI flags or the current working directory.
def resolve_input_audio_path(input_path: Path | None) -> Path:
    if input_path is not None:
        return input_path
    return find_single_audio_file(Path.cwd())


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
        print(f"File non trovato: {audio_path}", file=sys.stderr)
        return 1

    output_path = args.output or audio_path.with_suffix(".txt")

    args.model_cache_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"Trascrizione offline via faster-whisper (model={args.model}, mode={args.mode})..."
    )
    try:
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
        print(f"Errore durante la trascrizione: {exc}", file=sys.stderr)
        return 1

    if not text:
        print("Trascrizione vuota.", file=sys.stderr)
        return 2

    output_path.write_text(text + "\n", encoding="utf-8")
    print(f"Trascrizione completata: {output_path}")
    if args.stdout:
        print("=== TRASCRIZIONE INIZIO ===")
        print(text)
        print("=== TRASCRIZIONE FINE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
