# Faster Whisper Transcriber

Desktop app (GUI) for local `.mp3` and `.mp4` transcription using [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

Project priorities:
- Installable macOS application (`.app`)
- Simple, user-friendly GUI
- Optional CLI mode for automation

## GUI Preview

<p align="center">
  <a href="screenshots/app-first-screen.png">
    <img src="screenshots/app-first-screen.png" alt="Faster Whisper Transcriber GUI" width="860" />
  </a>
</p>

Click the screenshot to open the full-resolution image.

## Why Use the GUI

- No cloud upload: fully local processing
- Guided workflow: file selection -> preset -> start -> export text
- Model check/download directly from the app
- Progress bar + stop transcription action

Available GUI presets:
- `High` -> `large-v3` + `accurate`
- `Medium` -> `small` + `balanced`
- `Low` -> `base` + `fast`

## Download Prebuilt App

You can download the zipped macOS app (`.app.zip`) directly from the repository [Releases](../../releases) page.

Recommended install flow:
1. Open [Releases](../../releases)
2. Download the latest `.app.zip` asset
3. Unzip and move `Faster Whisper Transcriber.app` to `Applications`
4. First launch on macOS: right-click -> `Open`

## GUI Quick Start (Recommended)

```bash
git clone <REPO_URL>
cd faster-whisper-transcriber-ai
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install faster-whisper numpy PySide6
python3 transcription_gui.py
```

## Installable macOS App (.app)

Build with PyInstaller using `faster_whisper_transcriber.spec`:

```bash
python3 -m pip install pyinstaller
PYINSTALLER_CONFIG_DIR=.pyinstaller python3 -m PyInstaller -y faster_whisper_transcriber.spec
```

Main outputs:
- `dist/Faster Whisper Transcriber.app`
- `dist/FasterWhisperTranscriber/`

To include models inside the bundle (optional, for offline distribution):

```bash
mkdir -p "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models"
cp -R "models/faster-whisper" "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models/faster-whisper"
rm -rf "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models/faster-whisper/.locks"
codesign --force --deep --sign - "dist/Faster Whisper Transcriber.app"
```

macOS distribution notes:
- On first launch, Gatekeeper may block the app: right-click -> `Open`
- For public distribution, use Apple code signing + notarization

## GUI Usage

1. Select or drag-and-drop an `.mp3/.mp4` file
2. Choose preset (`High`, `Medium`, `Low`) and language (`Italian`, `English`)
3. Click `Check model` if the selected model is missing
4. Click `Start transcription`
5. Save the result with `Download transcription`

Useful notes:
- The GUI starts transcription only if the required model is available in cache
- When running from a macOS bundle, it checks bundled models first
- If the GUI crashes at startup, check: `~/Library/Logs/faster_whisper_transcriber/startup.log`

## Requirements

- Python `3.10+`
- Python dependencies:

```bash
python3 -m pip install faster-whisper numpy PySide6
```

## Model Cache

Used paths:
- GUI (user): `~/Library/Application Support/faster_whisper_transcriber/models/faster-whisper`
- CLI (default): `./models/faster-whisper`

## CLI (Optional)

Script: `transcription_cli.py`

If there is only one supported file in the current folder (`.mp3/.mp4`):

```bash
python3 transcription_cli.py
```

Examples:

```bash
# Fast
python3 transcription_cli.py --input audio.mp3 --model base --mode fast --lang it

# Balanced
python3 transcription_cli.py --input audio.mp3 --model small --mode balanced --lang it

# Highest accuracy
python3 transcription_cli.py --input audio.mp3 --model large-v3 --mode accurate --lang it

# Use only already-downloaded models (strict offline mode)
python3 transcription_cli.py --input audio.mp3 --local-files-only

# Also print output to stdout
python3 transcription_cli.py --input audio.mp3 --stdout
```

Main parameters:
- `--input`: `.mp3/.mp4` input file
- `--output`: `.txt` output file (default: same name as input)
- `--lang`: language (`it`, `en`, ...)
- `--prompt`: optional contextual prompt
- `--model`: `tiny|base|small|medium|large-v3`
- `--mode`: `fast|balanced|accurate`
- `--model-cache-dir`: model cache directory
- `--local-files-only`: do not download models
- `--stdout`: print transcription to terminal

## Project Structure

- `transcription_gui.py`: PySide6 desktop app
- `transcription_cli.py`: CLI transcription tool
- `faster_whisper_transcriber.spec`: PyInstaller build spec
- `resources/`: icons and assets
- `screenshots/`: GUI screenshots

## License

Apache License 2.0. See [LICENSE](LICENSE).
