# Faster Whisper Transcriber user and developer guide

Faster Whisper Transcriber converts one local MP3 or MP4 recording into TXT using
faster-whisper. The application owns its internal Python process; no separate
service or local HTTP port is required.

## Getting started

The desktop targets Ubuntu 24.04+ and macOS 14+, x86_64/ARM64, with a graphical
session. Windows is not currently a native target. A GPU is optional. Memory,
disk usage and transcription time depend on the selected model and recording;
the application does not invent fixed hardware requirements.

Run from source using the root README. `npm ci` installs code dependencies and
prepares the internal Python environment. `npm run desktop` opens the application
and starts the worker automatically when needed. A missing model never blocks
opening the app. Published older Qt packages are separate from this Tauri rewrite;
no Tauri release is currently advertised.

## Transcribe and save

Choose or drop an MP3/MP4 file. Uppercase extensions are accepted. The application
handles one file and one operation at a time. Select Italian or English and a
reliability preset:

| Preset | Model | Decoding mode |
| --- | --- | --- |
| High | `large-v3` | accurate |
| Medium (default) | `small` | balanced |
| Low | `base` | fast |

These mappings and the original beam/best-of/patience/temperature settings are
preserved. Faster-whisper decodes at 16 kHz, sanitizes/clips samples, enables VAD
and returns segment text separated by newlines. Media decoding uses PyAV's bundled
FFmpeg libraries; no external ffmpeg command is invoked.

**Download model** is an explicit network action. Until the required local files
resolve, the model remains missing/incomplete and **Start transcription** stays
disabled. **Check model** refreshes availability if files were changed outside the
application. A download indicator is indeterminate; transcription percentages track
segment timestamps, not elapsed time or a predicted finish time. Loading/decoding
are shown separately and can take time before the first percentage.

**Stop** terminates/reaps the internal worker and releases controls after completion.
An interrupted download may leave Hub-managed partial files; a later explicit
download lets the Hub client recover them. Partial folders are not treated as ready.
An interrupted/failed transcription creates no new result. An earlier result stays
available until a replacement succeeds or is explicitly discarded.

**Save TXT** chooses a native destination and writes UTF-8 atomically. Saving never
starts automatically. A failed save leaves the transcription available and keeps
the previous destination contents. Closing with work in progress or an unsaved
result asks for a decision; cancelling the decision preserves the current state.
Completed transcripts are held in memory until saved; there is no transcript
history or automatic recovery after a machine/application crash.

## Models, data and privacy

Models live in the native application data directory under `models/faster-whisper`:

- Linux: `${XDG_DATA_HOME:-$HOME/.local/share}/io.github.etufarini.faster-whisper-transcriber/models/faster-whisper`.
- macOS: `~/Library/Application Support/io.github.etufarini.faster-whisper-transcriber/models/faster-whisper`.

When the previous macOS cache exists at `~/Library/Application Support/faster_whisper_transcriber/models/faster-whisper`,
the application reuses it in place. It does not copy, delete or merge models.
**Open model folder** opens the actual selected cache. The CLI retains its original
working-directory cache unless `--model-cache-dir` is supplied.

Only explicit model downloads contact the model host. Inspection/transcription
use local-files-only and worker offline mode. Telemetry is disabled in the worker.
Desktop model downloads are anonymous: they do not read or refresh personal
Hugging Face credentials, so an expired login cannot block a public preset model.
Audio paths and transcripts are not sent to a cloud transcription service. The
renderer loads local assets without external fonts or scripts. Worker diagnostics
are bounded and appear on failure; source development may print errors in its
terminal. Transcripts are never automatically written to browser storage.

Back up saved TXT files and the model cache as needed. Uninstalling an application
does not imply deleting those separate files. `npm run clean` never deletes them.

## Command-line interface

The original CLI remains available, sharing the engine. From the repository root:

```bash
transcriber/engine/.venv/bin/python transcriber/engine/transcription_cli.py --input recording.mp3 --model small --mode balanced --lang it --local-files-only
```

For the desktop cache, add `--model-cache-dir /absolute/path/to/the/cache`.
Omitting `--input` still requires exactly one supported file in the current
directory. `--output`, `--prompt`, `--model`, `--mode`, `--lang`, `--stdout` and
`--local-files-only` retain their meanings. Without `--local-files-only`, the CLI
retains its original ability to download its requested model. The GUI always
requires a separate download action. Exit codes remain 0 for success, 1 for an
input/transcription/storage failure, and 2 for empty output.

## Troubleshooting

- **npm ci cannot find Python:** install Python 3.12 or 3.13 with venv support,
  or prefix installation with `TRANSCRIBER_PYTHON=/absolute/path/to/python3.12`.
  Python 3.14 is not part of the supported source environment.
