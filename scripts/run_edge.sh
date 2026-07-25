#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Edge Vision MCP - Edge Device Launcher ==="
echo "Starting MCP Gateway..."

python3 "$PROJECT_DIR/main.py" --host 0.0.0.0 --port 9000