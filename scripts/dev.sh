#!/usr/bin/env bash
# Run uninv in development mode: broker gateways + Python backend + desktop app.
# Works across macOS and Linux (bash/zsh).
#
# Usage:
#   ./scripts/dev.sh                  # gateways + backend + Tauri desktop app
#   ./scripts/dev.sh --browser        # gateways + backend + UI in web browser
#   ./scripts/dev.sh --services-only  # gateways + backend only (headless, no UI)
#   ./scripts/dev.sh --no-gateway     # backend + UI only (skip broker gateways)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BROWSER=false
SERVICES_ONLY=false
NO_GATEWAY=false

for arg in "$@"; do
    case "$arg" in
        -b|--browser|-Browser)
            BROWSER=true
            ;;
        -s|--services-only|--no-ui|-ServicesOnly)
            SERVICES_ONLY=true
            ;;
        --no-gateway|-NoGateway)
            NO_GATEWAY=true
            ;;
    esac
done

cleanup() {
    echo -e "\nShutting down all services and gateways cleanly..."
    # Terminate all background jobs launched by this script
    kill $(jobs -p) 2>/dev/null || true
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

echo "=========================================================="
echo "  UNINV: Unified Investing Development Environment"
echo "=========================================================="

# ---------------------------------------------------------
# 1. Start Broker Gateways
# ---------------------------------------------------------
if [ "$NO_GATEWAY" = false ]; then
    IBKR_DIR="$ROOT/gateways/ibkr-gateway"
    if [ -d "$IBKR_DIR" ]; then
        if nc -z 127.0.0.1 5000 2>/dev/null || lsof -i :5000 >/dev/null 2>&1; then
            echo -e "\033[32m[IBKR] Gateway already running on https://localhost:5000\033[0m"
        else
            echo -e "\033[36m[IBKR] Starting Client Portal Gateway on https://localhost:5000 ...\033[0m"
            chmod +x "$IBKR_DIR/bin/run.sh" 2>/dev/null || true
            (cd "$IBKR_DIR" && ./bin/run.sh root/conf.yaml) &
            sleep 2
            echo -e "\033[32m[IBKR] Gateway listening on https://localhost:5000\033[0m"
            echo -e "\033[33m       (Log in at https://localhost:5000 to authenticate 2FA)\033[0m"
        fi
    fi

    FUTU_DIR="$ROOT/gateways/futubull-gateway"
    if [ -d "$FUTU_DIR" ]; then
        if nc -z 127.0.0.1 11111 2>/dev/null || lsof -i :11111 >/dev/null 2>&1; then
            echo -e "\033[32m[Futubull] Gateway already running on 127.0.0.1:11111\033[0m"
        fi
    fi
fi

# ---------------------------------------------------------
# 2. Start Python FastAPI Backend (:8000)
# ---------------------------------------------------------
if nc -z 127.0.0.1 8000 2>/dev/null || lsof -i :8000 >/dev/null 2>&1; then
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
    echo "  All services and gateways running. Press Ctrl+C to stop."
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