- **No matching binary wheel:** check Python version, operating system and CPU
  architecture. Installation uses binary wheels to avoid silently compiling
  inference dependencies. Intel macOS uses a separate compatible ONNX Runtime pin.
- **`metadata_errors` rejected when starting transcription:** update the source and
  rerun `npm --prefix transcriber/desktop ci`, then reopen the app. The locked PyAV
  18 dependency preserves the decoder API required by faster-whisper 1.2.1.
  Older packaged apps must be rebuilt to include the corrected dependencies.
- **Internal environment missing:** rerun `npm --prefix transcriber/desktop ci`.
  If an environment is damaged, remove only `transcriber/engine/.venv` and rerun
  installation. Do not remove user caches to fix development dependencies.
- **Model missing after an interrupted download:** use **Download model** again.
  The application verifies required files in the referenced local snapshot.
- **Expired Hugging Face token / 401 for a preset model:** the desktop uses anonymous
  downloads and needs no login. Restart after updating the source, or rebuild an
  older packaged application to include the corrected engine. Personal credentials
  remain available to CLI downloads of private models.
- **CUDA initialization failure:** CPU works without a GPU. CUDA execution needs
  the libraries required by the pinned CTranslate2 build; hardware and driver
  integration are separate from normal UI tests. If CUDA model initialization
  fails, the engine reports the reason and tries CPU initialization once.
- **Cannot save:** choose a writable destination. The in-memory result remains
  available for retry. Cancelling a save dialog does not mark it saved.
- **Browser preview cannot transcribe:** use `desktop` to open the native window.
  Browser fixtures are explicitly labelled simulations, never real transcription.

## Development and architecture

Use installed Node.js 22.13+, 24 or 26+, Rust 1.92+ with rustfmt/Clippy, Python
3.12/3.13 and the host Tauri prerequisites. Node 24/Python 3.12 are used in CI.
Do not install system packages or download private toolchains during application
startup. Source installation uses npm's documented `postinstall` hook; it can
access package registries, but never downloads models.

```text
React features → typed desktop service → Tauri commands → Rust validation/storage
                                                       → owned Python worker
                                                       → faster-whisper/CTranslate2
```

`src/services/desktop.ts` owns all native IPC, dialogs and lifecycle subscriptions.
Native commands are adapters; the Rust library validates/snapshots requests,
reserves a single operation, drains bounded pipes and owns cancellation/reaping.
One versioned JSON request produces progress plus one terminal response. Stderr
is diagnostic only. Python owns model cache interpretation and decoding/inference.
Preset definitions are shared from `engine/presets.json`.

See the [desktop developer README](../desktop/README.md) for all commands, protocol
limits and fixture contracts. Use `bash transcriber/tests/run.sh` for complete
checks, with optional `frontend`, `runtime`, `browser`, `native` or `packaging`.
The normal suite does not load models or use GPU/network inference. Real audio
quality and native OS dialogs still need separate integration/manual validation.

After final native validation, close the application and run:

```bash
npm --prefix transcriber/desktop run clean
```

It deletes only `src-tauri/target`, ignoring external target-directory overrides.
Python/npm dependencies, models, test evidence and packaging candidates remain.
Builds use limited debug information without incremental compilation to bound
development disk usage. The next native build recompiles removed artifacts.

## Packaging and releases

Build on the intended operating system/architecture after source setup:

```bash
npm --prefix transcriber/desktop run bundle
```

The wrapper freezes the worker with the pinned repository Python environment,
copies licenses/dependency provenance and builds Tauri with that complete resource
tree. The onedir layout avoids a second bootstrap process and repeated extraction.
The app finds the worker via native resources, independently of the working
directory; installed startup needs no Python, pip, Node or Rust from PATH.
Never distribute a plain `tauri build` output without the prepared engine.

Outputs are under `transcriber/desktop/packaging/generated/`:

- `engine-build/dist/transcriber-engine/`: frozen worker and required libraries.
- `build/release/bundle/deb/`: Linux Debian package.
- `build/release/bundle/macos/` and `build/release/bundle/dmg/`: macOS app and DMG.

`npm run bundle -- --debug` creates a debug candidate under `build/debug/` for
local verification. Preparation verifies the real worker using a temporary cache,
minimal system PATH and no models. Package verification extracts a Debian payload
or inspects the macOS app, runs its included worker and checks the GUI's embedded
assets/dynamic loader. Package candidates can be hundreds of megabytes because
Python, media codecs and inference libraries are included; models are additional.

The optional `packaging.yml` workflow creates native candidates and retains them
as artifacts. macOS support must be validated on a Mac; Linux checks do not prove
Mac compatibility. Production signing/notarization and OS picker permissions
require the platform tools and credentials. No App Store variant is introduced.

No command here tags, uploads or publishes a release. Preserve older releases.
Approve an exact version, commit SHA and notes before publishing a Tauri release.
