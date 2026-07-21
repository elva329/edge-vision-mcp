# AGUI Design: Edge Vision MCP Frontend

## 1. Overview

The Agent Graphical User Interface (AGUI) is the operator-facing frontend for the edge vision system. It runs directly on the edge device, accessible via HDMI (kiosk mode) or LAN browser. The AGUI visualizes 16 camera feeds, real-time alerts, and system metrics without requiring an internet connection.

## 2. Layout

```
┌──────────────────────────────────────────────────────────────┐
│  EDGE VISION MCP          [CPU: 12%] [TPU: 45%] [RAM: 1.2GB]│
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│   │ cam_00   │  │ cam_01   │  │ cam_02   │  │ cam_03   │   │
│   │ [LIVE]   │  │ [LIVE]   │  │ [OFF]    │  │ [LIVE]   │   │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│   │ cam_04   │  │ cam_05   │  │ cam_06   │  │ cam_07   │   │
│   │ [LIVE]   │  │ [LIVE]   │  │ [LIVE]   │  │ [LIVE]   │   │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│   │ cam_08   │  │ cam_09   │  │ cam_10   │  │ cam_11   │   │
│   │ [LIVE]   │  │ [OFF]    │  │ [LIVE]   │  │ [LIVE]   │   │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│   │ cam_12   │  │ cam_13   │  │ cam_14   │  │ cam_15   │   │
│   │ [LIVE]   │  │ [LIVE]   │  │ [LIVE]   │  │ [LIVE]   │   │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                              │
├──────────────────────────┬───────────────────────────────────┤
│  ALERTS (last 10)        │  SYSTEM METRICS                   │
│  ─────────────────────   │  ┌─────────────────────────────┐  │
│  14:32:01 cam_00         │  │ CPU: ████████░░ 12%          │  │
│  RESTRICTED ZONE          │  │ TPU: ██████████░ 45%         │  │
│  [ACK] [CLIP]            │  │ RAM: ███████░░░ 1.2GB / 4GB │  │
│  ─────────────────────   │  │ Streams: 14/16 active        │  │
│  14:31:45 cam_05         │  │ Latency: p95 180ms           │  │
│  LOITERING                │  └─────────────────────────────┘  │
│  [ACK] [CLIP]            │                                   │
│  ─────────────────────   │  PROTOCOL: 2026 (stateless)      │
│  14:30:22 cam_12         │  CLIENTS: 3 connected             │
│  OBJECT LEFT BEHIND       │                                   │
│  [ACK] [CLIP]            │                                   │
└──────────────────────────┴───────────────────────────────────┘
```

## 3. Screens

### 3.1 Main Dashboard (Default)
- **Header**: System title, timestamp, connection status, protocol version.
- **Grid**: 4x4 camera thumbnails. Each tile shows:
  - Live JPEG snapshot (refreshed 1fps via WebSocket or polling).
  - Camera ID and status badge (`LIVE`, `OFF`, `ERROR`).
  - Overlay alert indicator (red border + icon when alert active).
- **Footer**: Metrics bar (CPU, TPU, RAM, stream latency, client count).

### 3.2 Alert Panel (Right Sidebar)
- Scrollable list of last 10 alerts.
- Each alert shows:
  - Timestamp (HH:MM:SS).
  - Camera ID.
  - Rule name (e.g., `RESTRICTED_ZONE`).
  - Thumbnail snapshot.
  - Action buttons: `ACK` (acknowledge), `CLIP` (record 10s clip).
- Auto-scrolls to newest alert; highlights unacknowledged.

### 3.3 Metrics Panel (Right Sidebar, Bottom)
- Gauges for CPU, TPU, RAM.
- Text metrics: active streams, p95 latency, client count.
- Protocol badge: `2025-11 (session)` or `2026 (stateless)`.
- Update frequency: 1Hz via WebSocket.

### 3.4 Config View (Access via Tab or URL param)
- Camera list with enable/disable toggle.
- Rule editor (CRUD for zone polygons, loitering thresholds).
- Model selector (switch between mock inference models).
- Protocol info and session list.

## 4. Components

| Component | File | Description |
|-----------|------|-------------|
| `App` | `app.js` | Root layout, state management, WebSocket connection. |
| `CameraGrid` | `camera-grid.js` | 4x4 grid container; manages tile state. |
| `CameraTile` | `camera-tile.js` | Single camera thumbnail, status badge, alert overlay. |
| `AlertPanel` | `alert-panel.js` | Scrollable alert list with actions. |
| `MetricsBar` | `metrics-bar.js` | System gauges and text metrics. |
| `ConfigView` | `config-view.js` | Camera toggles, rule editor, model selector. |
| `GatewayClient` | `gateway-client.js` | WebSocket + HTTP client for MCP and metrics. |

## 5. Communication

### 5.1 WebSocket (Real-Time)
- URL: `ws://192.168.1.10:8080/ws`
- Messages:
  - `frame_update`: `{ camera_id, image_data (base64), timestamp }`
  - `alert`: `{ id, camera_id, rule, timestamp, thumbnail }`
  - `metrics`: `{ cpu, tpu, ram, latency_p95, streams_active }`

### 5.2 HTTP REST (Control)
- `GET /api/cameras` — List cameras.
- `POST /api/alerts/:id/ack` — Acknowledge alert.
- `POST /api/clips` — Start clip recording.
- `GET /api/metrics` — Current metrics snapshot.
- `GET /api/protocol` — Protocol info.

### 5.3 MCP Proxy (Agent Bridge)
- The AGUI can also act as an MCP client proxy for the agent.
- WebSocket `mcp` channel forwards `tools/call` to gateway TCP.
- Allows agent-driven UI updates without separate client.

## 6. Styling

- **Theme**: Dark mode (high contrast for low-light control rooms).
- **Colors**:
  - Background: `#0f172a` (slate-900).
  - Surface: `#1e293b` (slate-800).
  - Accent: `#22d3ee` (cyan-400) for live indicators.
  - Alert: `#ef4444` (red-500) for critical alerts.
  - Text: `#f8fafc` (slate-50).
- **Typography**: System sans-serif (Inter if available).
- **Layout**: CSS Grid for camera tiles; Flexbox for panels.
- **Responsive**: Fixed 1920x1080 target; scales down to 1280x720.

## 7. Edge Optimizations

- **Image Quality**: JPEG quality 50%, max resolution 640x480 per tile.
- **Polling**: 1fps for grid; 10fps for selected camera focus view.
- **Memory**: Recycle canvas contexts; no image caching beyond current frame.
- **Startup**: Lazy-load non-critical components; show skeleton UI first.
- **Kiosk**: Auto-launch Chromium with `--kiosk --noerrdialogs --disable-infobars`.
