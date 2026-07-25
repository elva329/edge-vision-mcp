import React from 'react';

export default function CameraTile({ cameraId, status, frame, onClip }) {
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
      {status === 'live' && (
        <button className="clip-btn" onClick={() => onClip(cameraId)}>CLIP</button>
      )}
    </div>
  );
}