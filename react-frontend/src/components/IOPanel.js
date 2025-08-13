import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../contexts/WebSocketContext';

const IOPanel = ({ onStatusUpdate }) => {
  const { data: wsData, isConnected, connectionError } = useWebSocket();
  const [error, setError] = useState(null);
  const [analogChannelConfig, setAnalogChannelConfig] = useState({
    channel: 0,
    name: '',
    gain: 1,
    data_rate: 128
  });
  const [showAddChannel, setShowAddChannel] = useState(false);
  
  // Frontend voltage history tracking
  const [voltageHistory, setVoltageHistory] = useState({});
  const maxHistoryLength = 100;

  // Extract data from WebSocket
  const gpioPins = wsData.gpio_pins || {};
  const analogChannels = wsData.analog_channels || {};

  // Track voltage history locally when new data arrives
  useEffect(() => {
    if (analogChannels && Object.keys(analogChannels).length > 0) {
      setVoltageHistory(prevHistory => {
        const newHistory = { ...prevHistory };
        
        Object.entries(analogChannels).forEach(([channel, channelInfo]) => {
          if (!newHistory[channel]) {
            newHistory[channel] = [];
          }
          
          // Add new voltage value
          newHistory[channel].push(channelInfo.voltage);
          
          // Keep only the last maxHistoryLength values
          if (newHistory[channel].length > maxHistoryLength) {
            newHistory[channel] = newHistory[channel].slice(-maxHistoryLength);
          }
        });
        
        return newHistory;
      });
    }
  }, [analogChannels, maxHistoryLength]);
  const motorStats = wsData.motor_stats || {
    motor_direction: 'stopped',
    motor_speed: 0.0,
    tracking_enabled: false
  };

  // Mini chart component for analog sensors
  const MiniChart = ({ data, width = 80, height = 30 }) => {
    const canvasRef = useRef(null);

    useEffect(() => {
      if (!data || data.length === 0) return;

      const canvas = canvasRef.current;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      const dpr = window.devicePixelRatio || 1;
      
      // Set canvas size
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = width + 'px';
      canvas.style.height = height + 'px';
      ctx.scale(dpr, dpr);

      // Clear canvas
      ctx.clearRect(0, 0, width, height);

      if (data.length < 2) return;

      // Find min/max for scaling
      const min = Math.min(...data);
      const max = Math.max(...data);
      const range = max - min || 1; // Avoid division by zero

      // Draw line chart
      ctx.strokeStyle = '#007bff';
      ctx.lineWidth = 1.5;
      ctx.beginPath();

      data.forEach((value, index) => {
        const x = (index / (data.length - 1)) * width;
        const y = height - ((value - min) / range) * height;
        
        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();

      // Draw dots for last few points
      ctx.fillStyle = '#007bff';
      const lastPoints = data.slice(-3);
      lastPoints.forEach((value, i) => {
        const actualIndex = data.length - lastPoints.length + i;
        const x = (actualIndex / (data.length - 1)) * width;
        const y = height - ((value - min) / range) * height;
        
        ctx.beginPath();
        ctx.arc(x, y, 1.5, 0, 2 * Math.PI);
        ctx.fill();
      });

    }, [data, width, height]);

    return <canvas ref={canvasRef} style={{ display: 'block' }} />;
  };

  const handleAddAnalogChannel = async () => {
    try {
      const response = await fetch('/api/analog/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(analogChannelConfig)
      });

      const result = await response.json();
      if (result.success) {
        setShowAddChannel(false);
        setAnalogChannelConfig({ channel: 0, name: '', gain: 1, data_rate: 128 });
        setError(null);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(`Failed to add channel: ${err.message}`);
    }
  };

  const handleClutchLockToggle = async () => {
    try {
      const locked = !motorStats.driver_clutch_locked;
      const response = await fetch('/api/motor/clutch/lock', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ locked })
      });

      const result = await response.json();
      if (!result.success) {
        setError(result.error);
      } else {
        setError(null);
      }
    } catch (err) {
      setError(`Failed to toggle clutch lock: ${err.message}`);
    }
  };

  const handleEmergencyDisengage = async () => {
    try {
      const response = await fetch('/api/motor/clutch/emergency-disengage', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      const result = await response.json();
      if (!result.success) {
        setError(result.error);
      } else {
        setError(null);
      }
    } catch (err) {
      setError(`Failed to emergency disengage clutch: ${err.message}`);
    }
  };

  return (
    <div className="io-panel">
      <div className="panel-header">
        <h3>GPIO, Analog & Motor Control Panel</h3>
        {!isConnected && (
          <div className="connection-status">
            <span className="status-indicator offline"></span>
            WebSocket Disconnected
          </div>
        )}
      </div>

      {(error || connectionError) && (
        <div className="alert alert-danger">
          <strong>Error:</strong> {error || connectionError}
        </div>
      )}

      <div className="io-content">
        <div className="gpio-section">
          <div className="gpio-status">
            <h4>GPIO Pin Status</h4>
            {Object.keys(gpioPins).length > 0 ? (
              <div className="gpio-pins">
                {Object.entries(gpioPins).map(([pinNumber, pinInfo]) => (
                  <div key={pinNumber} className="gpio-pin-item">
                    <div className="pin-info">
                      <span className="pin-number">Pin {pinNumber}</span>
                      <span className="pin-name">{pinInfo.name}</span>
                      <span className="pin-direction">{pinInfo.direction}</span>
                    </div>
                    <div className="pin-status">
                      <div 
                        className={`status-circle ${pinInfo.state ? 'lit' : 'unlit'}`}
                        title={`State: ${pinInfo.state ? 'HIGH' : 'LOW'}`}
                      ></div>
                      <span className="pin-state">
                        {pinInfo.state ? 'HIGH' : 'LOW'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-pins">
                <span>No GPIO pins registered</span>
              </div>
            )}
          </div>
        </div>

        <div className="analog-section">
          <div className="analog-status">
            <div className="analog-header">
              <h4>Analog Sensors</h4>
              <button 
                className="btn btn-sm btn-primary"
                onClick={() => setShowAddChannel(!showAddChannel)}
              >
                Add Channel
              </button>
            </div>

            {showAddChannel && (
              <div className="add-channel-form">
                <div className="form-row">
                  <label>
                    Channel:
                    <select 
                      value={analogChannelConfig.channel} 
                      onChange={(e) => setAnalogChannelConfig({...analogChannelConfig, channel: parseInt(e.target.value)})}
                    >
                      <option value={0}>0</option>
                      <option value={1}>1</option>
                      <option value={2}>2</option>
                      <option value={3}>3</option>
                    </select>
                  </label>
                  <label>
                    Name:
                    <input 
                      type="text" 
                      value={analogChannelConfig.name} 
                      onChange={(e) => setAnalogChannelConfig({...analogChannelConfig, name: e.target.value})}
                      placeholder="Sensor name"
                    />
                  </label>
                </div>
                <div className="form-row">
                  <label>
                    Gain:
                    <select 
                      value={analogChannelConfig.gain} 
                      onChange={(e) => setAnalogChannelConfig({...analogChannelConfig, gain: parseInt(e.target.value)})}
                    >
                      <option value={1}>1x</option>
                      <option value={2}>2x</option>
                      <option value={4}>4x</option>
                      <option value={8}>8x</option>
                      <option value={16}>16x</option>
                    </select>
                  </label>
                  <label>
                    Data Rate:
                    <select 
                      value={analogChannelConfig.data_rate} 
                      onChange={(e) => setAnalogChannelConfig({...analogChannelConfig, data_rate: parseInt(e.target.value)})}
                    >
                      <option value={128}>128 SPS</option>
                      <option value={250}>250 SPS</option>
                      <option value={490}>490 SPS</option>
                      <option value={920}>920 SPS</option>
                      <option value={1600}>1600 SPS</option>
                      <option value={2400}>2400 SPS</option>
                      <option value={3300}>3300 SPS</option>
                    </select>
                  </label>
                </div>
                <div className="form-actions">
                  <button className="btn btn-sm btn-success" onClick={handleAddAnalogChannel}>
                    Add
                  </button>
                  <button className="btn btn-sm btn-secondary" onClick={() => setShowAddChannel(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {Object.keys(analogChannels).length > 0 ? (
              <div className="analog-channels">
                {Object.entries(analogChannels).map(([channel, channelInfo]) => {
                  const history = voltageHistory[channel] || [];
                  return (
                    <div key={channel} className="analog-channel-item">
                      <div className="channel-info">
                        <div className="channel-header">
                          <span className="channel-number">Ch {channel}</span>
                          <span className="channel-name">{channelInfo.name}</span>
                        </div>
                        <div className="channel-values">
                          <div className="value-group">
                            <span className="value-label">Raw:</span>
                            <span className="value-number">{channelInfo.raw_value}</span>
                          </div>
                          <div className="value-group">
                            <span className="value-label">Voltage:</span>
                            <span className="value-number">{channelInfo.voltage.toFixed(3)}V</span>
                          </div>
                        </div>
                        <div className="channel-stats">
                          <span>Min: {channelInfo.stats.min_voltage.toFixed(2)}V</span>
                          <span>Max: {channelInfo.stats.max_voltage.toFixed(2)}V</span>
                          <span>Avg: {channelInfo.stats.avg_voltage.toFixed(2)}V</span>
                        </div>
                      </div>
                      <div className="channel-chart">
                        <MiniChart data={history} />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="no-channels">
                <span>No analog channels registered</span>
                <small>Use the "Add Channel" button to register ADS1015 channels</small>
              </div>
            )}
          </div>
        </div>
        
        <div className="motor-section">
          <div className="motor-status">
            <h4>Motor Status</h4>
            <div className="motor-info">
              <div className="motor-direction">
                <span className="motor-label">Direction:</span>
                <span className={`motor-value direction-${motorStats.motor_direction}`}>
                  {motorStats.motor_direction === 'forward' ? '← Forward' : 
                   motorStats.motor_direction === 'reverse' ? 'Reverse →' : 
                   '● Stopped'}
                </span>
              </div>
              <div className="motor-speed">
                <span className="motor-label">Speed:</span>
                <div className="speed-display">
                  <span className="speed-value">{(motorStats.motor_speed * 100).toFixed(0)}%</span>
                  <div className="speed-bar">
                    <div 
                      className="speed-fill" 
                      style={{width: `${motorStats.motor_speed * 100}%`}}
                    ></div>
                  </div>
                </div>
              </div>
              <div className="motor-tracking">
                <span className="motor-label">Tracking:</span>
                <span className={`motor-value tracking-${motorStats.tracking_enabled ? 'enabled' : 'disabled'}`}>
                  {motorStats.tracking_enabled ? '● Enabled' : '○ Disabled'}
                </span>
              </div>
            </div>
            
            {/* Clutch Control Section */}
            <div className="clutch-control">
              <h5>Clutch Control</h5>
              <div className="clutch-info">
                <div className="clutch-status">
                  <span className="clutch-label">Status:</span>
                  <span className={`clutch-value status-${motorStats.driver_clutch_engaged ? 'engaged' : 'disengaged'}`}>
                    {motorStats.driver_clutch_engaged ? '● Engaged' : '○ Disengaged'}
                  </span>
                </div>
                <div className="clutch-lock">
                  <span className="clutch-label">Lock:</span>
                  <span className={`clutch-value lock-${motorStats.driver_clutch_locked ? 'locked' : 'unlocked'}`}>
                    {motorStats.driver_clutch_locked ? '🔒 Locked' : '🔓 Unlocked'}
                  </span>
                </div>
                <div className="limit-switches">
                  <span className="clutch-label">Limits:</span>
                  <div className="limit-indicators">
                    <span className={`limit-indicator ${motorStats.driver_forward_limit_active ? 'active' : 'inactive'}`}>
                      ← Forward
                    </span>
                    <span className={`limit-indicator ${motorStats.driver_reverse_limit_active ? 'active' : 'inactive'}`}>
                      Reverse →
                    </span>
                  </div>
                </div>
              </div>
              <div className="clutch-controls">
                <button 
                  className={`btn btn-sm ${motorStats.driver_clutch_locked ? 'btn-success' : 'btn-warning'}`}
                  onClick={handleClutchLockToggle}
                >
                  {motorStats.driver_clutch_locked ? 'Unlock Clutch' : 'Lock Clutch'}
                </button>
                <button 
                  className="btn btn-sm btn-danger"
                  onClick={handleEmergencyDisengage}
                >
                  Emergency Stop
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .io-panel {
          padding: 20px;
        }
        
        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }
        
        .panel-header h3 {
          margin: 0;
          color: #333;
        }
        
        .connection-status {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 12px;
          color: #dc3545;
        }
        
        .status-indicator {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background-color: #28a745;
        }
        
        .status-indicator.offline {
          background-color: #dc3545;
        }
        
        .alert {
          padding: 10px;
          margin: 10px 0;
          border-radius: 5px;
        }
        
        .alert-danger {
          background-color: #f8d7da;
          color: #721c24;
          border: 1px solid #f5c6cb;
        }
        
        .io-content {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        
        .gpio-section, .analog-section, .motor-section {
          background-color: #f8f9fa;
          padding: 15px;
          border-radius: 8px;
          border: 1px solid #dee2e6;
        }
        
        .gpio-status h4, .analog-status h4, .motor-status h4 {
          margin-bottom: 15px;
          color: #495057;
        }
        
        .analog-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 15px;
        }
        
        .btn {
          padding: 6px 12px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
          font-weight: 500;
        }
        
        .btn-sm {
          padding: 4px 8px;
          font-size: 11px;
        }
        
        .btn-primary {
          background-color: #007bff;
          color: white;
        }
        
        .btn-success {
          background-color: #28a745;
          color: white;
        }
        
        .btn-secondary {
          background-color: #6c757d;
          color: white;
        }
        
        .btn-warning {
          background-color: #ffc107;
          color: #212529;
        }
        
        .btn-danger {
          background-color: #dc3545;
          color: white;
        }
        
        .add-channel-form {
          background-color: white;
          padding: 15px;
          border-radius: 5px;
          border: 1px solid #e9ecef;
          margin-bottom: 15px;
        }
        
        .form-row {
          display: flex;
          gap: 15px;
          margin-bottom: 10px;
        }
        
        .form-row label {
          display: flex;
          flex-direction: column;
          gap: 4px;
          font-size: 12px;
          font-weight: 500;
          color: #495057;
        }
        
        .form-row select, .form-row input {
          padding: 4px 8px;
          border: 1px solid #ced4da;
          border-radius: 3px;
          font-size: 12px;
        }
        
        .form-actions {
          display: flex;
          gap: 8px;
          justify-content: flex-end;
        }
        
        .gpio-pins, .analog-channels {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        
        .gpio-pin-item, .analog-channel-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 15px;
          background-color: white;
          border-radius: 5px;
          border: 1px solid #e9ecef;
        }
        
        .analog-channel-item {
          flex-direction: row;
          align-items: flex-start;
        }
        
        .pin-info, .channel-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        
        .channel-info {
          flex: 1;
          gap: 8px;
        }
        
        .pin-number, .channel-number {
          font-weight: bold;
          color: #495057;
          font-size: 14px;
        }
        
        .pin-name, .channel-name {
          color: #6c757d;
          font-size: 12px;
        }

        .pin-direction, .channel-direction {
          color: #707376ff;
          font-size: 10px;
        }
        
        .channel-header {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        
        .channel-values {
          display: flex;
          gap: 15px;
        }
        
        .value-group {
          display: flex;
          gap: 4px;
          align-items: center;
        }
        
        .value-label {
          font-size: 11px;
          color: #6c757d;
          font-weight: 500;
        }
        
        .value-number {
          font-size: 13px;
          font-weight: bold;
          color: #495057;
          font-family: monospace;
        }
        
        .channel-stats {
          display: flex;
          gap: 10px;
          font-size: 10px;
          color: #6c757d;
        }
        
        .channel-chart {
          margin-left: 15px;
          border: 1px solid #e9ecef;
          border-radius: 3px;
          background-color: #fff;
          padding: 4px;
        }
        
        .pin-status {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        
        .status-circle {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          border: 2px solid #dee2e6;
          transition: all 0.3s ease;
        }
        
        .status-circle.lit {
          background-color: #28a745;
          border-color: #28a745;
          box-shadow: 0 0 8px rgba(40, 167, 69, 0.5);
        }
        
        .status-circle.unlit {
          background-color: #6c757d;
          border-color: #6c757d;
        }
        
        .pin-state {
          font-weight: bold;
          font-size: 12px;
          color: #495057;
          min-width: 35px;
        }
        
        .no-pins, .no-channels {
          text-align: center;
          color: #6c757d;
          font-style: italic;
          padding: 20px;
        }
        
        .no-channels {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        
        .no-channels small {
          font-size: 11px;
          color: #adb5bd;
        }
        
        .motor-info {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        
        .motor-direction, .motor-speed, .motor-tracking {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 12px;
          background-color: white;
          border-radius: 5px;
          border: 1px solid #e9ecef;
        }
        
        .motor-label {
          font-weight: 500;
          color: #6c757d;
        }
        
        .motor-value {
          font-weight: bold;
        }
        
        .direction-forward {
          color: #007bff;
        }
        
        .direction-reverse {
          color: #fd7e14;
        }
        
        .direction-stopped {
          color: #6c757d;
        }
        
        .tracking-enabled {
          color: #28a745;
        }
        
        .tracking-disabled {
          color: #6c757d;
        }
        
        .speed-display {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        
        .speed-value {
          font-weight: bold;
          color: #495057;
          min-width: 40px;
          text-align: right;
        }
        
        .speed-bar {
          width: 100px;
          height: 8px;
          background-color: #e9ecef;
          border-radius: 4px;
          overflow: hidden;
        }
        
        .speed-fill {
          height: 100%;
          background-color: #28a745;
          transition: width 0.3s ease;
          border-radius: 4px;
        }
        
        .clutch-control {
          margin-top: 15px;
          padding-top: 15px;
          border-top: 1px solid #e9ecef;
        }
        
        .clutch-control h5 {
          margin: 0 0 10px 0;
          color: #495057;
          font-size: 14px;
        }
        
        .clutch-info {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 10px;
        }
        
        .clutch-status, .clutch-lock, .limit-switches {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 6px 10px;
          background-color: white;
          border-radius: 4px;
          border: 1px solid #e9ecef;
          font-size: 12px;
        }
        
        .clutch-label {
          font-weight: 500;
          color: #6c757d;
        }
        
        .clutch-value {
          font-weight: bold;
          font-size: 11px;
        }
        
        .status-engaged {
          color: #28a745;
        }
        
        .status-disengaged {
          color: #6c757d;
        }
        
        .lock-locked {
          color: #dc3545;
        }
        
        .lock-unlocked {
          color: #28a745;
        }
        
        .limit-indicators {
          display: flex;
          gap: 8px;
        }
        
        .limit-indicator {
          font-size: 10px;
          padding: 2px 6px;
          border-radius: 3px;
          font-weight: 500;
        }
        
        .limit-indicator.active {
          background-color: #dc3545;
          color: white;
        }
        
        .limit-indicator.inactive {
          background-color: #e9ecef;
          color: #6c757d;
        }
        
        .clutch-controls {
          display: flex;
          gap: 8px;
          justify-content: flex-end;
        }
        
        @media (min-width: 1200px) {
          .io-content {
            flex-direction: row;
          }
          
          .gpio-section {
            flex: 1;
          }
          
          .analog-section {
            flex: 1.5;
          }
          
          .motor-section {
            flex: 1;
          }
        }
      `}</style>
    </div>
  );
};

export default IOPanel;
