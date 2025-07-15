import React, { useState, useEffect } from 'react';

function BehaviourPanel({ onStatusUpdate }) {
  const [treeStatus, setTreeStatus] = useState({ 
    nodes: [], 
    currently_running: [], 
    changed: false, 
    tree_running: false 
  });
  const [blackboardData, setBlackboardData] = useState({});
  const [treeRunning, setTreeRunning] = useState(false);
  const [dotGraph, setDotGraph] = useState('');

  // Fetch tree status periodically
  useEffect(() => {
    const fetchTreeStatus = async () => {
      try {
        const response = await fetch('/api/behaviour/status');
        const data = await response.json();
        if (data.success) {
          setTreeStatus(data.status);
          setBlackboardData(data.blackboard || {});
          setTreeRunning(data.running);
        }
      } catch (error) {
        console.error('Failed to fetch tree status:', error);
      }
    };

    // Initial fetch
    fetchTreeStatus();

    // Set up polling every 500ms
    const interval = setInterval(fetchTreeStatus, 500);

    return () => clearInterval(interval);
  }, []);

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

  const fetchDotGraph = async () => {
    try {
      const response = await fetch('/api/behaviour/graph');
      const data = await response.json();
      if (data.success) {
        setDotGraph(data.dot_graph);
      } else {
        onStatusUpdate({ type: 'error', message: data.error || 'Failed to fetch dot graph' });
      }
    } catch (error) {
      onStatusUpdate({ type: 'error', message: `Failed to fetch dot graph: ${error.message}` });
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
        
        <button 
          onClick={fetchDotGraph}
          style={{
            padding: '6px 12px',
            backgroundColor: '#17a2b8',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Generate ASCII Graph
        </button>
      </div>

      {/* Tree Nodes Visualization */}
      <div className="tree-visualization" style={{ marginBottom: '20px' }}>
        <h4>Current Tree State</h4>
        <div className="tree-nodes" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {treeStatus.nodes && treeStatus.nodes.length > 0 ? (
            treeStatus.nodes.map(node => (
              <div 
                key={node.id} 
                className={`node ${node.status.toLowerCase()}`}
                style={{
                  padding: '10px',
                  border: `2px solid ${getStatusColor(node.status)}`,
                  borderRadius: '5px',
                  backgroundColor: treeStatus.currently_running.includes(node.id) ? '#00465fff' : '#2d2d2dff'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span 
                    style={{ 
                      fontSize: '16px', 
                      color: getStatusColor(node.status),
                      fontWeight: 'bold'
                    }}
                  >
                    {getStatusIcon(node.status)}
                  </span>
                  <strong>{node.name}</strong>
                  <span style={{ color: '#6c757d', fontSize: '12px' }}>({node.type})</span>
                  {treeStatus.currently_running.includes(node.id) && (
                    <span style={{ 
                      backgroundColor: '#ffc107', 
                      color: '#212529', 
                      padding: '2px 6px', 
                      borderRadius: '3px', 
                      fontSize: '10px',
                      fontWeight: 'bold'
                    }}>
                      ACTIVE
                    </span>
                  )}
                </div>
                <div style={{ marginTop: '4px' }}>
                  <span style={{ fontWeight: 'bold' }}>Status:</span> {node.status}
                </div>
                {node.feedback && (
                  <div style={{ marginTop: '4px', fontStyle: 'italic', color: '#6c757d' }}>
                    {node.feedback}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div style={{ padding: '20px', textAlign: 'center', color: '#6c757d' }}>
              No tree nodes to display. Start the behaviour tree to see active nodes.
            </div>
          )}
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

      {/* Dot Graph Display */}
      {dotGraph && (
        <div className="dot-graph" style={{ marginBottom: '20px' }}>
          <h4>Tree Structure (Dot Graph)</h4>
          <pre style={{ 
            backgroundColor: '#2d2d2dff', 
            padding: '10px', 
            border: '1px solid #dee2e6', 
            borderRadius: '5px',
            fontSize: '10px',
            overflow: 'auto',
            maxHeight: '300px'
          }}>
            {dotGraph}
          </pre>
        </div>
      )}
    </div>
  );
}

export default BehaviourPanel;
