# Edge Vision MCP

Python FastAPI backend + React AGUI frontend for simulated edge vision monitoring. 16 mock cameras, mock TPU inference, rule-based alerting.

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm 9+

## Installation

```bash
# Clone and install Python deps
pip install -r requirements.txt

# Install AGUI frontend deps
cd src/agui && npm install && cd ../..
```

## Running

### Development (with hot reload)

```bash
# Terminal 1 — start backend
python3 main.py

# Terminal 2 — start frontend dev server with HMR
cd src/agui && npm run dev
```

Then open **http://localhost:5173**. The Vite dev server proxies API (`/rpc`) and WebSocket (`/ws`) requests to the backend on port 8080. UI changes reload automatically; no hard refresh needed.

### Production

```bash
# Build frontend, then start backend (serves API on :9000 + frontend on :8080)
cd src/agui && npm run build && cd ../..
python3 main.py
```

Or use the Makefile:

```bash
make dev && make build && make run-edge
```

Then open http://localhost:8080.

## Configuration

Edit `src/agui/src/App.jsx` to change `CAMERAS` count or polling interval. The backend hosts the frontend at `/` on port 8080 and exposes MCP tools over TCP on port 9000.

## Demo

Quick 3–5 minute demo for interviews or reviews.

### Terminal 1 — start backend
```bash
python3 main.py
```

### Terminal 2 — start frontend (auto-reload)
```bash
cd src/agui && npm run dev
```

### Open browser
- **Development**: http://localhost:5173
- **Production build**: http://localhost:8080

### Demo flow

1. **Dashboard**
   - Open browser to the dev/prod URL
   - Show the **4×4 camera grid** with live snapshots updating every second
   - Point out **live alert panel** on the right — alerts appear automatically (`zone_crossing`, `object_left`)
   - Show **metrics bar** (CPU / TPU / RAM / Protocol)

2. **Config tab**
   - Click **Config** in the top nav
   - Walk through each card and make live changes (see table below)
   - Switch back to **Dashboard** to show the impact of those changes

3. **WebSocket events**
   - Open browser DevTools → Console → Network → WS
   - Show real-time frames: `frame_update`, alerts: `alert`, metrics: `metrics`

4. **Testing agent**
   - Run `python3 src/testing/testing_agent.py --host 127.0.0.1 --port 9000 --output /tmp/test-report.json`
   - Show JSON pass/fail report

### Config tab: actions and expected results

| Section | Action | Steps | Expected result |
|---------|--------|-------|-----------------|
| **Cameras** | Stop a camera | Click **Stop** on `cam_00` | Camera chip turns gray (`off`); Dashboard stops receiving frames for `cam_00` |
| **Cameras** | Start a camera | Click **Start** on a stopped camera | Camera chip turns cyan (`live`); Dashboard resumes frames for that camera |
| **Rules** | Create a `zone_crossing` rule | Fill form → Name: `test_rule`, Camera: `cam_00`, Type: `zone_crossing`, Zone: `[[100,100],[300,100],[300,300],[100,300]]`, Threshold: `10` → **Create** | Rule appears in the Rules list as `On`; Alert panel may show alerts when inference detects objects in that zone |
| **Rule Server** | Create a `loitering` rule | Type: `loitering`, Camera: `cam_01`, Threshold: `5` → **Create** | Rule appears; if an object stays in zone > 5s, a loitering alert is emitted |
| **Rule Server** | Create an `object_left` rule | Type: `object_left`, Camera: `cam_02` → **Create** | Rule appears; alerts when an object is left behind without a person |
| **Models** | View model list | Look at the Models card | Shows `mobilenet_v2_edge` and `yolo_nas_edge` with mocked latency ranges |
| **Protocol** | View protocol info | Look at the Protocol card | Shows supported versions `2025-11, 2026`, default `2026`, session-based `Yes`, stateless `Yes` |
| **Protocol info** | No direct edit | Read-only | Confirms gateway is ready for both legacy (`2025-11`) and modern (`2026`) MCP clients |

### Verify with curl
```bash
# List cameras
curl -s -X POST http://localhost:8080/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_cameras"}}' | python3 -m json.tool

# Get frame from camera 0
curl -s -X POST http://localhost:8080/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_stream_frame","arguments":{"camera_id":"cam_00"}}}' | python3 -m json.tool

# Run inference
curl -s -X POST http://localhost:8080/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"run_inference","arguments":{"image_data":"test"}}}' | python3 -m json.tool

# Protocol info
curl -s -X POST http://localhost:8080/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_protocol_info"}}' | python3 -m json.tool
```

## Testing

### pytest suites
```bash
# Install test dependency
pip install pytest-asyncio==0.23.7

# Run all tests
PYTHONPATH=/Users/Elva/Desktop/Job\ Application/Novos/edge-vision-mcp pytest tests/ -v
```

### Testing agent (LAN)
```bash
# From another device or same host
python3 src/testing/testing_agent.py --host 127.0.0.1 --port 9000 --output /tmp/test-report.json
cat /tmp/test-report.json | python3 -m json.tool
```

Environment variables:
- `GATEWAY_HOST` — Edge device IP (default `192.168.1.10`)
- `OUTPUT` — Report file path (default `test-report.json`)

## Project Structure

- `main.py` — Entry point; starts MCP Gateway and aiohttp frontend server
- `src/gateway/server.py` — JSON-RPC 2.0 TCP gateway with session management and rate limiting
- `src/servers/` — Stream, Inference, and Rule MCP servers with circular JPEG buffers
- `src/agui/` — React frontend (Vite) with dashboard and config views
- `src/testing/testing_agent.py` — Compliance, stress, and security test runner
- `scripts/` — Launch scripts for edge device and kiosk, systemd service file

## Deployment

This project is deployed as a single Docker container. The frontend is built into the image and served by the Python backend.

### Prerequisites

- Docker 20+
- Fly CLI (for Fly.io) or access to Render/Docker Hub

### Deploy with Fly.io

```bash
fly auth login
fly launch --no-deploy
fly deploy
```

### Deploy with Render

1. Connect this repo in the Render dashboard
2. Set **Environment** to Docker
3. Set **Start Command**:
   ```bash
   python3 main.py --host 0.0.0.0 --port 9000
   ```
4. Render will auto-build using the Dockerfile

### Deploy with Docker

```bash
docker build -t edge-vision-mcp .
docker run -p 9000:9000 -p 8080:8080 edge-vision-mcp
```

### Deploy with Docker Desktop (GUI)

1. Open Docker Desktop
2. Build the image:
   - Go to **Images** → **Build**
   - Path: select this project folder
   - Image name: `edge-vision-mcp`
3. Run the container:
   - Go to **Containers** → **Run**
   - Image: `edge-vision-mcp`
   - Map ports: `8080` and `9000`
   - Command: `python3 main.py --host 0.0.0.0 --port 9000`
4. Open `http://localhost:8080`

### Ports

| Port | Service |
|------|---------|
| 8080 | Frontend + WebSocket + HTTP API |
| 9000 | TCP MCP Gateway |

## Kiosk Mode (HDMI)

Launch the edge device in kiosk mode:

```bash
bash scripts/run_kiosk.sh
```

Or install as a systemd service:

```bash
sudo cp scripts/edge-vision-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now edge-vision-mcp
```

## Troubleshooting

### Tests failing with async errors
Install pytest-asyncio matching the requirements:
```bash
pip install pytest-asyncio==0.23.7
pytest tests/ -v
```
