#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Edge Vision MCP - Kiosk Mode ==="

export DISPLAY=:0
export XAUTHORITY=/home/edge/.Xauthority

python3 "$PROJECT_DIR/main.py" --host 0.0.0.0 --port 9000 &
PID=$!

sleep 2

chromium-browser \
  --noerrdialogs \
  --disable-infobars \
  --disable-features=TranslateUI \
  --disable-translate \
  --no-first-run \
  --kiosk \
  --window-size=1920,1080 \
  --window-position=0,0 \
  http://localhost:8080 2>/dev/null || \
google-chrome \
  --noerrdialogs \
  --disable-infobars \
  --disable-features=TranslateUI \
  --disable-translate \
  --no-first-run \
  --kiosk \
  --window-size=1920,1080 \
  --window-position=0,0 \
  http://localhost:8080 2>/dev/null || \
firefox \
  --kiosk \
  --width 1920 \
  --height 1080 \
  http://localhost:8080

wait $PID
