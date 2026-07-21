# Agent Architecture: Edge Vision MCP

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Edge Device (192.168.1.x)                 │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                  MCP Gateway (TCP :9000)               │  │
│  │  ┌─────────────────┐    ┌──────────────────────────┐  │  │
│  │  │ Protocol Layer  │    │   Router / Dispatcher     │  │  │
│  │  │ - 2025-11       │    │ - Session manager         │  │  │
│  │  │ - 2026          │    │ - Rate limiter            │  │  │
│  │  │ - Negotiation   │    │ - Input validator         │  │  │
│  │  └─────────────────┘    └───────────┬──────────────┘  │  │
│  │                                      │                 │  │
│  │  ┌───────────────────────────────────┼─────────────┐  │  │
│  │  │                                   │             │  │  │
│  │  ▼                                   ▼             ▼  │  │
│  │  ┌──────────────┐   ┌──────────────┐  ┌──────────┐   │  │
│  │  │ Stream MCP   │   │ Inference    │  │ Rule MCP │   │  │
│  │  │ Server       │   │ MCP Server   │  │ Server   │   │  │
│  │  │              │   │              │  │          │   │  │
│  │  │ 16 cameras   │   │ Mock TPU     │  │ Alert    │   │  │
│  │  │ Mock JPEG    │   │ BBox + label │  │ Rules    │   │  │
│  │  │ buffers      │   │ 10-50ms      │  │ Engine   │   │  │
│  │  └──────────────┘   └──────────────┘  └──────────┘   │  │
│  │         ▲                  ▲                  ▲       │  │
│  │         │                  │                  │       │  │
│  └─────────┼──────────────────┼──────────────────┼───────┘  │
│            │                  │                  │          │
│  ┌─────────┼──────────────────┼──────────────────┼───────┐  │
│  │         │                  │                  │       │  │
│  │         ▼                  ▼                  ▼       │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │           Circular JPEG Buffer (RAM)             │ │  │
│  │  │   16 cams x 5 frames = 80 frames max            │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  │                                                      │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │           Async Inference Queue                  │ │  │
│  │  │        (TPU simulation, max depth 32)            │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  │                                                      │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │           Alert Ring Buffer                      │ │  │
│  │  │        (last 100 alerts, TTL 5min)               │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              AGUI (HTTP :8080 / WebSocket)            │  │
│  │   - 4x4 camera grid   - Alert panel                   │  │
│  │   - Metrics gauges    - Rule config                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                        │
                        │  LAN (192.168.1.0/24)
                        │
┌───────────────────────▼─────────────────────────────────────┐
│              Testing Agent (192.168.1.y)                     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            MCP Client (TCP :9000)                     │  │
│  │   - Protocol compliance checker                       │  │
│  │   - Stress generator (50+ concurrent)                 │  │
│  │   - Security fuzzer                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            Results Reporter                           │  │
│  │   - JSON output with pass/fail counts                 │  │
│  │   - Latency percentiles (p50, p95, p99)               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 2. Component Details

### 2.1 MCP Gateway
- **Protocol**: JSON-RPC 2.0 over TCP.
- **Port**: `9000` (configurable).
- **Responsibilities**:
  - Negotiate protocol version (`2025-11` vs `2026`) during `initialize`.
  - Maintain `sessionId` for `2025-11` clients; reject calls missing it.
  - Route `tools/call` to the appropriate server (stream, inference, rule).
  - Enforce rate limiting (1000 req/min per IP).
  - Validate all input parameters against JSON Schema before dispatching.

### 2.2 Stream MCP Server
- **Camera Model**: 16 simulated cameras (`cam_00` to `cam_15`).
- **Frame Format**: Base64-encoded JPEG, quality 50-70%.
- **Throttling**: Max 10fps per camera; global cap at 120fps to protect CPU.
- **Buffering**: Circular buffer of 5 frames per camera (80 frames total).
- **Health Checks**: Expose `get_stream_health` returning latency, drops, bitrate.

