#!/usr/bin/env bash
# run.sh
# Development checks for isolated frontend, Python/Rust runtime and native GUI.
set -euo pipefail
desktop="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../desktop" && pwd)"
runner="$desktop/../tests/run.sh"
suite=${1:-all}
if (( $# > 1 )); then printf 'Expected at most one suite.\n' >&2; exit 1; fi
case "$suite" in
    common|frontend|runtime|browser|native|packaging|all) ;;
    *) printf 'Usage: bash transcriber/tests/run.sh [common|frontend|runtime|browser|native|packaging|all]\n' >&2; exit 1 ;;
esac
cd -- "$desktop"

# Fail clearly without installing tools or system dependencies on the user's behalf.
require_tools() {
    local tool
    for tool in "$@"; do
        command -v "$tool" >/dev/null || { printf 'Missing developer tool: %s. See transcriber/desktop/README.md.\n' "$tool" >&2; return 1; }
    done
}

if [[ "$suite" == common || "$suite" == all ]]; then
    bash -n "$runner"
    if command -v shellcheck >/dev/null; then shellcheck "$runner"; else printf 'SKIP: ShellCheck is not installed.\n'; fi
    require_tools python3
    python3 -I ../tests/check_repository.py
fi
if [[ "$suite" == frontend || "$suite" == all ]]; then
    require_tools npm
    npm run format:check
    npm run lint
    npm run build
    npm test
fi
if [[ "$suite" == runtime || "$suite" == all ]]; then
    require_tools cargo
    [[ -x ../engine/.venv/bin/python ]] || { printf 'Run npm ci to prepare the internal Python engine.\n' >&2; exit 1; }
    ../engine/.venv/bin/python -m unittest discover -s ../engine -p 'test_*.py' -v
    cargo fmt --manifest-path src-tauri/Cargo.toml -- --check
    cargo clippy --locked --manifest-path src-tauri/Cargo.toml --no-default-features --all-targets -- -D warnings
    cargo test --locked --manifest-path src-tauri/Cargo.toml --no-default-features
fi
if [[ "$suite" == browser || "$suite" == all ]]; then
    require_tools npm
    npm run test:e2e
fi
if [[ "$suite" == native || "$suite" == all ]]; then
    if [[ $(uname -s) == Linux && -z ${DISPLAY:-} && -z ${WAYLAND_DISPLAY:-} ]]; then
        if command -v xvfb-run >/dev/null && command -v dbus-run-session >/dev/null; then
            LIBGL_ALWAYS_SOFTWARE=1 WEBKIT_DISABLE_COMPOSITING_MODE=1 xvfb-run -a dbus-run-session -- "$BASH" "$runner" native
        elif [[ "$suite" == native ]]; then printf 'Native checks require a display or xvfb-run and dbus-run-session.\n' >&2; exit 1
        else printf 'SKIP: no graphical session or headless native tools; CI runs the native check.\n'; fi
    else
        require_tools cargo npm python3
        cargo clippy --locked --manifest-path src-tauri/Cargo.toml --all-targets --features native-tests -- -D warnings
        npm run test:native
    fi
fi
if [[ "$suite" == packaging ]]; then
    require_tools node
    node packaging/prepare-engine.mjs
fi
