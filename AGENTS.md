# Faster Whisper Transcriber development instructions

## Purpose and boundaries

Faster Whisper Transcriber is a local MP3/MP4 transcription application using
faster-whisper. Target Linux and macOS with Tauri 2, React and TypeScript. Preserve
the High/Medium/Low presets, Italian/English selection, explicit model downloads,
progress, cancellation and TXT exports. Keep the Python CLI for automation.
Do not introduce cloud transcription, a persistent server, history or queues
without an approved scope. Comments, UI messages and documentation are in English.
Development and required checks need no GPU, model weights or inference service.
Real inference and hardware checks are separate integration diagnostics.

## Human-readable code

Write small, direct programs for human maintainers. Prefer explicit control flow,
descriptive names, focused modules and locally understandable invariants. Avoid
speculative abstractions, frameworks, dependencies and unrelated refactors.
Before editing, identify constraints, invariants, the simplest change and its risk.
Make ownership and failure paths explicit. Keep JSX multiline and operations named.

Every named function/method needs a purpose/behavior comment immediately above it.
Begin each source file with one multiline comment containing its name and purpose.
Use consecutive comment lines for shell/TOML. JSON and generated lockfiles cannot
contain comments. Explain guarantees and trade-offs, not obvious statements.
Do not retain commented-out code or stale TODO/FIXME notes. After development,
remove redundant code/dependencies within the approved scope, report cleanup,
and explain any necessary complexity. Keep builds warning-free.

## Repository structure

Keep the visible root limited to README.md, AGENTS.md, LICENSE and transcriber/.
Keep desktop code in transcriber/desktop/, Python engine/CLI in transcriber/engine/,
the runner in transcriber/tests/run.sh and documentation in transcriber/docs/.
Frontend modules separate app composition, features, shared controls and domain
data. All IPC, native dialogs and window events belong in services/desktop.ts.
Keep commands thin. Rust owns validation, paths, exports, operation state, process
supervision and shutdown. Native logic must be testable without the desktop feature.

Python is an internal engine, not an independently managed service. Use one child
per operation and a versioned JSON-lines protocol over pipes. Worker stdout is
protocol only; stderr is diagnostics. Start programs directly with argument arrays,
never shell commands. Resolve packaged resources independently of the working
directory. Introduce platform modules only for actual platform differences.

## Configuration and compatibility

Preserve preset/model/decoding mappings and CLI flags. Share owning definitions
with frontend fixtures rather than copying rules. Validate at native and engine
boundaries. Snapshot options at start. Never infer CUDA availability solely from
CUDA_VISIBLE_DEVICES; CPU operation must remain possible without CUDA.
Use platform-appropriate storage and reuse the existing macOS model cache without
copying/merging it. Resolve required files before declaring a model available.
Transcription is local-files-only; downloading is a separate explicit action.
Keep original data on failures and write TXT exports atomically.

## Desktop behavior and data

Enforce one download/transcription operation at a time in Rust. Identify each
operation and reject stale events. Retain child ownership through cancellation
until exit and reaping. Clean up only owned children. Ask before discarding an
unsaved result or interrupting active work. Report missing native services,
dependencies/models, decoding errors, crashes and export failures explicitly.
Fixtures are development-only, visibly labelled and excluded from release assets.
Preserve keyboard access, focus, contrast and reduced motion. Keep the interface
focused on choosing a file/options, preparing a model, transcribing and saving.

## Development and distribution

Use installed Node/npm, Rust, Python and platform prerequisites. The local flow is
npm --prefix transcriber/desktop ci followed by npm --prefix transcriber/desktop
run desktop. The install hook prepares a local Python environment with pinned
dependencies. It must not install system packages, fetch toolchains or load/download
models. Document the Python prerequisite. Rust launches the engine automatically;
no separate service command or backend selection is needed.
Packages include Python, faster-whisper, native libraries, licenses and dependency
provenance. Installed startup must not invoke pip, compile or need Python/Node/Rust
from PATH. Build on matching operating systems/architectures and verify resources
and dynamic dependencies. Ad hoc signing is not signing for public distribution
or notarization. Preparing packages does not publish them.

## Verification

Use bash transcriber/tests/run.sh as the complete entry point. Keep focused common,
frontend, runtime, browser, native and packaging suites. Use temporary directories,
synthetic data and fake workers; never personal configuration/models, system
package installation or inference/model services. Support macOS Bash 3.2 and report
skips. Test protocol, validation, atomic storage and process ownership at the
cheapest effective level; browser tests cover renderer flows, native tests actual
WebView/IPC/processes. Cover cancellation, crashes, incomplete models, paths with
spaces and failed writes. Mocks do not establish inference quality or OS permissions.

Keep one required workflow with three jobs: Linux frontend/browser, native Linux
and native macOS. Keep native smoke paths short. Packaging is separate and must
be checked when its boundaries change. Retain failure evidence. Prefer readiness
conditions to fixed sleeps/retries. Run format/lint/types, rustfmt/Clippy with denied
warnings and affected suites first. Never weaken assertions or bypass CI failures.
Use limited debug information and disable incremental development compilation.
After final native checks, close processes and run npm --prefix transcriber/desktop
run clean. Clean only src-tauri/target, ignoring external target overrides. Preserve
Python environments, models, user data, npm dependencies, evidence and packaging
candidates. Do not immediately rebuild or clean between dependent CI checks.

## Documentation and releases

Follow Straggler's README structure: introduction and human-maintainer principle,
availability/requirements, run from source, first launch, and a link to the guide.
Keep architecture, CLI, development, data, troubleshooting and packaging in
transcriber/docs/guide.md. The desktop README documents commands and test contracts.
Use real screenshots without fabricated readiness/transcriptions or private paths.
Keep the existing product identity. main is development; merging does not publish.
Do not advertise Tauri packages before publication. Preserve existing tags/releases.
Approve the exact version, candidate SHA and notes before tagging/publishing.
Do not delete remote branches without approval.

## Approval

Every modification requires explicit approval of the proposed scope, including
instructions, renames and deletions. Existing approval persists for the presented
work and included cleanup; do not repeatedly request it. Read-only investigation
is allowed. Present out-of-scope additions before applying them. The approved
rewrite includes npm-integrated Python, docs, tests, packaging and removal of Qt.
