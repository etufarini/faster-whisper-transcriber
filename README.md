# Faster Whisper Transcriber

Local `.mp3` and `.mp4` transcription with [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

This repository provides:
- a desktop GUI for interactive use;
- a small CLI for automation;
- a PyInstaller spec for building a macOS `.app`.

Core properties:
- fully local processing;
- no cloud upload;
- explicit model download and cache paths;
- simple preset-based operation.

## Requirements

- Python `3.10+`
- `faster-whisper`
- `numpy`
- `PySide6` for the GUI

Install dependencies:

```bash
python3 -m pip install faster-whisper numpy PySide6
```

## Quick Start

Clone the repository and run the GUI:

```bash
git clone <REPO_URL>
cd faster-whisper-transcriber
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install faster-whisper numpy PySide6
python3 transcription_gui.py
```

## GUI

The GUI is the main interface.

What it does:
- lets you pick or drag-and-drop an `.mp3` or `.mp4` file;
- lets you choose a preset and language;
- checks whether the required model is available;
- runs transcription locally with progress reporting;
- lets you save the resulting text.

Presets:
- `High` -> `large-v3` + `accurate`
- `Medium` -> `small` + `balanced`
- `Low` -> `base` + `fast`

Typical flow:
1. Select or drop an input file.
2. Choose a preset and language.
3. Click `Check model` if the model is missing.
4. Click `Start transcription`.
5. Click `Download transcription` to save the result.

Operational notes:
- transcription starts only when the selected model is already available;
- bundled models are preferred when the app is run from a packaged macOS app;
- GUI startup failures are logged to `~/Library/Logs/faster_whisper_transcriber/startup.log`.

## CLI

The CLI is intended for direct and scriptable use.

If the current directory contains exactly one supported input file:

```bash
python3 transcription_cli.py
```

Common examples:

```bash
python3 transcription_cli.py --input audio.mp3 --model base --mode fast --lang it
python3 transcription_cli.py --input audio.mp3 --model small --mode balanced --lang it
python3 transcription_cli.py --input audio.mp3 --model large-v3 --mode accurate --lang it
python3 transcription_cli.py --input audio.mp3 --local-files-only
python3 transcription_cli.py --input audio.mp3 --stdout
```

Main options:
- `--input`: input `.mp3` or `.mp4` file;
- `--output`: output `.txt` file, defaulting to the input basename;
- `--lang`: language code such as `it` or `en`;
- `--prompt`: optional contextual prompt;
- `--model`: Whisper model name;
- `--mode`: `fast`, `balanced`, or `accurate`;
- `--model-cache-dir`: model cache directory;
- `--local-files-only`: refuse model downloads;
- `--stdout`: also print the transcription to standard output.

## Model Cache

Default cache locations:
- GUI: `~/Library/Application Support/faster_whisper_transcriber/models/faster-whisper`
- CLI: `./models/faster-whisper`

## Prebuilt macOS App

Prebuilt `.app.zip` releases are published on the repository [Releases](../../releases) page.

Recommended install flow:
1. Download the latest `.app.zip`.
2. Unzip it.
3. Move `Faster Whisper Transcriber.app` to `Applications`.
4. On first launch, right-click and choose `Open`.

## Build macOS App

Build the app with PyInstaller:

```bash
python3 -m pip install pyinstaller
PYINSTALLER_CONFIG_DIR=.pyinstaller python3 -m PyInstaller -y faster_whisper_transcriber.spec
```

Main outputs:
- `dist/Faster Whisper Transcriber.app`
- `dist/FasterWhisperTranscriber/`

To bundle already-downloaded models into the app:

```bash
mkdir -p "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models"
cp -R "models/faster-whisper" "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models/faster-whisper"
rm -rf "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models/faster-whisper/.locks"
codesign --force --deep --sign - "dist/Faster Whisper Transcriber.app"
```

Distribution notes:
- Gatekeeper may block the first launch until the app is opened explicitly;
- public distribution should use proper Apple code signing and notarization.

## Project Layout

- `transcription_core.py`: shared transcription and model-cache logic
- `transcription_gui.py`: PySide6 desktop application
- `transcription_cli.py`: command-line entry point
- `faster_whisper_transcriber.spec`: PyInstaller build spec
- `resources/`: icons and bundle assets
- `screenshots/`: GUI screenshots

## License

Apache License 2.0. See [LICENSE](LICENSE).
