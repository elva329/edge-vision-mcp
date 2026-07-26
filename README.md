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

Then open **http://localhost:5173**. The Vite dev server proxies API (`/rpc`) and WebSocket (`/ws`) requests to the backend on port 9000. UI changes reload automatically; no hard refresh needed.

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

## Testing

```bash
make test
```

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

## Testing Agent

The testing agent discovers the gateway via UDP broadcast and runs tests from another device on the same LAN:

```bash
bash scripts/run_tester.sh
```

Environment variables:
- `GATEWAY_HOST` — Edge device IP (default `192.168.1.10`)
- `OUTPUT` — Report file path (default `test-report.json`)

## Troubleshooting

### Tests failing with async errors
Install pytest-asyncio matching the requirements:
```bash
pip install pytest-asyncio==0.23.7
pytest tests/ -v
```
