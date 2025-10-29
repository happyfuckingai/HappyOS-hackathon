import React, { createContext, useContext, useState, useEffect, ReactNode, useRef, useCallback, useMemo } from 'react';
import { SSEContextType, EventMessage } from '../types';

const SSEContext = createContext<SSEContextType | undefined>(undefined);

export const useSSE = () => {
  const context = useContext(SSEContext);
  if (context === undefined) {
    throw new Error('useSSE must be used within an SSEProvider');
  }
  return context;
};

interface SSEProviderProps {
  children: ReactNode;
}

export const SSEProvider: React.FC<SSEProviderProps> = ({ children }) => {
  const [events, setEvents] = useState<EventMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const agentResponseSourceRef = useRef<EventSource | null>(null);
  const currentRoomIdRef = useRef<string | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000; // 1 second

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const getReconnectDelay = useCallback(() => {
    // Exponential backoff with jitter
    const delay = Math.min(
      baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current),
      30000 // Max 30 seconds
    );
    return delay + Math.random() * 1000; // Add jitter
  }, []);

  const parseBackendEvent = useCallback((data: any): EventMessage | null => {
    try {
      // Handle the specific backend event structure from streaming_routes.py
      // Backend sends: { timestamp, channel, meeting_id, data: {...} }
      
      if (data.data?.type) {
        // Direct event message with explicit type
        return {
          type: data.data.type,
          ...data.data,
          timestamp: data.timestamp || new Date().toISOString()
        } as EventMessage;
      }
      
      // Handle agent responses (from agent-responses endpoint)
      if (data.response) {
        return {
          type: 'agent_response',
          message: data.response,
          context: { persona: data.persona || 'AI' },
          timestamp: data.timestamp || new Date().toISOString()
        } as EventMessage;
      }
      
      // Handle summary/context updates from Redis channels
      if (data.data?.summary || data.data?.context) {
        return {
          type: 'note',
          content: data.data.summary || data.data.context,
          speaker: data.data?.speaker,
          timestamp: data.timestamp || new Date().toISOString()
        } as EventMessage;
      }
      
      // Handle action items from Redis channels
      if (data.data?.actions) {
        const actions = Array.isArray(data.data.actions) ? data.data.actions : [data.data.actions];
        return {
          type: 'action',
          description: actions.map((a: any) => a.what || a.description || a).join(', '),
          assignee: data.data?.assignee,
          dueDate: data.data?.dueDate,
          timestamp: data.timestamp || new Date().toISOString()
        } as EventMessage;
      }
      
      // Handle generic data from Redis channels based on channel type
      if (data.channel && data.data) {
        switch (data.channel) {
          case 'summary':
            return {
              type: 'note',
              content: typeof data.data === 'string' ? data.data : JSON.stringify(data.data),
              timestamp: data.timestamp || new Date().toISOString()
            } as EventMessage;
          
          case 'events':
            // Try to extract meaningful content from events
            if (data.data.content || data.data.message) {
              return {
                type: 'note',
                content: data.data.content || data.data.message,
                speaker: data.data.speaker,
                timestamp: data.timestamp || new Date().toISOString()
              } as EventMessage;
            }
            break;
            
          case 'visuals':
            // Visual data might contain action items or notes
            if (data.data.actions) {
              return {
                type: 'action',
                description: Array.isArray(data.data.actions) 
                  ? data.data.actions.join(', ') 
                  : data.data.actions,
                timestamp: data.timestamp || new Date().toISOString()
              } as EventMessage;
            }
            break;
        }
      }
      
      return null;
    } catch (error) {
      console.error('Failed to parse backend event:', error, data);
      return null;
    }
  }, []);

  const handleEventSourceMessage = useCallback((event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      
      // Handle different event types from backend
      switch (event.type) {
        case 'connected':
          console.log('SSE connected:', data);
          setIsConnected(true);
          setConnectionError(null);
          setIsReconnecting(false);
          reconnectAttemptsRef.current = 0;
          break;
          
        case 'heartbeat':
          // Update connection status based on heartbeat
          if (data.status === 'unhealthy') {
            setConnectionError('Connection unhealthy');
          }
          break;
          
        case 'error':
          console.error('SSE error event:', data);
          setConnectionError(data.error || 'Unknown SSE error');
          break;
          
        case 'summary':
        case 'visuals':
        case 'events':
        case 'agent-response':
          // Parse AI events from the backend data structure
          if (data.data) {
            const eventMessage = parseBackendEvent(data);
            if (eventMessage) {
              setEvents(prev => [...prev, eventMessage]);
            }
          }
          break;
          
        default:
          // Handle generic message events
          if (data.meeting_id && data.data) {
            const eventMessage = parseBackendEvent(data);
            if (eventMessage) {
              setEvents(prev => [...prev, eventMessage]);
            }
          }
      }
    } catch (error) {
      console.error('Failed to parse SSE event:', error, event.data);
    }
  }, [parseBackendEvent]);

  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    if (agentResponseSourceRef.current) {
      agentResponseSourceRef.current.close();
      agentResponseSourceRef.current = null;
    }
    
    setIsConnected(false);
    setIsReconnecting(false);
    setConnectionError(null);
    currentRoomIdRef.current = null;
    reconnectAttemptsRef.current = 0;
  }, [clearReconnectTimeout]);

  const connect = useCallback((roomId: string) => {
    // Close existing connection
    disconnect();

    currentRoomIdRef.current = roomId;
    setConnectionError(null);
    setIsReconnecting(reconnectAttemptsRef.current > 0);

    try {
      // Connect to backend SSE endpoint based on the actual backend implementation
      const baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      
      // Primary endpoint - events channel for comprehensive updates (matches backend route)
      const eventSource = new EventSource(`${baseUrl}/sse/${roomId}/events`, {
        withCredentials: false // Adjust based on your auth setup
      });
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('SSE connection opened for room:', roomId);
        setIsConnected(true);
        setConnectionError(null);
        setIsReconnecting(false);
        reconnectAttemptsRef.current = 0;
      };

      eventSource.onmessage = handleEventSourceMessage;

      eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        setIsConnected(false);
        
        if (eventSource.readyState === EventSource.CLOSED) {
          setConnectionError('Connection closed by server');
        } else {
          setConnectionError('Connection error occurred');
        }

        // Attempt to reconnect with exponential backoff
        if (reconnectAttemptsRef.current < maxReconnectAttempts && currentRoomIdRef.current) {
          reconnectAttemptsRef.current++;
          const delay = getReconnectDelay();
          
          console.log(`Attempting to reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (currentRoomIdRef.current) {
              connect(currentRoomIdRef.current);
            }
          }, delay);
        } else {
          setConnectionError('Max reconnection attempts reached');
          setIsReconnecting(false);
        }
      };

      // Handle specific event types
      eventSource.addEventListener('connected', handleEventSourceMessage);
      eventSource.addEventListener('heartbeat', handleEventSourceMessage);
      eventSource.addEventListener('error', handleEventSourceMessage);
      eventSource.addEventListener('summary', handleEventSourceMessage);
      eventSource.addEventListener('visuals', handleEventSourceMessage);
      eventSource.addEventListener('events', handleEventSourceMessage);

      // Also connect to agent responses endpoint for TTS/agent interactions
      const agentResponseSource = new EventSource(`${baseUrl}/sse/${roomId}/agent-responses`, {
        withCredentials: false
      });
      agentResponseSourceRef.current = agentResponseSource;

      agentResponseSource.onmessage = handleEventSourceMessage;
      agentResponseSource.onerror = (error) => {
        console.warn('Agent response SSE connection error (non-critical):', error);
        // Don't fail the main connection for agent response errors
      };
      agentResponseSource.addEventListener('agent-response', handleEventSourceMessage);
      agentResponseSource.addEventListener('connected', handleEventSourceMessage);
      agentResponseSource.addEventListener('heartbeat', handleEventSourceMessage);

    } catch (error) {
      console.error('Failed to create SSE connection:', error);
      setConnectionError('Failed to establish connection');
      setIsConnected(false);
    }
  }, [handleEventSourceMessage, getReconnectDelay, disconnect]);

  const sendMessage = useCallback(async (message: any) => {
    // For SSE, we send messages via regular HTTP POST to trigger backend events
    try {
      const baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const token = localStorage.getItem('auth_token');
      
      const response = await fetch(`${baseUrl}/api/meetings/${currentRoomIdRef.current}/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(message),
      });

      if (!response.ok) {
        throw new Error(`Failed to send message: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  const getEventsByType = useCallback((type: EventMessage['type']) => {
    return events.filter(event => event.type === type);
  }, [events]);

  // Handle online/offline state changes
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      // Reconnect if we have a room and were previously offline
      if (currentRoomIdRef.current && !isConnected) {
        console.log('Back online, attempting to reconnect...');
        connect(currentRoomIdRef.current);
      }
    };

    const handleOffline = () => {
      setIsOnline(false);
      setConnectionError('Connection lost - you are offline');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      disconnect();
    };
  }, [disconnect, connect, isConnected]);

  const value: SSEContextType = useMemo(() => ({
    events,
    isConnected,
    sendMessage,
    connect,
    disconnect,
    // Extended interface for better UX
    connectionError,
    isReconnecting,
    clearEvents,
    getEventsByType,
    // Additional state for better UX
    isOnline,
  }), [
    events,
    isConnected,
    sendMessage,
    connect,
    disconnect,
    connectionError,
    isReconnecting,
    clearEvents,
    getEventsByType,
    isOnline,
  ]);

  return (
    <SSEContext.Provider value={value}>
      {children}
    </SSEContext.Provider>
  );
};