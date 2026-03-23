#!/usr/bin/env python3
"""
Trascrizione audio/video offline con faster-whisper.

Pensato per essere leggero e veloce su CPU, senza dipendenze cloud.

Uso:
  python3 transcription_cli.py
  python3 transcription_cli.py --mode fast --model small --lang it

Dipendenze:
  pip install faster-whisper
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable, Optional


AUDIO_SAMPLE_RATE = 16000
MODE_DECODING_PARAMS: dict[str, tuple[int, int, int, list[float]]] = {
    "fast": (2, 2, 1, [0.0]),
    "balanced": (5, 5, 1, [0.0, 0.2]),
    "accurate": (8, 8, 2, [0.0, 0.2, 0.4]),
}


def get_mode_decoding_params(mode: str) -> tuple[int, int, int, list[float]]:
    return MODE_DECODING_PARAMS.get(mode, MODE_DECODING_PARAMS["balanced"])


def is_cancel_requested(cancel_check: Optional[Callable[[], bool]]) -> bool:
    return bool(cancel_check and cancel_check())


SUPPORTED_INPUT_EXTENSIONS = (".mp3", ".mp4")


def find_single_audio_file(cwd: Path) -> Path:
    candidates = sorted(
        p for p in cwd.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
    )
    if not candidates:
        raise FileNotFoundError(
            "Nessun file audio/video supportato trovato nella cartella corrente (.mp3, .mp4)."
        )
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        raise RuntimeError(
            f"Trovati più file supportati ({names}). Usa --input per specificarne uno."
        )
    return candidates[0]


def transcribe_with_faster_whisper(
    audio_path: Path,
    language: Optional[str],
    prompt: Optional[str],
    model_name: str,
    mode: str,
    model_cache_dir: Path,
    local_files_only: bool,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> str:
    import numpy as np
    from faster_whisper.audio import decode_audio  # type: ignore
    from faster_whisper import WhisperModel  # type: ignore

    device = "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu"
    compute_type = "float16" if device == "cuda" else "int8_float32"
    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
        download_root=str(model_cache_dir),
        local_files_only=local_files_only,
    )
    if is_cancel_requested(cancel_check):
        raise InterruptedError("Trascrizione interrotta.")

    beam_size, best_of, patience, temperatures = get_mode_decoding_params(mode)

    # Decodifica e sanitizzazione difensiva: alcuni file possono arrivare
    # con ampiezze fuori scala e innescare overflow nel mel spectrogram.
    raw_audio = decode_audio(str(audio_path), sampling_rate=AUDIO_SAMPLE_RATE)
    audio = np.asarray(raw_audio, dtype=np.float32)
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        audio = audio / peak
    audio = np.clip(audio, -1.0, 1.0)
    duration_sec = float(audio.shape[0]) / float(AUDIO_SAMPLE_RATE) if audio.size else 0.0
    last_reported = -1
    if progress_callback:
        progress_callback(0)

    segments, _info = model.transcribe(
        audio,
        language=language,
        initial_prompt=prompt,
        beam_size=beam_size,
        best_of=best_of,
        patience=patience,
        temperature=temperatures,
        condition_on_previous_text=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        word_timestamps=False,
    )

    parts: list[str] = []
    for segment in segments:
        if is_cancel_requested(cancel_check):
            raise InterruptedError("Trascrizione interrotta.")
        if progress_callback and duration_sec > 0:
            progress = int(min(100.0, max(0.0, (float(segment.end) / duration_sec) * 100.0)))
            if progress != last_reported:
                last_reported = progress
                progress_callback(progress)
        text = segment.text.strip()
        if text:
            parts.append(text)
    if is_cancel_requested(cancel_check):
        raise InterruptedError("Trascrizione interrotta.")
    if progress_callback and last_reported < 100:
        progress_callback(100)
    return "\n".join(parts).strip()


def main() -> int:
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
    args = parser.parse_args()

    try:
        audio_path = args.input if args.input else find_single_audio_file(Path.cwd())
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
