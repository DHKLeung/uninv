#!/usr/bin/env bash
# Run uninv in development mode: Python backend + desktop app.
# Works across macOS and Linux (bash/zsh).
#
# Usage:
#   ./scripts/dev.sh                  # backend + Tauri desktop app
#   ./scripts/dev.sh --browser        # backend + UI in web browser (no Rust build)
#   ./scripts/dev.sh --services-only  # backend only (headless, no UI)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BROWSER=false
SERVICES_ONLY=false

for arg in "$@"; do
    case "$arg" in
        -b|--browser|-Browser)
            BROWSER=true
            ;;
        -s|--services-only|--no-ui|-ServicesOnly)
            SERVICES_ONLY=true
            ;;
    esac
done

cleanup() {
    echo -e "\nShutting down cleanly..."
    kill $(jobs -p) 2>/dev/null || true
    echo "All processes stopped."
}
trap cleanup EXIT INT TERM

echo "=========================================================="
echo "  UNINV: Unified Investing Development Environment"
echo "=========================================================="

# ---------------------------------------------------------
# 1. Check Broker Gateways (IB Gateway / TWS, Futu OpenD)
# ---------------------------------------------------------
check_port() {
    local port=$1
    nc -z 127.0.0.1 "$port" 2>/dev/null || lsof -i :"$port" >/dev/null 2>&1
}

if check_port 4001; then
    echo -e "\033[32m[IBKR] IB Gateway Live detected on port 4001\033[0m"
elif check_port 4002; then
    echo -e "\033[32m[IBKR] IB Gateway Paper detected on port 4002\033[0m"
elif check_port 7496; then
    echo -e "\033[32m[IBKR] TWS Live API detected on port 7496\033[0m"
elif check_port 7497; then
    echo -e "\033[32m[IBKR] TWS Paper API detected on port 7497\033[0m"
else
    echo -e "\033[33m[IBKR] Notice: IB Gateway / TWS not detected on 4001/4002/7496/7497.\033[0m"
    echo -e "\033[33m       (Ensure IB Gateway or TWS is running with socket API enabled)\033[0m"
fi

if check_port 11111; then
    echo -e "\033[32m[Futu] OpenD API detected on port 11111\033[0m"
fi

# ---------------------------------------------------------
# 2. Start Python FastAPI Backend (:8000)
# ---------------------------------------------------------
if check_port 8000; then
    echo -e "\033[32m[Backend] FastAPI server already running on http://127.0.0.1:8000\033[0m"
else
    echo -e "\033[36m[Backend] Starting FastAPI server on http://127.0.0.1:8000 ...\033[0m"
    (cd "$ROOT/backend" && uv run uninv-backend --reload) &
    sleep 2
    echo -e "\033[32m[Backend] API ready at http://127.0.0.1:8000/docs\033[0m"
fi

# ---------------------------------------------------------
# 3. Start Frontend / UI
# ---------------------------------------------------------
if [ "$SERVICES_ONLY" = true ]; then
    echo "=========================================================="
    echo "  Backend running. Press Ctrl+C to stop."
    echo "=========================================================="
    wait
elif [ "$BROWSER" = true ]; then
    echo -e "\033[36m[UI] Serving UI on http://127.0.0.1:1420 (Ctrl+C to stop) ...\033[0m"
    (cd "$ROOT/backend" && uv run python -m http.server 1420 --bind 127.0.0.1 -d ../desktop/src) &
    sleep 1
    if command -v open >/dev/null 2>&1; then
        open "http://127.0.0.1:1420"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://127.0.0.1:1420"
    fi
    wait
else
    echo -e "\033[36m[UI] Launching Tauri desktop application ...\033[0m"
    cd "$ROOT/desktop/src-tauri"
    if cargo tauri --version >/dev/null 2>&1; then
        cargo tauri dev
    else
        cargo run
    fi
fi
