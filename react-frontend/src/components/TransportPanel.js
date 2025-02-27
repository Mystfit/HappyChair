import React, { useState, useEffect } from 'react';

function TransportPanel({ transportPlaying, globalFramerate, animationMode, onTransportAction }) {
  const [framerate, setFramerate] = useState(globalFramerate);

  useEffect(() => {
    setFramerate(globalFramerate);
  }, [globalFramerate]);

  const handleFramerateChange = (e) => {
    setFramerate(parseFloat(e.target.value));
  };

  const handleUpdateSpeed = () => {
    onTransportAction('update', framerate);
  };

  return (
    <div className="panel">
      <h2>
        {animationMode === 'live' && 'Live transport'}
        {animationMode === 'playlist' && 'Playlist transport'}
        {animationMode === 'transport' && 'Single animation transport'}
      </h2>
      
      {(animationMode === 'transport' || animationMode === 'playlist') && (
        <div className="control-panel">
          {transportPlaying ? (
            <button onClick={() => onTransportAction('pause')}>Pause</button>
          ) : (
            <button onClick={() => onTransportAction('play')}>Play</button>
          )}
          
          <button onClick={() => onTransportAction('stop')}>Stop</button>
          
          <div className="framerate-control">
            <label htmlFor="framerate">Global framerate:</label>
            <input
              id="framerate"
              type="number"
              step="any"
              min="0.001"
              value={framerate}
              onChange={handleFramerateChange}
            />
            <button onClick={handleUpdateSpeed}>Update speed</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default TransportPanel;
