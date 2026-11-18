# Desktop development

Use this page for commands and test contracts. The
[user and developer guide](../docs/guide.md) covers behavior, the CLI, storage,
architecture, troubleshooting and packaging.

Keep React composition, features, domain data and the typed desktop service
separate. Rust owns native validation, storage and the lifetime of its Python
children. The Python worker owns inference and local model-cache inspection.

## Setup and commands

From the repository root:

```bash
npm --prefix transcriber/desktop ci
npm --prefix transcriber/desktop run desktop
```

The install hook creates `transcriber/engine/.venv` and installs
`engine/requirements.lock` with hash checks and binary wheels. It uses an existing
Python 3.12 or 3.13, preferring 3.12. `TRANSCRIBER_PYTHON` accepts an explicit
interpreter path during installation. No toolchain, system package or model is
installed automatically. Python runs as an internal child, never an HTTP service.

Run these commands from `transcriber/desktop`:

| Command | Purpose |
| --- | --- |
| `npm run desktop` | Start Vite and the native Tauri application |
| `npm run clean` | Remove only the repository's Rust `src-tauri/target` |
| `npm run dev` | Open a loopback browser preview with native actions unavailable |
| `npm run build` | Check TypeScript and build production assets |
| `npm run bundle` | Freeze Python, build Tauri, and verify the actual native package |
| `npm run format:check` | Check source formatting |
| `npm run lint` | Check frontend and JavaScript tooling |
| `npm run typecheck` | Check TypeScript without building |
| `npm test` | Run frontend domain tests |
| `npm run test:runtime` | Run Rust process/storage tests without WebKit |
| `npm run test:e2e` | Run renderer flows in WebKit |
| `npm run test:native` | Build and exercise the actual window with a fake worker |

## Build artifacts

After final validation, close development processes and run:

```bash
npm --prefix transcriber/desktop run clean
```

Cleanup deliberately ignores an external `CARGO_TARGET_DIR` and removes only
`src-tauri/target`. Preserve `packaging/generated`, test evidence, models, `.venv`
and user data. Packaging uses `packaging/generated/build` independently of normal
native tests and cleanup. Debug builds use limited debug information and no
incremental compilation; rebuilding after cleanup takes longer.

## Test suites

Use `bash transcriber/tests/run.sh` from the repository root. Add a suite name to
focus checks. All ordinary checks need no models, GPU or inference service.

| Suite | Checks |
| --- | --- |
| `common` | Bash syntax/ShellCheck, Python source syntax, production fixture exclusion |
| `frontend` | Format, lint, TypeScript/build and frontend unit tests |
| `runtime` | Python engine tests, rustfmt, denied Clippy warnings and Rust integration tests |
| `browser` | WebKit renderer interactions with labelled fake services |
| `native` | Native Clippy and the actual window, IPC, exports and owned child cleanup |
| `packaging` | Build/import the real frozen worker outside the source tree |
| `all` | Common, frontend, runtime, browser and native checks |

Frontend/browser checks need no Rust libraries. Runtime checks need the Python
environment created by `npm ci`, Rust and the host linker, but no WebKit. Native
checks require the host Tauri prerequisites and a display. Headless Linux uses
`xvfb-run` and a private D-Bus session when installed. Explicit `native` fails if
neither is available; `all` reports a skip. CI always supplies a display.

Install WebKit explicitly before browser checks, from this directory:

```bash
npm exec -- playwright install webkit
```

Install any Playwright system dependencies explicitly during development setup.
The runner never installs system packages. CI retains browser/native failure
evidence under `test-results/` and uses three jobs: shared Linux renderer checks,
native Linux and native macOS. Native tests run the copied application from a
temporary directory. Real OS file-picker interaction, macOS signing/permissions
and actual transcription remain platform/integration checks.

## Worker and fixture contracts

`engine/presets.json` is the preset source for Python, native validation and frontend
fixtures. The worker reads one JSON line from stdin, limited to 64 KiB. It emits
version 1 JSON lines with operation `id` and `event` (`progress`, `result`, `error`).
Messages are limited to 32 MiB. Stdout is protocol-only; stderr is bounded native
diagnostics. A valid terminal message and a successful process exit are both
required. Inspection has a 30-second deadline; inference/download have no fixed
time limit and remain cancellable. The worker must exit within five seconds after
its result. Rust retains/reaps the owned child on every exit path.

Tests use temporary user directories and fake workers. Browser fixtures load only
when Vite serves an explicit scenario; release assets exclude them. Preview URLs:

```text
http://127.0.0.1:1420/?scenario=ready
http://127.0.0.1:1420/?scenario=missing
http://127.0.0.1:1420/?scenario=slow
http://127.0.0.1:1420/?scenario=failure
http://127.0.0.1:1420/?scenario=save-error
```

All are labelled simulations. They do not prove inference quality or native
dialog behavior. Python tests exercise actual local Hub snapshot resolution,
normalization and decoding of generated MP3/MP4 files without model weights or
network access. The upstream contracts are
[faster-whisper 1.2.1](https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1),
[Tauri IPC channels](https://v2.tauri.app/develop/calling-frontend/#channels) and
[PyInstaller onedir bundles](https://pyinstaller.org/en/stable/operating-mode.html).

## Dependency maintenance

Commit npm/Cargo lockfiles and the hash-verified universal Python lock. Regenerate
the latter deliberately with `uv pip compile engine/pyproject.toml --extra packaging
--universal --python-version 3.12 --generate-hashes --output-file engine/requirements.lock`
from `transcriber/`; uv is a maintainer tool, not an installation prerequisite.
Intel macOS pins ONNX Runtime 1.23.2 because newer releases lack Intel wheels.
The application minimum is macOS 14 because of the pinned ARM64 media wheels.
Keep PyAV below 19 while using faster-whisper 1.2.1: its decoder still passes
`metadata_errors` to `av.open`. The real MP3/MP4 decoding test must pass before
lifting this compatibility constraint, even when dependency resolution succeeds.
See the [PyAV 19 API removals](https://github.com/PyAV-Org/PyAV/blob/v19.0.2/CHANGELOG.rst).

Review `npm audit`, `npm outdated` and `npm ls --all` after dependency updates.
The scoped minimatch overrides follow Straggler's toolchain workaround; reassess
them when updating their parents. `allowScripts` approves the pinned esbuild
install script. Do not apply automatic major downgrades or suppress audit results.

The current dev-tool graph reports
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), an unpatched
picomatch glob-pattern ReDoS advisory, including propagated parent alerts.
Its glob callers here operate on repository-controlled build/test patterns; it
is absent from production dependencies (`npm audit --omit=dev`). Recheck upstream
when updating tooling; this is not a claim that the dependency itself is fixed.

## Packaging commands

See the [packaging guide](../docs/guide.md#packaging-and-releases). A plain Tauri
build does not prepare the internal engine; `npm run bundle` does. Prepared workers,
licenses, provenance and native candidates stay under `packaging/generated`.
Source setup and packaging download code dependencies, never model weights.
