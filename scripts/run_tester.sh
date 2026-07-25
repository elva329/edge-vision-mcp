#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

GATEWAY_HOST="${GATEWAY_HOST:-192.168.1.10}"
OUTPUT="${OUTPUT:-test-report.json}"

echo "=== Edge Vision MCP - Testing Agent ==="
echo "Gateway: $GATEWAY_HOST"
echo "Report: $OUTPUT"

python3 "$PROJECT_DIR/src/testing/testing_agent.py" --host "$GATEWAY_HOST" --output "$OUTPUT"