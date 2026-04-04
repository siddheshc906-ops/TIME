// frontend/src/hooks/useWebSocket.js
import { useEffect, useRef, useCallback, useState } from 'react';

export const useWebSocket = (userId) => {
  const wsRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef(null);
  const isMounted = useRef(true);
  const isConnectingRef = useRef(false);
  const maxReconnectAttempts = 5;

  // ✅ Event emitter system to support socket.on() / socket.off()
  const listenersRef = useRef({});

  const emitEvent = useCallback((type, data) => {
    const handlers = listenersRef.current[type] || [];
    handlers.forEach(handler => handler(data));
  }, []);

  // ✅ Socket-like object with .on() and .off() support
  const socketApiRef = useRef({
    on: (event, handler) => {
      if (!listenersRef.current[event]) {
        listenersRef.current[event] = [];
      }
      listenersRef.current[event].push(handler);
    },
    off: (event, handler) => {
      if (!listenersRef.current[event]) return;
      listenersRef.current[event] = listenersRef.current[event].filter(h => h !== handler);
    },
    emit: (event, data) => {
      emitEvent(event, data);
    }
  });

  const connectWebSocket = useCallback(() => {
    if (!userId) return;

    // ✅ Prevent multiple simultaneous connection attempts
    if (isConnectingRef.current) {
      console.log('⏳ Connection already in progress, skipping...');
      return;
    }

    // ✅ Stop after max attempts
    if (reconnectAttemptRef.current >= maxReconnectAttempts) {
      console.log(`❌ Max reconnection attempts (${maxReconnectAttempts}) reached. Stopping.`);
      return;
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    isConnectingRef.current = true;
    const wsUrl = `ws://localhost:8000/api/ws/${userId}`;
    console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log('✅ WebSocket connected successfully');
        if (isMounted.current) {
          setIsConnected(true);
          reconnectAttemptRef.current = 0;
          isConnectingRef.current = false;
        }

        try {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'ping' }));
          }
        } catch (err) {
          console.error('Error sending ping:', err);
        }
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('📨 WebSocket message:', data);

          // ✅ Fire event to all registered listeners
          emitEvent(data.type, data);

          switch (data.type) {
            case 'pong':
              console.log('🏓 Pong received');
              break;
            case 'notification':
              console.log('🔔 Notification:', data);
              break;
            case 'task:created':
            case 'task:updated':
            case 'task:deleted':
            case 'task:completed':
              console.log('📝 Task event:', data.type);
              break;
            case 'achievement':
              console.log('🏆 Achievement:', data);
              break;
            default:
              console.log('Unknown message type:', data.type);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      wsRef.current.onclose = (event) => {
        console.log(`🔌 WebSocket disconnected: ${event.code}`);
        if (isMounted.current) {
          setIsConnected(false);
        }
        isConnectingRef.current = false;

        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }

        if (event.code !== 1000 && reconnectAttemptRef.current < maxReconnectAttempts) {
          reconnectAttemptRef.current++;
          console.log(`🔄 Reconnection attempt ${reconnectAttemptRef.current} of ${maxReconnectAttempts}`);

          reconnectTimeoutRef.current = setTimeout(() => {
            if (isMounted.current && reconnectAttemptRef.current < maxReconnectAttempts) {
              connectWebSocket();
            }
          }, 3000);
        } else if (reconnectAttemptRef.current >= maxReconnectAttempts) {
          console.log(`❌ Stopping reconnection attempts after ${maxReconnectAttempts} failures`);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      isConnectingRef.current = false;
    }
  }, [userId, emitEvent]);

  // Connect on mount
  useEffect(() => {
    isMounted.current = true;

    const timeoutId = setTimeout(() => {
      if (isMounted.current) {
        connectWebSocket();
      }
    }, 1000);

    return () => {
      clearTimeout(timeoutId);
      isMounted.current = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmounting");
        wsRef.current = null;
      }
    };
  }, [connectWebSocket]);

  // Send message helper
  const sendMessage = useCallback((message) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify(message));
        return true;
      } catch (err) {
        console.error('Error sending message:', err);
        return false;
      }
    }
    return false;
  }, []);

  // Emit helpers
  const emitTaskCreated = useCallback((task) => {
    sendMessage({ type: 'task:created', task });
  }, [sendMessage]);

  const emitTaskUpdated = useCallback((task) => {
    sendMessage({ type: 'task:updated', task });
  }, [sendMessage]);

  const emitTaskDeleted = useCallback((taskId) => {
    sendMessage({ type: 'task:deleted', taskId, userId });
  }, [sendMessage, userId]);

  const emitTaskCompleted = useCallback((task) => {
    sendMessage({ type: 'task:completed', task, userId });
  }, [sendMessage, userId]);

  const emitScheduleReady = useCallback((schedule) => {
    sendMessage({ type: 'schedule:ready', schedule });
  }, [sendMessage]);

  const emitUserPresence = useCallback((status) => {
    sendMessage({ type: 'user:presence', userId, status });
  }, [sendMessage, userId]);

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    reconnectAttemptRef.current = 0;
    isConnectingRef.current = false;
    connectWebSocket();
  }, [connectWebSocket]);

  return {
    isConnected,
    socket: socketApiRef.current, // ✅ Now supports .on() and .off()
    sendMessage,
    emitTaskCreated,
    emitTaskUpdated,
    emitTaskDeleted,
    emitTaskCompleted,
    emitScheduleReady,
    emitUserPresence,
    reconnect,
    connectionStatus: isConnected ? 'connected' : 'disconnected',
    isReady: isConnected && wsRef.current?.readyState === WebSocket.OPEN
  };
};