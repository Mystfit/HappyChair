import React, { useState, useEffect } from 'react';

const IOPanel = ({ onStatusUpdate }) => {
  const [cameraActive, setCameraActive] = useState(false);
  const [detectionStats, setDetectionStats] = useState({
    person_count: 0,
    unique_people: 0,
    fps: 0,
    last_update: 0,
    tracked_person_id: null,
    motor_direction: 'stopped',
    motor_speed: 0.0,
    tracking_enabled: false
  });
  const [gpioPins, setGpioPins] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Poll camera status every second
  useEffect(() => {
    const interval = setInterval(fetchCameraStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchCameraStatus = async () => {
    try {
      const response = await fetch('/api/camera/status');
      const data = await response.json();
      
      if (data.success) {
        setCameraActive(data.running);
        setDetectionStats(data.stats);
        setGpioPins(data.gpio_pins || {});
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch camera status');
      }
    } catch (err) {
      setError(`Network error: ${err.message}`);
    }
  };

  const handleStartCamera = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/camera/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      const data = await response.json();
      
      if (data.success) {
        setCameraActive(true);
        if (onStatusUpdate) {
          onStatusUpdate({
            type: 'success',
            message: 'Camera started successfully'
          });
        }
      } else {
        setError(data.error || 'Failed to start camera');
        if (onStatusUpdate) {
          onStatusUpdate({
            type: 'error',
            message: data.error || 'Failed to start camera'
          });
        }
      }
    } catch (err) {
      const errorMsg = `Failed to start camera: ${err.message}`;
      setError(errorMsg);
      if (onStatusUpdate) {
        onStatusUpdate({
          type: 'error',
          message: errorMsg
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleStopCamera = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/camera/stop', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      const data = await response.json();
      
      if (data.success) {
        setCameraActive(false);
        // Reset stats when camera stops
        setDetectionStats({
          person_count: 0,
          unique_people: 0,
          fps: 0,
          last_update: 0,
          tracked_person_id: null,
          motor_direction: 'stopped',
          motor_speed: 0.0,
          tracking_enabled: false
        });
        setGpioPins({});
        if (onStatusUpdate) {
          onStatusUpdate({
            type: 'success',
            message: 'Camera stopped successfully'
          });
        }
      } else {
        setError(data.error || 'Failed to stop camera');
        if (onStatusUpdate) {
          onStatusUpdate({
            type: 'error',
            message: data.error || 'Failed to stop camera'
          });
        }
      }
    } catch (err) {
      const errorMsg = `Failed to stop camera: ${err.message}`;
      setError(errorMsg);
      if (onStatusUpdate) {
        onStatusUpdate({
          type: 'error',
          message: errorMsg
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleImageError = (e) => {
    console.log('Camera stream error:', e);
    // The stream will show "Camera Not Active" when not running
  };

  const formatLastUpdate = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString();
  };

  return (
    <div className="camera-panel">
      <div className="panel-header">
        <h3>IO Control Panel</h3>
      </div>
      
      <div className="camera-controls">
        <button 
          className={`btn ${cameraActive ? 'btn-danger' : 'btn-success'}`}
          onClick={cameraActive ? handleStopCamera : handleStartCamera}
          disabled={loading}
        >
          {loading ? 'Processing...' : (cameraActive ? 'Stop Camera' : 'Start Camera')}
        </button>
        
        <div className="camera-status">
          <span className={`status-indicator ${cameraActive ? 'active' : 'inactive'}`}>
            {cameraActive ? '● Active' : '○ Inactive'}
          </span>
        </div>
      </div>

      {error && (
        <div className="alert alert-danger">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="camera-content">
        <div className="camera-feed-container">
          <img 
            src="/api/camera/stream" 
            alt="Live Camera Feed"
            className="camera-feed"
            onError={handleImageError}
            style={{
              width: '100%',
              maxWidth: '640px',
              height: 'auto',
              border: '2px solid #ddd',
              borderRadius: '8px',
              backgroundColor: '#000'
            }}
          />
        </div>
        
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
        
        <div className="detection-stats">
          <h4>Detection Statistics</h4>
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-label">Current Persons:</span>
              <span className="stat-value">{detectionStats.person_count}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Unique People:</span>
              <span className="stat-value">{detectionStats.unique_people || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Tracking Person ID:</span>
              <span className="stat-value">{detectionStats.tracked_person_id || 'None'}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">FPS:</span>
              <span className="stat-value">{detectionStats.fps.toFixed(1)}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Last Update:</span>
              <span className="stat-value">{formatLastUpdate(detectionStats.last_update)}</span>
            </div>
          </div>
          
          <div className="motor-status">
            <h5>Motor Status</h5>
            <div className="motor-info">
              <div className="motor-direction">
                <span className="motor-label">Direction:</span>
                <span className={`motor-value direction-${detectionStats.motor_direction}`}>
                  {detectionStats.motor_direction === 'forward' ? '← Forward' : 
                   detectionStats.motor_direction === 'reverse' ? 'Reverse →' : 
                   '● Stopped'}
                </span>
              </div>
              <div className="motor-speed">
                <span className="motor-label">Speed:</span>
                <div className="speed-display">
                  <span className="speed-value">{(detectionStats.motor_speed * 100).toFixed(0)}%</span>
                  <div className="speed-bar">
                    <div 
                      className="speed-fill" 
                      style={{width: `${detectionStats.motor_speed * 100}%`}}
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .camera-panel {
          padding: 20px;
        }
        
        .gpio-status {
          background-color: #f8f9fa;
          padding: 15px;
          border-radius: 8px;
          border: 1px solid #dee2e6;
          margin-bottom: 20px;
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
        
        .panel-header h3 {
          margin-bottom: 20px;
          color: #333;
        }
        
        .camera-controls {
          display: flex;
          align-items: center;
          gap: 15px;
          margin-bottom: 20px;
        }
        
        .camera-controls button {
          padding: 10px 20px;
          font-size: 16px;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          transition: background-color 0.3s;
        }
        
        .btn-success {
          background-color: #28a745;
          color: white;
        }
        
        .btn-success:hover:not(:disabled) {
          background-color: #218838;
        }
        
        .btn-danger {
          background-color: #dc3545;
          color: white;
        }
        
        .btn-danger:hover:not(:disabled) {
          background-color: #c82333;
        }
        
        .btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        
        .status-indicator {
          font-weight: bold;
          padding: 5px 10px;
          border-radius: 15px;
          font-size: 14px;
        }
        
        .status-indicator.active {
          background-color: #d4edda;
          color: #155724;
        }
        
        .status-indicator.inactive {
          background-color: #f8d7da;
          color: #721c24;
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
        
        .camera-content {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        
        .camera-feed-container {
          text-align: center;
        }
        
        .detection-stats {
          background-color: #f8f9fa;
          padding: 15px;
          border-radius: 8px;
          border: 1px solid #dee2e6;
        }
        
        .detection-stats h4 {
          margin-bottom: 15px;
          color: #495057;
        }
        
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 10px;
        }
        
        .stat-item {
          display: flex;
          justify-content: space-between;
          padding: 8px 12px;
          background-color: white;
          border-radius: 5px;
          border: 1px solid #e9ecef;
        }
        
        .stat-label {
          font-weight: 500;
          color: #6c757d;
        }
        
        .stat-value {
          font-weight: bold;
          color: #495057;
        }
        
        .motor-status {
          margin-top: 20px;
          padding-top: 15px;
          border-top: 1px solid #dee2e6;
        }
        
        .motor-status h5 {
          margin-bottom: 10px;
          color: #495057;
          font-size: 16px;
        }
        
        .motor-info {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        
        .motor-direction, .motor-speed {
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
          .camera-content {
            flex-direction: row;
          }
          
          .camera-feed-container {
            flex: 2;
          }
          
          .detection-stats {
            flex: 1;
            min-width: 300px;
          }
        }
      `}</style>
    </div>
  );
};

export default IOPanel;