### 2.3 Inference MCP Server
- **Model**: Mocked TPU with configurable latency (10-50ms).
- **Output Format**:
  ```json
  {
    "boxes": [{"x": 10, "y": 20, "w": 100, "h": 200, "label": "person", "confidence": 0.92}],
    "model_id": "mobilenet_v2_edge",
    "inference_time_ms": 23
  }
  ```
- **Batching**: `batch_inference` accepts up to 16 images, returns array of results.
- **Queue**: Async queue with max depth 32; drops oldest if full.

### 2.4 Rule MCP Server
- **Rule Types**:
  - `zone_crossing`: bounding box enters polygon zone.
  - `loitering`: object remains in zone for N seconds.
  - `object_left`: object appears without a person in frame.
- **State**: In-memory rule registry; no persistence (Phase 1).
- **Evaluation**: Called after each inference; returns array of alerts.

### 2.5 AGUI (Agent Graphical User Interface)
- **Runtime**: HTML/CSS/JS served by a static HTTP server on port `8080`.
- **WebSocket**: Real-time updates for alerts and metrics at 1Hz.
- **Rendering**: Canvas API for 4x4 grid; CSS gauges for metrics.
- **Deployment**: Auto-starts on boot; launches Chromium in kiosk mode on HDMI.

## 3. Data Flow

### 3.1 Stream Inspection
```
Agent → Gateway (get_stream_frame cam_00)
  Gateway → Stream Server (validate camera_id)
    Stream Server → JPEG buffer (read frame)
      JPEG buffer → base64 encode
        Stream Server → Gateway (frame data)
          Gateway → Agent (JSON-RPC response)
```

### 3.2 Inference Pipeline
```
Agent → Gateway (run_inference image_data)
  Gateway → Input Validator (size, format)
    Gateway → Inference Server (queue job)
      Inference Server → Mock TPU (10-50ms)
        Inference Server → Gateway (boxes, labels)
          Gateway → Agent (JSON-RPC response)
```

### 3.3 Alert Generation
```
Stream Server → Frame ready (cam_00)
  Gateway → Inference Server (run_inference)
    Inference Server → Bounding boxes
      Gateway → Rule Server (evaluate cam_00, boxes)
        Rule Server → Zone check → Alert
          Gateway → Agent (notification)
            Agent → Gateway (acknowledge_alert)
```

## 4. Protocol Negotiation

```
Client                         Gateway
 │                               │
 │──── initialize ──────────────>│
 │    { version: "2025-11" }      │
 │                               │
 │<──── response ────────────────│
 │    { sessionId: "abc123" }     │
 │                               │
 │──── tools/call ──────────────>│
 │    { sessionId: "abc123" }     │
 │                               │
```

```
Client                         Gateway
 │                               │
 │──── initialize ──────────────>│
 │    { version: "2026" }        │
 │                               │
 │<──── response ────────────────│
 │    {}  (no sessionId)          │
 │                               │
 │──── tools/call ──────────────>│
 │    {}  (stateless)             │
 │                               │
```

## 5. Deployment Topology

| Component | IP | Port | Protocol |
|-----------|----|------|----------|
| MCP Gateway | 192.168.1.10 | 9000 | TCP |
| AGUI | 192.168.1.10 | 8080 | HTTP/WS |
| Testing Agent | 192.168.1.20 | dynamic | TCP (outbound) |
| UDP Broadcast (discovery) | 192.168.1.255 | 9001 | UDP |

## 6. Resource Budget

| Component | CPU % | RAM | Notes |
|-----------|-------|-----|-------|
| Gateway | 5-10% | 32MB | Event loop, routing |
| Stream Server | 10-15% | 64MB | JPEG encode/decode |
| Inference Server | 5-10% | 32MB | Mock queue |
| Rule Server | 2-5% | 16MB | Polygon math |
| AGUI | 5-10% | 64MB | Browser process |
| **Total** | **27-50%** | **~208MB** | Within 4GB budget |
