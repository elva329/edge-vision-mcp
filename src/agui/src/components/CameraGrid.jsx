import React from 'react';
import CameraTile from './CameraTile.jsx';

export default function CameraGrid({ cameras, onClip, onToggle }) {
  return (
    <section className="camera-grid">
      {cameras.size === 0 && Array.from({ length: 16 }, (_, i) => `cam_${i.toString().padStart(2, '0')}`).map((id) => (
        <CameraTile key={id} cameraId={id} status="off" onClip={onClip} onToggle={onToggle} />
      ))}
      {Array.from(cameras.entries()).map(([id, data]) => (
        <CameraTile key={id} cameraId={id} status={data.status} frame={data.frame} onClip={onClip} onToggle={onToggle} />
      ))}
    </section>
  );
}