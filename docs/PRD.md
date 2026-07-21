# Product Requirements Document: Edge Vision MCP

## 1. Executive Summary

Build a Model Context Protocol (MCP) gateway and agent system for edge-deployed surveillance. The system ingests up to 16 RTSP camera streams, runs real-time inference on a local TPU, applies configurable rule-based alerts, and exposes all capabilities via MCP tools to an AI agent. A lightweight frontend (AGUI) runs on the edge device via HDMI or LAN, and a separate testing agent validates behavior over the LAN.

## 2. Problem Statement

Edge surveillance devices ship with camera interfaces and TPUs but lack a unified, agentic control plane. Integrators must write custom glue code for each camera model, inference runtime, and alert rule. MCP offers a standardized tool interface, but no production-grade edge gateway exists that can negotiate both the legacy `2025-11` session-based protocol and the modern `2026` stateless protocol while keeping resource usage low.

## 3. Goals and Objectives

- Deliver an MCP gateway that supports both `2025-11` and `2026` protocol versions.
- Provide a lightweight, mocked-tools MCP server to validate AGUI and agent behavior without real hardware.
- Integrate a 16-camera stream MCP server, a TPU inference MCP server, and a rule-based alert MCP server.
- Run the full stack on an edge device with limited CPU/TPU/RAM.
- Enable LAN-based testing by a separate agent or x86 PC.
- Pass stress and security test suites.

## 4. User Personas

| Persona | Description |
|---------|-------------|
| Edge Integrator | Installs the gateway on a device, configures cameras, rules, and inference models. |
| AI Agent | An LLM-backed or scripted agent that discovers and calls MCP tools to inspect streams, run inference, and acknowledge alerts. |
| Tester | Runs the testing agent on another edge device or x86 PC to verify behavior under load and attack. |
| Operator | Uses the AGUI to monitor camera health, live alerts, and system metrics. |

## 5. Use Cases

### UC1: Live Surveillance Monitoring
The testing agent connects to the edge gateway and calls `list_cameras`, `get_stream_frame`, and `get_inference_result` to monitor 16 feeds.

### UC2: Intrusion Alert
A rule server evaluates bounding boxes from the inference server. When a person enters a restricted zone, it emits an alert. The agent calls `acknowledge_alert` and can trigger `record_clip`.

### UC3: Protocol Negotiation
A legacy MCP client connects using `2025-11` and maintains a session ID. A modern client connects using `2026` with stateless requests. The gateway routes both correctly.

## 6. Functional Requirements

### FR1: MCP Gateway
- Implement JSON-RPC 2.0 over TCP.
- Support `initialize` handshake for `2025-11` (returns `sessionId`) and `2026` (returns no session).
- Maintain per-session state for `2025-11`; reject stateless calls that require session context.
- Expose `tools/list`, `tools/call`, and `notifications/...`.

### FR2: Stream MCP Server
- Manage up to 16 simulated camera streams.
- `list_cameras` returns camera IDs, resolutions, and health status.
- `get_stream_frame(camera_id)` returns a JPEG snapshot (mocked base64) with latency < 200ms.
- `start_stream(camera_id)` / `stop_stream(camera_id)` for continuous low-rate MJPEG stream.

### FR3: Inference MCP Server
- Accept image payloads and return mocked TPU inference results (bounding boxes, class labels, confidence).
- `run_inference(image_data)` simulates 10-50ms TPU latency.
- `list_models` returns available model IDs and metadata.
- Async support: allow batched inference for multiple cameras.

### FR4: Rule MCP Server
- `define_rule(rule_spec)` creates or updates a rule.
- `list_rules` returns active rules.
- `evaluate(camera_id, inference_results)` returns alerts.
- Rules include: restricted zone crossing, loitering, object left behind.

### FR5: AGUI (Frontend)
- Display 16-camera grid view (4x4) with live thumbnails.
- Alert panel with real-time feed.
- System metrics (CPU, TPU, RAM, stream latency).
- Config view for rules and camera status.
- Accessible via HDMI (Kiosk mode) or LAN browser.

### FR6: Testing Agent
- Runs on a separate device in the same LAN.
- Discovers the edge gateway via UDP broadcast.
- Executes test suites for protocol compliance, stress, and security.
- Reports pass/fail with structured JSON.

## 7. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| Gateway latency (p95) | < 50ms per tool call |
| Stream frame latency | < 200ms |
| Inference mock latency | 10-50ms |
| Memory footprint | < 256MB |
| CPU usage (idle) | < 15% |
| Concurrent MCP clients | 10+ |
| Uptime | 99.9% |

## 8. Constraints

- Edge device: limited CPU, single TPU, 2-4GB RAM.
- No GPU; all heavy lifting must be mocked or TPU-offloaded.
- HDMI 1080p output; USB for keyboard/mouse.
- LAN: 192.168.1.0/24.
- Must support both `2025-11` and `2026` MCP protocols simultaneously.

## 9. Out of Scope (Phase 1)

- Real RTSP/ONVIF camera integration (use mocked streams).
- Real TPU driver integration (use mocked inference).
- Persistent storage for recordings (use in-memory circular buffer).
- Authentication and encryption for local HDMI access (TLS only for LAN).

## 10. Milestones

| Milestone | Description | ETA |
|-----------|-------------|-----|
| M1 | PRD, skill.md, architecture, AGUI design | Week 1 |
| M2 | Dual-protocol MCP gateway + lightweight mocked server | Week 2 |
| M3 | Stream, inference, and rule MCP servers | Week 3 |
| M4 | AGUI implementation and edge deployment | Week 4 |
| M5 | Testing agent and LAN integration | Week 5 |
| M6 | Stress and security test suites | Week 6 |

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| TPU driver unavailable | Medium | High | Mock inference; design interface for future swap. |
| 2026 spec changes | Low | Medium | Pin protocol negotiation to capability flags; version field. |
| LAN bandwidth saturation | Medium | Medium | Throttle stream quality; prioritize alert traffic. |
| Memory leaks from 16 streams | Medium | High | Use circular buffers; enforce frame rate caps. |
