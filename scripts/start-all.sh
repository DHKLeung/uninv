#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

BACKEND_PID=""
cleanup() {
  echo ""
  echo "[Shutdown] Stopping background services ..."
  if [ -n "$BACKEND_PID" ]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  echo "[Shutdown] Complete."
}
trap cleanup EXIT INT TERM

echo "=========================================================="
echo "  UNINV: Starting Backend + Desktop Application"
echo "=========================================================="

echo "[Backend] Starting FastAPI server on http://127.0.0.1:7541 ..."
cd "${ROOT_DIR}/backend"
uv run uninv-backend --reload &
BACKEND_PID=$!

# Wait for backend health
for i in {1..20}; do
  if curl -s http://127.0.0.1:7541/health >/dev/null 2>&1; then
    echo "[Backend] API ready at http://127.0.0.1:7541/docs"
    break
  fi
  sleep 0.5
done

# Launch desktop
"${ROOT_DIR}/scripts/start-desktop.sh" "$@"
