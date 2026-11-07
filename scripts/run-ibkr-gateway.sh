#!/usr/bin/env bash
# Starts the IBKR Client Portal Gateway on macOS and Linux.
# Once started, open https://localhost:5000 in your browser to log in with 2FA.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IBKR_DIR="$ROOT/gateways/ibkr-gateway"

if [ ! -d "$IBKR_DIR" ]; then
    echo "Error: IBKR Gateway directory not found at: $IBKR_DIR" >&2
    exit 1
fi

echo "=========================================================="
echo "  Starting IBKR Client Portal Gateway"
echo "  URL: https://localhost:5000"
echo "  Keep this window open while using uninv with IBKR."
echo "=========================================================="

chmod +x "$IBKR_DIR/bin/run.sh" 2>/dev/null || true
cd "$IBKR_DIR"
exec ./bin/run.sh root/conf.yaml
