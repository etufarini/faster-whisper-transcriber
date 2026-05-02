#!/usr/bin/env python3
"""
transcription_core.py

Shared transcription and model-cache helpers for the faster-whisper CLI and GUI.
This module keeps the core transcription path in one place so the entry points
stay small, explicit, and easy to reason about.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional, Sequence


AUDIO_SAMPLE_RATE = 16000
SUPPORTED_INPUT_EXTENSIONS = (".mp3", ".mp4")
MODE_DECODING_PARAMS: dict[str, tuple[int, int, int, list[float]]] = {
    "fast": (2, 2, 1, [0.0]),
    "balanced": (5, 5, 1, [0.0, 0.2]),
    "accurate": (8, 8, 2, [0.0, 0.2, 0.4]),
}


# Return decoding parameters for the requested speed/quality mode.
def get_mode_decoding_params(mode: str) -> tuple[int, int, int, list[float]]:
    return MODE_DECODING_PARAMS.get(mode, MODE_DECODING_PARAMS["balanced"])


# Return True when the caller requested cancellation.
def is_cancel_requested(cancel_check: Optional[Callable[[], bool]]) -> bool:
    return bool(cancel_check and cancel_check())


# Return the only supported media file in the working directory or fail explicitly.
def find_single_audio_file(cwd: Path) -> Path:
    candidates = sorted(
        path
        for path in cwd.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
    )
    if not candidates:
        raise FileNotFoundError(
            "Nessun file audio/video supportato trovato nella cartella corrente (.mp3, .mp4)."
        )
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise RuntimeError(
            f"Trovati più file supportati ({names}). Usa --input per specificarne uno."
        )
    return candidates[0]


# Return True when the faster-whisper cache already contains the requested model.
def model_exists_in_cache(model_name: str, cache_dir: Path) -> bool:
    repo_dir = cache_dir / f"models--Systran--faster-whisper-{model_name}"
    return repo_dir.exists()


# Download each missing model by constructing it once through faster-whisper.
def download_missing_models(model_names: Sequence[str], cache_dir: Path) -> None:
    from faster_whisper import WhisperModel  # type: ignore

    cache_dir.mkdir(parents=True, exist_ok=True)
    for model_name in model_names:
        if model_exists_in_cache(model_name, cache_dir):
            continue
        _ = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8_float32",
            download_root=str(cache_dir),
            local_files_only=False,
        )


# Decode audio and normalize amplitudes before computing the mel spectrogram.
def decode_audio_for_transcription(audio_path: Path):
    import numpy as np
    from faster_whisper.audio import decode_audio  # type: ignore

    raw_audio = decode_audio(str(audio_path), sampling_rate=AUDIO_SAMPLE_RATE)
    audio = np.asarray(raw_audio, dtype=np.float32)
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        audio = audio / peak
    return np.clip(audio, -1.0, 1.0)


# Transcribe a local media file with faster-whisper and optional cancellation/progress hooks.
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
    audio = decode_audio_for_transcription(audio_path)
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
