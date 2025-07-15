import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../contexts/WebSocketContext';
import { AnsiUp } from 'ansi_up/ansi_up.js'

const ansi_up = new AnsiUp();

function BehaviourPanel({ onStatusUpdate }) {
  const [treeRunning, setTreeRunning] = useState(false);

  // Use WebSocket context for real-time updates
  const { data: wsData, isConnected, connectionError } = useWebSocket();
  const treeStatus = wsData.behaviour_status || { nodes: [], currently_running: [], changed: false, tree_running: false };
  const blackboardData = wsData.blackboard_data || {};
  const asciiGraph = wsData.graph_data || '';

  // Update local tree running state when websocket data changes
  useEffect(() => {
    if (treeStatus.tree_running !== undefined) {
      setTreeRunning(treeStatus.tree_running);
    }
  }, [treeStatus.tree_running]);

  const startTree = async () => {
    try {
      const response = await fetch('/api/behaviour/start', { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        setTreeRunning(true);
        onStatusUpdate({ type: 'success', message: 'Behaviour tree started' });
      } else {
        onStatusUpdate({ type: 'error', message: data.error || 'Failed to start tree' });
      }
    } catch (error) {
      onStatusUpdate({ type: 'error', message: `Failed to start tree: ${error.message}` });
    }
  };

  const stopTree = async () => {
    try {
      const response = await fetch('/api/behaviour/stop', { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        setTreeRunning(false);
        onStatusUpdate({ type: 'success', message: 'Behaviour tree stopped' });
      } else {
        onStatusUpdate({ type: 'error', message: data.error || 'Failed to stop tree' });
      }
    } catch (error) {
      onStatusUpdate({ type: 'error', message: `Failed to stop tree: ${error.message}` });
    }
  };


  const getStatusColor = (status) => {
    switch (status) {
      case 'SUCCESS': return '#28a745';
      case 'FAILURE': return '#dc3545';
      case 'RUNNING': return '#007bff';
      case 'INVALID': return '#6c757d';
      default: return '#6c757d';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'SUCCESS': return '✓';
      case 'FAILURE': return '✕';
      case 'RUNNING': return '⟳';
      case 'INVALID': return '-';
      default: return '?';
    }
  };

  return (
    <div className="behaviour-panel">
      <h3>Behaviour Tree Control</h3>
      
      {/* Tree Controls */}
      <div className="tree-controls" style={{ marginBottom: '20px', padding: '15px', border: '1px solid #ddd', borderRadius: '5px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
          <button 
            onClick={startTree} 
            disabled={treeRunning}
            style={{
              padding: '8px 16px',
              backgroundColor: treeRunning ? '#6c757d' : '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: treeRunning ? 'not-allowed' : 'pointer'
            }}
          >
            Start Tree
          </button>
          <button 
            onClick={stopTree} 
            disabled={!treeRunning}
            style={{
              padding: '8px 16px',
              backgroundColor: !treeRunning ? '#6c757d' : '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: !treeRunning ? 'not-allowed' : 'pointer'
            }}
          >
            Stop Tree
          </button>
          <span 
            className={`status ${treeRunning ? 'running' : 'stopped'}`}
            style={{
              padding: '4px 8px',
              borderRadius: '4px',
              backgroundColor: treeRunning ? '#d4edda' : '#f8d7da',
              color: treeRunning ? '#155724' : '#721c24',
              fontWeight: 'bold'
            }}
          >
            {treeRunning ? 'Running' : 'Stopped'}
          </span>
        </div>
        
      </div>


      {/* Blackboard Data */}
      <div className="blackboard-data" style={{ marginBottom: '20px' }}>
        <h4>Blackboard Data</h4>
        <div style={{ 
          padding: '10px', 
          backgroundColor: '#2d2d2dff', 
          border: '1px solid #dee2e6', 
          borderRadius: '5px',
          fontFamily: 'monospace',
          fontSize: '12px'
        }}>
          {Object.keys(blackboardData).length > 0 ? (
            Object.entries(blackboardData).map(([key, value]) => (
              <div key={key} style={{ marginBottom: '4px' }}>
                <strong>{key}:</strong> {JSON.stringify(value)}
              </div>
            ))
          ) : (
            <div style={{ color: '#6c757d' }}>No blackboard data available</div>
          )}
        </div>
      </div>

      {/* ASCII Graph Display */}
      {asciiGraph && (
        <div className="ascii-graph" style={{ marginBottom: '20px' }}>
          <h4>Tree Structure (ASCII Graph)</h4>
          <pre 
            style={{ 
              backgroundColor: '#2d2d2dff', 
              padding: '10px', 
              border: '1px solid #dee2e6', 
              borderRadius: '5px',
              fontSize: '10px',
              overflow: 'auto',
              maxHeight: '300px'
            }}
            dangerouslySetInnerHTML={{
              __html: ansi_up.ansi_to_html(asciiGraph)
            }}
          />
        </div>
      )}

      {/* WebSocket Connection Status */}
      {!isConnected && (
        <div style={{ 
          padding: '10px', 
          backgroundColor: '#dc3545', 
          color: 'white', 
          borderRadius: '5px',
          marginBottom: '20px'
        }}>
          WebSocket disconnected. Real-time updates unavailable.
          {connectionError && <div>Error: {connectionError}</div>}
        </div>
      )}
    </div>
  );
}

export default BehaviourPanel;
