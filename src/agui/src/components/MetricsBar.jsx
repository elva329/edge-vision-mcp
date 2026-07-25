import React from 'react';

export default function MetricsBar({ metrics }) {
  return (
    <div className="panel metrics-panel">
      <h2>System Metrics</h2>
      <div className="metric-bar">
        <div className="metric-bar-label">CPU</div>
        <div className="metric-bar-track"><div className="metric-bar-fill" style={{ width: `${metrics.cpu || 0}%` }}></div></div>
      </div>
      <div className="metric-bar">
        <div className="metric-bar-label">TPU</div>
        <div className="metric-bar-track"><div className="metric-bar-fill" style={{ width: `${metrics.tpu || 0}%` }}></div></div>
      </div>
      <div className="metric-bar">
        <div className="metric-bar-label">RAM</div>
        <div className="metric-bar-track"><div className="metric-bar-fill" style={{ width: `${(metrics.ram || 0) / 4 * 100}%` }}></div></div>
      </div>
      <div className="metric-row"><span>Streams</span><span>{metrics.streams_active != null ? `${metrics.streams_active}/16` : '--/16'}</span></div>
      <div className="metric-row"><span>Latency p95</span><span>{metrics.latency_p95 != null ? `${Math.round(metrics.latency_p95)} ms` : '-- ms'}</span></div>
      <div className="metric-row"><span>Clients</span><span>{metrics.clients != null ? metrics.clients : '--'}</span></div>
    </div>
  );
}