import React from 'react';

function PowerPanel({ onPowerOff }) {
  const handlePowerOff = () => {
    if (window.confirm('Are you sure you want to power off the system?')) {
      onPowerOff();
    }
  };

  return (
    <div className="panel">
      <h2>Power Controls</h2>
      <div className="control-panel">
        <button onClick={handlePowerOff}>Power Off</button>
      </div>
    </div>
  );
}

export default PowerPanel;
