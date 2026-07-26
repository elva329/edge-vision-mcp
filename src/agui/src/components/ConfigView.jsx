import React, { useState, useEffect, useCallback } from 'react';

const GATEWAY_URL = '/rpc';

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

export default function ConfigView({ cameras, onRefresh }) {
  const [rules, setRules] = useState([]);
  const [models, setModels] = useState([]);
  const [protocol, setProtocol] = useState({});
  const [loading, setLoading] = useState(false);
  const [newRule, setNewRule] = useState({ name: '', camera_id: 'cam_00', type: 'zone_crossing', zone: '[[100,100],[300,100],[300,300],[100,300]]', threshold_seconds: 10 });

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const [r, m, p] = await Promise.all([
        mcpCall('tools/call', { name: 'list_rules' }),
        mcpCall('tools/call', { name: 'list_models' }),
        mcpCall('tools/call', { name: 'get_protocol_info' }),
      ]);
      setRules(r || []);
      setModels(m || []);
      setProtocol(p || {});
    } catch (e) {
      console.error('Failed to load config', e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  const handleDefineRule = async (e) => {
    e.preventDefault();
    try {
      const zone = JSON.parse(newRule.zone || '[]');
      await mcpCall('tools/call', {
        name: 'define_rule',
        arguments: {
          rule_spec: {
            name: newRule.name,
            camera_id: newRule.camera_id,
            type: newRule.type,
            zone,
            threshold_seconds: Number(newRule.threshold_seconds),
          }
        }
      });
      setNewRule({ name: '', camera_id: 'cam_00', type: 'zone_crossing', zone: '[[100,100],[300,100],[300,300],[100,300]]', threshold_seconds: 10 });
      await loadConfig();
    } catch (e) {
      alert('Failed to create rule: ' + e.message);
    }
  };

  const toggleCamera = async (cameraId, currentStatus) => {
    const action = currentStatus === 'live' ? 'stop_stream' : 'start_stream';
    try {
      await mcpCall('tools/call', { name: action, arguments: { camera_id: cameraId } });
      onRefresh && onRefresh();
    } catch (e) {
      alert('Failed to toggle camera: ' + e.message);
    }
  };

  return (
    <div className="config-view">
      <div className="config-section">
        <h3>Cameras</h3>
        <div className="config-list">
          {Array.from(cameras.values()).map((cam) => (
            <div key={cam.id} className="config-row">
              <span className="config-id">{cam.id}</span>
              <span className={`config-status ${cam.status}`}>{cam.status}</span>
              <button onClick={() => toggleCamera(cam.id, cam.status)}>
                {cam.status === 'live' ? 'Stop' : 'Start'}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="config-section">
        <h3>Rules</h3>
        <div className="config-list">
          {rules.length === 0 && <div className="empty-state">No rules defined</div>}
          {rules.map((r) => (
            <div key={r.rule_id} className="config-row">
              <span className="config-id">{r.name}</span>
              <span className="config-type">{r.type}</span>
              <span className={`config-status ${r.active ? 'active' : 'inactive'}`}>{r.active ? 'Active' : 'Inactive'}</span>
            </div>
          ))}
        </div>
        <form className="config-form" onSubmit={handleDefineRule}>
          <input
            placeholder="Rule name"
            value={newRule.name}
            onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
            required
          />
          <select value={newRule.camera_id} onChange={(e) => setNewRule({ ...newRule, camera_id: e.target.value })}>
            {Array.from({ length: 16 }, (_, i) => `cam_${i.toString().padStart(2, '0')}`).map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
          <select value={newRule.type} onChange={(e) => setNewRule({ ...newRule, type: e.target.value })}>
            <option value="zone_crossing">Zone Crossing</option>
            <option value="loitering">Loitering</option>
            <option value="object_left">Object Left</option>
          </select>
          <input
            placeholder='Zone [[x1,y1],...]'
            value={newRule.zone}
            onChange={(e) => setNewRule({ ...newRule, zone: e.target.value })}
          />
          <input
            type="number"
            placeholder="Threshold (s)"
            value={newRule.threshold_seconds}
            onChange={(e) => setNewRule({ ...newRule, threshold_seconds: e.target.value })}
          />
          <button type="submit">Create Rule</button>
        </form>
      </div>

      <div className="config-section">
        <h3>Models</h3>
        <div className="config-list">
          {models.length === 0 && <div className="empty-state">No models</div>}
          {models.map((m) => (
            <div key={m.id} className="config-row">
              <span className="config-id">{m.id}</span>
              <span className="config-type">{m.classes.join(', ')}</span>
              <span className="config-status">{m.latency_ms[0]}-{m.latency_ms[1]}ms</span>
            </div>
          ))}
        </div>
      </div>

      <div className="config-section">
        <h3>Protocol</h3>
        <div className="config-list">
          <div className="config-row">
            <span className="config-id">Supported</span>
            <span className="config-type">{(protocol.supported_versions || []).join(', ')}</span>
          </div>
          <div className="config-row">
            <span className="config-id">Default</span>
            <span className="config-type">{protocol.default_version}</span>
          </div>
          <div className="config-row">
            <span className="config-id">Session-based</span>
            <span className="config-type">{protocol.session_based_available ? 'Yes' : 'No'}</span>
          </div>
          <div className="config-row">
            <span className="config-id">Stateless</span>
            <span className="config-type">{protocol.stateless_available ? 'Yes' : 'No'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
