# Skill: Edge Vision MCP Agent

## Description

Autonomous agent skill for operating an edge-deployed surveillance system via Model Context Protocol (MCP). This skill enables an LLM-backed or scripted agent to discover cameras, inspect live frames, trigger TPU inference, manage alert rules, and acknowledge alerts—all through standardized MCP tool calls. Designed for resource-constrained edge devices (CPU/TPU/RAM limited) with LAN-based testing.

## When to Use

Use this skill when:
- You need to monitor or control a surveillance system over MCP.
- You are testing edge MCP gateway behavior (protocol negotiation, stress, security).
- You want to build or validate an AI agent that orchestrates camera streams, inference, and alerts.
- You are deploying on an edge device with limited resources and need a lightweight control plane.

## Prerequisites

- MCP gateway running on edge device at `192.168.1.x:9000` (TCP).
- Network access to LAN subnet `192.168.1.0/24`.
- For testing: separate testing agent on another edge device or x86 PC.
- Protocol support: `2025-11` (session-based) or `2026` (stateless).

## Core Workflow

1. **Discover** — Call `tools/list` to enumerate available MCP tools.
2. **Inspect** — Use `list_cameras` to verify stream health and enumerate 16 feeds.
3. **Observe** — Call `get_stream_frame(camera_id)` to retrieve a live JPEG snapshot.
4. **Infer** — Call `run_inference(image_data)` to get mocked TPU bounding boxes and class labels.
5. **Rule** — Use `evaluate(camera_id, inference_results)` to trigger rule-based alerts.
6. **React** — Call `acknowledge_alert(alert_id)` or `record_clip(camera_id, duration)`.
7. **Monitor** — Query `get_system_metrics()` for CPU, TPU, RAM, and stream latency.

## MCP Tools Reference

### Stream Server Tools
- `list_cameras` — Returns list of camera IDs, resolutions, and health.
- `get_stream_frame(camera_id: string)` — Returns base64 JPEG snapshot (<200ms).
- `start_stream(camera_id: string)` — Begins low-rate MJPEG stream.
- `stop_stream(camera_id: string)` — Stops active stream.
- `get_stream_health(camera_id: string)` — Returns latency, frame drop rate, bitrate.

### Inference Server Tools
- `list_models` — Returns available model IDs and metadata.
- `run_inference(image_data: string)` — Accepts base64 image; returns bounding boxes, labels, confidence.
- `batch_inference(requests: array)` — Processes multiple images in one call (async).

### Rule Server Tools
- `define_rule(rule_spec: object)` — Creates or updates a rule (restricted zone, loitering, object left).
- `list_rules` — Returns active rules and their thresholds.
- `evaluate(camera_id: string, inference_results: object)` — Evaluates rules; returns alerts array.
- `acknowledge_alert(alert_id: string)` — Marks alert as handled.
- `record_clip(camera_id: string, duration: number)` — Starts a clip recording in circular buffer.

### Gateway Tools
- `get_system_metrics()` — Returns CPU%, TPU utilization, RAM usage, active streams.
- `get_protocol_info()` — Returns supported MCP protocol versions and current session mode.

## Protocols

### 2025-11 (Session-Based)
- Client sends `initialize` request.
- Gateway returns `sessionId` in response.
- All subsequent requests MUST include `sessionId` in header or params.
- Stateful: gateway maintains per-session subscriptions and stream bindings.

### 2026 (Stateless)
- Client sends `initialize` request.
- Gateway returns no session identifier.
- All requests are independent; no server-side session state.
- Stateless: suitable for serverless or high-availability frontends.

### Negotiation Logic
- Client declares supported versions in `initialize`.
- Gateway selects highest mutually supported version.
- If both supported, prefer `2026` (lower overhead).
- If mismatch, reject with `protocol_error`.

## Resource Constraints

| Resource | Limit | Strategy |
|----------|-------|----------|
| CPU | 4 cores | Stream throttling; mock inference uses async queue. |
| TPU | Single accelerator | Mocked 10-50ms latency; batch requests to reduce queue depth. |
| RAM | 2-4GB | Circular JPEG buffers; cap at 16 streams x 5 frames. |
| Network | 1Gbps LAN | JPEG quality 50-70%; drop to 30fps under congestion. |

## Testing Agent Behavior

The testing agent is a separate MCP client that:
- Discovers the gateway via UDP broadcast on `192.168.1.255:9001`.
- Connects via TCP and negotiates protocol version.
- Runs automated test suites:
  - **Protocol compliance**: verifies `2025-11` session handling and `2026` stateless behavior.
  - **Stress**: 50+ concurrent `get_stream_frame` calls, 100+ `run_inference` calls/sec.
  - **Security**: input validation fuzzing, oversized payload rejection, rate limiting checks.
- Reports structured JSON with pass/fail counts and latency percentiles.

## Error Handling

- `CAMERA_NOT_FOUND` — Invalid `camera_id`. Returned by stream server.
- `INFERENCE_TIMEOUT` — Mock TPU exceeded latency budget. Retry with backoff.
- `RULE_CONFLICT` — Rule spec invalid or duplicate. Check schema before `define_rule`.
- `PROTOCOL_ERROR` — Version mismatch or missing `sessionId` for `2025-11`.
- `RATE_LIMIT_EXCEEDED` — Too many requests per second. Back off 100ms and retry.
- `PAYLOAD_TOO_LARGE` — Image data exceeds 10MB. Downscale before `run_inference`.

## AGUI Overview

The Agent Graphical User Interface (AGUI) runs on the edge device:
- **Dashboard**: 4x4 live camera thumbnails refreshed at 1fps via WebSocket + polling.
- **Alert Panel**: Real-time alert feed with timestamp, camera, rule, and thumbnail.
- **Metrics**: CPU, TPU, RAM gauges; stream latency line chart.
- **Config**: Camera enable/disable toggles, rule CRUD form, model list, protocol info.
- **Protocol**: HTTP/WebSocket to local gateway; no external dependencies.
- **Kiosk**: Auto-launch Chromium with `scripts/run_kiosk.sh` on HDMI.

## Security Considerations

- LAN-only access; gateway binds to `192.168.1.0/24` interface.
- No internet egress required.
- Rate limiting: max 1000 requests/min per client IP.
- Input validation: all tool params validated against JSON Schema.
- No secrets stored on device; configuration is plaintext in `/etc/edge-vision/`.
- Future: mutual TLS for testing agent authentication.

## Example Agent Loop

```python
# 1. Initialize (stateless)
client.initialize(supported_versions=["2026"])

# 2. List cameras
cameras = client.call("list_cameras")

# 3. Get frame from camera 0
frame = client.call("get_stream_frame", {"camera_id": "cam_00"})

# 4. Run inference
inference = client.call("run_inference", {"image_data": frame})

# 5. Evaluate rules
alerts = client.call("evaluate", {
    "camera_id": "cam_00",
    "inference_results": inference
})

# 6. Acknowledge first alert
if alerts:
    client.call("acknowledge_alert", {"alert_id": alerts[0]["id"]})
```

## Related Files

- PRD: `docs/PRD.md`
- Architecture: `docs/architecture.md`
- AGUI Spec: `docs/agui.md`
- Gateway Implementation: `src/gateway/`
- Test Suites: `tests/stress/`, `tests/security/`
