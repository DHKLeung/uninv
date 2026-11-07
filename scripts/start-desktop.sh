#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

BROWSER_MODE=false
for arg in "$@"; do
  case "$arg" in
    --browser|-b) BROWSER_MODE=true ;;
  esac
done

echo "=========================================================="
echo "  UNINV: Starting Desktop Application"
echo "=========================================================="

if [ "$BROWSER_MODE" = true ]; then
  echo "[UI] Serving web UI on http://127.0.0.1:1420 ..."
  cd "${ROOT_DIR}/backend"
  uv run python -m http.server 1420 --bind 127.0.0.1 -d "${ROOT_DIR}/desktop/src"
else
  echo "[UI] Launching Tauri desktop shell ..."
  cd "${ROOT_DIR}/desktop/src-tauri"
  if command -v cargo-tauri >/dev/null 2>&1; then
    cargo tauri dev
  else
    cargo run
  fi
fi
