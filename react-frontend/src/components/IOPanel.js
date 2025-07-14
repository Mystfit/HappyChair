import React, { useState, useEffect } from 'react';

const IOPanel = ({ onStatusUpdate }) => {
  const [motorStats, setMotorStats] = useState({
    motor_direction: 'stopped',
    motor_speed: 0.0,
    tracking_enabled: false
  });
  const [gpioPins, setGpioPins] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Poll GPIO and motor status every second
  useEffect(() => {
    const interval = setInterval(fetchIOStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchIOStatus = async () => {
    try {
      // Fetch GPIO pins
      const gpioResponse = await fetch('/api/gpio/pins');
      const gpioData = await gpioResponse.json();
      
      // Fetch motor status
      const motorResponse = await fetch('/api/yaw/status');
      const motorData = await motorResponse.json();
      
      if (gpioData.success) {
        setGpioPins(gpioData.pins || {});
      }
      
      if (motorData.success) {
        setMotorStats({
          motor_direction: motorData.motor_direction,
          motor_speed: motorData.motor_speed,
          tracking_enabled: motorData.tracking_enabled
        });
      }
      
      setError(null);
    } catch (err) {
      setError(`Network error: ${err.message}`);
    }
  };

  return (
    <div className="io-panel">
      <div className="panel-header">
        <h3>GPIO & Motor Control Panel</h3>
      </div>

      {error && (
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="io-content">
        <div className="gpio-status">
          <h4>GPIO Pin Status</h4>
          {Object.keys(gpioPins).length > 0 ? (
            <div className="gpio-pins">
              {Object.entries(gpioPins).map(([pinNumber, pinInfo]) => (
                <div key={pinNumber} className="gpio-pin-item">
                  <div className="pin-info">
                    <span className="pin-number">Pin {pinNumber}</span>
                    <span className="pin-name">{pinInfo.name}</span>
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
        </div>
      </div>

      <style jsx>{`
        .io-panel {
          padding: 20px;
        }
        
        .panel-header h3 {
          margin-bottom: 20px;
          color: #333;
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
        
        .gpio-status {
          background-color: #f8f9fa;
          padding: 15px;
          border-radius: 8px;
          border: 1px solid #dee2e6;
        }
        
        .gpio-status h4 {
          margin-bottom: 15px;
          color: #495057;
        }
        
        .gpio-pins {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        
        .gpio-pin-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 15px;
          background-color: white;
          border-radius: 5px;
          border: 1px solid #e9ecef;
        }
        
        .pin-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        
        .pin-number {
          font-weight: bold;
          color: #495057;
          font-size: 14px;
        }
        
        .pin-name {
          color: #6c757d;
          font-size: 12px;
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
        
        .no-pins {
          text-align: center;
          color: #6c757d;
          font-style: italic;
          padding: 20px;
        }
        
        .motor-status {
          background-color: #f8f9fa;
          padding: 15px;
          border-radius: 8px;
          border: 1px solid #dee2e6;
        }
        
        .motor-status h4 {
          margin-bottom: 15px;
          color: #495057;
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
        
        @media (min-width: 768px) {
          .io-content {
            flex-direction: row;
          }
          
          .gpio-status {
            flex: 1;
          }
          
          .motor-status {
            flex: 1;
          }
        }
      `}</style>
    </div>
  );
};

export default IOPanel;
