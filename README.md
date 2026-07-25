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
