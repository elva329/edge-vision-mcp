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
- `src/gateway/server.py` — JSON-RPC 2.0 TCP gateway with session management
- `src/servers/` — Stream, Inference, and Rule MCP servers
- `src/agui/` — React frontend (Vite)
- `src/testing/testing_agent.py` — Compliance, stress, and security test runner

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

### Ports

| Port | Service |
|------|---------|
| 8080 | Frontend + WebSocket + HTTP API |
| 9000 | TCP MCP Gateway |
