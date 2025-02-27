import React from 'react';

function StatusIndicator({ type, message }) {
  return (
    <div className={`status-indicator ${type}`}>
      {message}
    </div>
  );
}

export default StatusIndicator;
