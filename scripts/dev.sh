#!/usr/bin/env bash
# Run uninv in development mode: Python backend + desktop app.
# Works on macOS and Linux (bash/zsh).
#
# Usage:
#   ./scripts/dev.sh           # backend + Tauri desktop app
#   ./scripts/dev.sh --browser # backend + UI in web browser (no Rust build needed)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BROWSER=false
for arg in "$@"; do
    case "$arg" in
        -b|--browser|-Browser)
            BROWSER=true
            ;;
    esac
done

cleanup() {
    echo -e "\nStopping backend and frontend processes..."
    # Terminate all background jobs launched by this script
    kill $(jobs -p) 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on http://127.0.0.1:8000 ..."
(cd "$ROOT/backend" && uv run uninv-backend --reload) &

sleep 2

if [ "$BROWSER" = true ]; then
    echo "Serving UI on http://127.0.0.1:1420 (Ctrl+C to stop) ..."
    (cd "$ROOT/backend" && uv run python -m http.server 1420 --bind 127.0.0.1 -d ../desktop/src) &
    sleep 1
    if command -v open >/dev/null 2>&1; then
        open "http://127.0.0.1:1420"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://127.0.0.1:1420"
    fi
    wait
else
    cd "$ROOT/desktop/src-tauri"
    if cargo tauri --version >/dev/null 2>&1; then
        cargo tauri dev
    else
        cargo run
    fi
fi
