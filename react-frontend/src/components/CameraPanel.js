import React, { useState, useEffect } from 'react';

const CameraPanel = ({ onStatusUpdate }) => {
  const [cameraActive, setCameraActive] = useState(false);
  const [detectionStats, setDetectionStats] = useState({
    person_count: 0,
    unique_people: 0,
    fps: 0,
    last_update: 0,
    tracked_person_id: null
  });
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
          tracked_person_id: null
        });
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

  const handleRestartCamera = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/camera/restart', {
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
            message: 'Camera restarted successfully'
          });
        }
      } else {
        setError(data.error || 'Failed to restart camera');
        if (onStatusUpdate) {
          onStatusUpdate({
            type: 'error',
            message: data.error || 'Failed to restart camera'
          });
        }
      }
    } catch (err) {
      const errorMsg = `Failed to restart camera: ${err.message}`;
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
        <h3>Camera Control Panel</h3>
      </div>
      
      <div className="camera-controls">
        <button 
          className={`btn ${cameraActive ? 'btn-danger' : 'btn-success'}`}
          onClick={cameraActive ? handleStopCamera : handleStartCamera}
          disabled={loading}
        >
          {loading ? 'Processing...' : (cameraActive ? 'Stop Camera' : 'Start Camera')}
        </button>
        
        <button 
          className="btn btn-warning"
          onClick={handleRestartCamera}
          disabled={loading || !cameraActive}
        >
          {loading ? 'Processing...' : 'Restart Camera'}
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
              <span className="stat-value">{detectionStats.fps ? detectionStats.fps.toFixed(1) : '0.0'}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Last Update:</span>
              <span className="stat-value">{formatLastUpdate(detectionStats.last_update)}</span>
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .camera-panel {
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
          flex-wrap: wrap;
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
        
        .btn-warning {
          background-color: #ffc107;
          color: #212529;
        }
        
        .btn-warning:hover:not(:disabled) {
          background-color: #e0a800;
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

export default CameraPanel;
