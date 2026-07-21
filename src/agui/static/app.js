const CONFIG = {
  gateway: "http://192.168.1.10:9000",
  agui: "http://192.168.1.10:8080",
  ws: "ws://192.168.1.10:8080/ws",
  cameras: Array.from({ length: 16 }, (_, i) => `cam_${i.toString().padStart(2, "0")}`),
  refreshMs: 1000,
};

const state = {
  cameras: new Map(),
  alerts: [],
  metrics: {},
  ws: null,
};

function initGrid() {
  const grid = document.getElementById("camera-grid");
  grid.innerHTML = "";
  CONFIG.cameras.forEach((id) => {
    const tile = document.createElement("div");
    tile.className = "camera-tile";
    tile.id = `tile-${id}`;
    tile.innerHTML = `
      <img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='640' height='480'%3E%3Crect width='640' height='480' fill='%231e293b'/%3E%3Ctext x='50%25' y='50%25' fill='%2394a3b8' font-family='sans-serif' font-size='24' text-anchor='middle' dy='.3em'%3ELoading...%3C/text%3E%3C/svg%3E" alt="${id}">
      <div class="tile-overlay">
        <span class="tile-id">${id}</span>
        <span class="tile-status off">OFF</span>
      </div>
    `;
    grid.appendChild(tile);
    state.cameras.set(id, { status: "off", frame: null });
  });
}

function updateTile(cameraId, data) {
  const tile = document.getElementById(`tile-${cameraId}`);
  if (!tile) return;
  const img = tile.querySelector("img");
  const status = tile.querySelector(".tile-status");
  if (data && data.data) {
    img.src = `data:image/jpeg;base64,${data.data}`;
    status.textContent = "LIVE";
    status.className = "tile-status live";
    tile.classList.remove("alert");
  }
  state.cameras.set(cameraId, { status: data ? "live" : "off", frame: data });
}

function addAlert(alert) {
  state.alerts.unshift(alert);
  if (state.alerts.length > 50) state.alerts.pop();
  renderAlerts();
}

function renderAlerts() {
  const list = document.getElementById("alerts-list");
  if (!list) return;
  if (state.alerts.length === 0) {
    list.innerHTML = "<div class='empty-state'>No alerts</div>";
    return;
  }
  list.innerHTML = state.alerts.slice(0, 20).map((a) => `
    <div class="alert-item">
      <div class="alert-header">
        <span class="alert-rule">${escapeHtml(a.rule_name || "ALERT")}</span>
        <span class="alert-time">${new Date(a.timestamp).toLocaleTimeString()}</span>
      </div>
      <div class="alert-cam">${escapeHtml(a.camera_id)}</div>
      <div class="alert-actions">
        <button onclick="ackAlert('${a.alert_id}')">ACK</button>
        <button onclick="recordClip('${a.camera_id}')">CLIP</button>
      </div>
    </div>
  `).join("");
}

function updateMetrics(m) {
  state.metrics = m;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  const setBar = (id, pct) => { const el = document.getElementById(id); if (el) el.style.width = pct; };
  if (m.cpu !== undefined) { set("cpu", `${Math.round(m.cpu)}%`); setBar("cpu-bar", `${m.cpu}%`); }
  if (m.tpu !== undefined) { set("tpu", `${Math.round(m.tpu)}%`); setBar("tpu-bar", `${m.tpu}%`); }
  if (m.ram !== undefined) { set("ram", `${m.ram.toFixed(1)} GB`); setBar("ram-bar", `${(m.ram / 4) * 100}%`); }
  if (m.protocol) set("protocol", m.protocol);
  if (m.streams_active !== undefined) set("streams-count", `${m.streams_active}/16`);
  if (m.latency_p95 !== undefined) set("latency-p95", `${Math.round(m.latency_p95)} ms`);
  if (m.clients !== undefined) set("clients-count", String(m.clients));
}

function setConnection(status) {
  const el = document.getElementById("connection-status");
  if (!el) return;
  el.textContent = status.toUpperCase();
  el.className = `status-badge ${status === "online" ? "online" : "offline"}`;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function mcpCall(method, params = {}, sessionId) {
  const headers = { "Content-Type": "application/json" };
  const body = { jsonrpc: "2.0", id: Date.now(), method, params };
  if (sessionId) body.params.session_id = sessionId;
  const res = await fetch(CONFIG.gateway, { method: "POST", headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  if (data.error) throw new Error(data.error.message || JSON.stringify(data.error));
  const content = data.result && data.result.content && data.result.content[0];
  if (!content) return data.result;
  try { return JSON.parse(content.text); } catch { return content.text; }
}

async function loadCameras() {
  try {
    const data = await mcpCall("tools/call", { name: "list_cameras" });
    const cams = Array.isArray(data) ? data : [];
    CONFIG.cameras.forEach((id) => {
      const found = cams.find((c) => c.id === id);
      updateTile(id, found || null);
    });
  } catch (e) { console.error("list_cameras failed", e); }
}

async function loadFrame(cameraId) {
  try {
    const data = await mcpCall("tools/call", { name: "get_stream_frame", arguments: { camera_id: cameraId } });
    updateTile(cameraId, data);
  } catch (e) { console.error(`frame ${cameraId} failed`, e); }
}

async function loadMetrics() {
  try {
    const data = await mcpCall("tools/call", { name: "get_system_metrics" });
    if (data) updateMetrics(data);
  } catch (e) { console.error("metrics failed", e); }
}

async function ackAlert(alertId) {
  try {
    await mcpCall("tools/call", { name: "acknowledge_alert", arguments: { alert_id: alertId } });
    state.alerts = state.alerts.filter((a) => a.alert_id !== alertId);
    renderAlerts();
  } catch (e) { console.error("ack failed", e); }
}

async function recordClip(cameraId) {
  try {
    await mcpCall("tools/call", { name: "record_clip", arguments: { camera_id: cameraId, duration: 10 } });
    alert(`Recording started for ${cameraId}`);
  } catch (e) { console.error("clip failed", e); }
}

function connectWs() {
  const ws = new WebSocket(CONFIG.ws);
  state.ws = ws;
  ws.onopen = () => { setConnection("online"); };
  ws.onclose = () => { setConnection("offline"); setTimeout(connectWs, 3000); };
  ws.onerror = () => { setConnection("offline"); };
  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === "frame_update") updateTile(msg.camera_id, msg);
      if (msg.type === "alert") addAlert(msg);
      if (msg.type === "metrics") updateMetrics(msg);
    } catch {}
  };
}

async function init() {
  initGrid();
  setConnection("offline");
  connectWs();
  await loadCameras();
  await loadMetrics();
  setInterval(async () => {
    for (const id of CONFIG.cameras) await loadFrame(id);
    await loadMetrics();
  }, CONFIG.refreshMs);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
