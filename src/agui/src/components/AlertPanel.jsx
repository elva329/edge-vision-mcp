import React from 'react';

export default function AlertPanel({ alerts, onAck, onClip }) {
  return (
    <div className="panel alerts-panel">
      <h2>Alerts</h2>
      {alerts.length === 0 && <div className="empty-state">No alerts</div>}
      {alerts.map((a) => (
        <div key={a.alert_id} className="alert-item">
          <div className="alert-header">
            <span className="alert-rule">{a.rule_name || 'ALERT'}</span>
            <span className="alert-time">{new Date(a.timestamp).toLocaleTimeString()}</span>
          </div>
          <div className="alert-cam">{a.camera_id}</div>
          <div className="alert-actions">
            <button onClick={() => onAck(a.alert_id)}>ACK</button>
            <button onClick={() => onClip(a.camera_id)}>CLIP</button>
          </div>
        </div>
      ))}
    </div>
  );
}