import React from 'react';

export default function CameraTile({ cameraId, status, frame, onClip, onToggle }) {
  const imgSrc = frame && frame.data ? `data:image/jpeg;base64,${frame.data}` : null;
  return (
    <div className={`camera-tile ${status === 'live' ? 'live' : 'off'}`}>
      {imgSrc ? (
        <img src={imgSrc} alt={cameraId} />
      ) : (
        <div className="tile-placeholder">
          <span>{cameraId}</span>
        </div>
      )}
      <div className="tile-overlay">
        <span className="tile-id">{cameraId}</span>
        <span className={`tile-status ${status}`}>{status.toUpperCase()}</span>
      </div>
      <button className={`tile-toggle ${status === 'live' ? 'tile-toggle-stop' : 'tile-toggle-start'}`} onClick={() => onToggle && onToggle(cameraId, status)}>
        {status === 'live' ? 'Stop' : 'Start'}
      </button>
      {status === 'live' && (
        <button className="clip-btn" onClick={() => onClip(cameraId)}>CLIP</button>
      )}
    </div>
  );
}