import React, { useState, useEffect, useCallback } from 'react';
import CameraGrid from './components/CameraGrid.jsx';
import AlertPanel from './components/AlertPanel.jsx';
import MetricsBar from './components/MetricsBar.jsx';

const GATEWAY_URL = '/rpc';
const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

const CAMERAS = Array.from({ length: 16 }, (_, i) => `cam_${i.toString().padStart(2, '0')}`);

function mcpCall(method, params = {}) {
  return fetch(GATEWAY_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: Date.now(), method, params }),
  }).then((r) => r.json()).then((d) => {
    if (d.error) throw new Error(d.error.message || JSON.stringify(d.error));
    const c = d.result?.content?.[0];
    if (!c) return d.result;
    try { return JSON.parse(c.text); } catch { return c.text; }
  });
}

function useWebSocket(onMessage) {
  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)); } catch {}
    };
    ws.onclose = () => { setTimeout(() => useWebSocket(onMessage), 3000); };
    return () => ws.close();
  }, [onMessage]);
}

export default function App() {
  const [cameras, setCameras] = useState(new Map());
  const [alerts, setAlerts] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [connected, setConnected] = useState(false);

  const handleWsMessage = useCallback((msg) => {
    if (msg.type === 'frame_update') {
      setCameras((prev) => {
        const next = new Map(prev);
        next.set(msg.camera_id, { status: 'live', frame: msg });
        return next;
      });
    }
    if (msg.type === 'alert') {
      setAlerts((prev) => [msg, ...prev].slice(0, 50));
    }
    if (msg.type === 'metrics') {
      setMetrics(msg);
    }
  }, []);

  useWebSocket(handleWsMessage);

  useEffect(() => {
    mcpCall('tools/call', { name: 'list_cameras' }).then((cams) => {
      const map = new Map();
      (cams || []).forEach((c) => map.set(c.id, { status: c.status, frame: null }));
      setCameras(map);
    }).catch(() => {});

    const iv = setInterval(() => {
      mcpCall('tools/call', { name: 'get_system_metrics' }).then(setMetrics).catch(() => {});
      CAMERAS.forEach((id) => {
        mcpCall('tools/call', { name: 'get_stream_frame', arguments: { camera_id: id } }).then((frame) => {
          setCameras((prev) => {
            const next = new Map(prev);
            next.set(id, { status: 'live', frame });
            return next;
          });
        }).catch(() => {});
      });
    }, 1000);

    setConnected(true);
    return () => clearInterval(iv);
  }, []);

  const handleAck = useCallback(async (alertId) => {
    try {
      await mcpCall('tools/call', { name: 'acknowledge_alert', arguments: { alert_id: alertId } });
      setAlerts((prev) => prev.filter((a) => a.alert_id !== alertId));
    } catch {}
  }, []);

  const handleClip = useCallback(async (cameraId) => {
    try {
      await mcpCall('tools/call', { name: 'record_clip', arguments: { camera_id: cameraId, duration: 10 } });
      alert(`Recording started for ${cameraId}`);
    } catch {}
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1>Edge Vision MCP</h1>
          <span className={`status-badge ${connected ? 'online' : 'offline'}`}>{connected ? 'ONLINE' : 'OFFLINE'}</span>
        </div>
        <div className="header-right">
          <div className="metric"><span className="metric-label">CPU</span><span className="metric-value">{metrics.cpu != null ? `${Math.round(metrics.cpu)}%` : '--'}</span></div>
          <div className="metric"><span className="metric-label">TPU</span><span className="metric-value">{metrics.tpu != null ? `${Math.round(metrics.tpu)}%` : '--'}</span></div>
          <div className="metric"><span className="metric-label">RAM</span><span className="metric-value">{metrics.ram != null ? `${metrics.ram.toFixed(1)} GB` : '--'}</span></div>
          <div className="metric"><span className="metric-label">Protocol</span><span className="metric-value">{metrics.protocol || '--'}</span></div>
        </div>
      </header>
      <main className="main">
        <CameraGrid cameras={cameras} onClip={handleClip} />
        <aside className="sidebar">
          <AlertPanel alerts={alerts} onAck={handleAck} onClip={handleClip} />
          <MetricsBar metrics={metrics} />
        </aside>
      </main>
    </div>
  );
}
