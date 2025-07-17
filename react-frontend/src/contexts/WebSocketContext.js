import React, { createContext, useContext, useEffect, useState, useRef } from 'react';

const WebSocketContext = createContext();

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

export const WebSocketProvider = ({ children }) => {
  const [data, setData] = useState({
    is_playing: false,
    animation_mode: 'transport',
    global_framerate: 30,
    active_animations: [],
    gpio_pins: {},
    analog_channels: {},
    camera_stats: {},
    motor_stats: {},
    behaviour_status: { nodes: [], currently_running: [], changed: false, tree_running: false },
    blackboard_data: {},
    graph_data: '',
  });
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 1000; // 1 second

  const connectWebSocket = () => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/ws/status`;
      
      console.log('Connecting to WebSocket:', wsUrl);
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttemptsRef.current = 0;
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const newData = JSON.parse(event.data);
          setData(newData);
        } catch (error) {
          console.error('WebSocket parse error:', error);
          setConnectionError(`Parse error: ${error.message}`);
        }
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionError('Connection error occurred');
      };
      
      wsRef.current.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        
        // Only attempt to reconnect if it wasn't a manual close
        if (event.code !== 1000 && reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(
            baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current),
            30000 // Max 30 seconds
          );
          
          console.log(`Attempting to reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connectWebSocket();
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          setConnectionError('Max reconnection attempts reached');
        }
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setConnectionError(`Connection failed: ${error.message}`);
      
      // Retry connection after delay
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = Math.min(
          baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current),
          30000
        );
        
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttemptsRef.current++;
          connectWebSocket();
        }, delay);
      }
    }
  };

  useEffect(() => {
    connectWebSocket();
    
    return () => {
      // Clear reconnect timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      // Close WebSocket connection
      if (wsRef.current) {
        if (wsRef.current.readyState === WebSocket.OPEN || 
            wsRef.current.readyState === WebSocket.CONNECTING) {
          wsRef.current.close(1000, 'Component unmounting');
        }
      }
    };
  }, []);

  const value = {
    data,
    isConnected,
    connectionError,
    reconnect: () => {
      reconnectAttemptsRef.current = 0;
      connectWebSocket();
    }
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
