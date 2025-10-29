import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { UIResource, UIResourceEvent, UIResourceQuery, TenantConfig } from '../types/ui-resources';
import { uiResourceApi } from '../lib/ui-resource-api';

interface UIResourceContextType {
  resources: Map<string, UIResource>;
  isConnected: boolean;
  connectionError: string | null;
  isLoading: boolean;
  
  // Resource management
  getResources: (query?: UIResourceQuery) => UIResource[];
  getResourceById: (id: string) => UIResource | undefined;
  getResourcesByType: (type: UIResource['type']) => UIResource[];
  getResourcesByAgent: (agentId: string) => UIResource[];
  getResourcesByTags: (tags: string[]) => UIResource[];
  
  // WebSocket connection
  connect: (tenantId: string, sessionId: string) => void;
  disconnect: () => void;
  
  // Tenant configuration
  tenantConfig: TenantConfig | null;
  setTenantConfig: (config: TenantConfig) => void;
  
  // Error handling
  clearError: () => void;
}

const UIResourceContext = createContext<UIResourceContextType | undefined>(undefined);

export const useUIResources = () => {
  const context = useContext(UIResourceContext);
  if (!context) {
    throw new Error('useUIResources must be used within a UIResourceProvider');
  }
  return context;
};

interface UIResourceProviderProps {
  children: React.ReactNode;
}

export const UIResourceProvider: React.FC<UIResourceProviderProps> = ({ children }) => {
  const [resources, setResources] = useState<Map<string, UIResource>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [tenantConfig, setTenantConfig] = useState<TenantConfig | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const currentTenantRef = useRef<string | null>(null);
  const currentSessionRef = useRef<string | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000;

  // Resource query functions
  const getResources = useCallback((query?: UIResourceQuery): UIResource[] => {
    let filteredResources = Array.from(resources.values());
    
    if (query) {
      if (query.tenantId) {
        filteredResources = filteredResources.filter(r => r.tenantId === query.tenantId);
      }
      if (query.sessionId) {
        filteredResources = filteredResources.filter(r => r.sessionId === query.sessionId);
      }
      if (query.agentId) {
        filteredResources = filteredResources.filter(r => r.agentId === query.agentId);
      }
      if (query.type) {
        filteredResources = filteredResources.filter(r => r.type === query.type);
      }
      if (query.tags && query.tags.length > 0) {
        filteredResources = filteredResources.filter(r => 
          query.tags!.some(tag => r.tags.includes(tag))
        );
      }
    }
    
    return filteredResources.sort((a, b) => 
      new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    );
  }, [resources]);

  const getResourceById = useCallback((id: string): UIResource | undefined => {
    return resources.get(id);
  }, [resources]);

  const getResourcesByType = useCallback((type: UIResource['type']): UIResource[] => {
    return getResources({ type });
  }, [getResources]);

  const getResourcesByAgent = useCallback((agentId: string): UIResource[] => {
    return getResources({ agentId });
  }, [getResources]);

  const getResourcesByTags = useCallback((tags: string[]): UIResource[] => {
    return getResources({ tags });
  }, [getResources]);

  // WebSocket message handler
  const handleWebSocketMessage = useCallback((event: MessageEvent) => {
    try {
      const resourceEvent: UIResourceEvent = JSON.parse(event.data);
      
      setResources(prev => {
        const newResources = new Map(prev);
        
        switch (resourceEvent.type) {
          case 'create':
          case 'update':
            if (resourceEvent.resource) {
              newResources.set(resourceEvent.resourceId, resourceEvent.resource);
            }
            break;
          case 'delete':
            newResources.delete(resourceEvent.resourceId);
            break;
        }
        
        return newResources;
      });
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, []);

  // Hydration - load existing resources
  const hydrate = useCallback(async (tenantId: string, sessionId: string) => {
    if (!tenantId || !sessionId) return;
    
    setIsLoading(true);
    try {
      const existingResources = await uiResourceApi.getResources({
        tenantId,
        sessionId
      });
      
      const resourceMap = new Map<string, UIResource>();
      existingResources.forEach(resource => {
        resourceMap.set(resource.id, resource);
      });
      
      setResources(resourceMap);
      setConnectionError(null);
    } catch (error) {
      console.error('Failed to hydrate resources:', error);
      setConnectionError('Failed to load existing resources');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // WebSocket connection management
  const connect = useCallback(async (tenantId: string, sessionId: string) => {
    // Disconnect existing connection first
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect');
      wsRef.current = null;
    }
    
    setIsConnected(false);
    setConnectionError(null);
    reconnectAttemptsRef.current = 0;
    
    currentTenantRef.current = tenantId;
    currentSessionRef.current = sessionId;
    
    // First, hydrate existing resources
    await hydrate(tenantId, sessionId);
    
    // Then establish WebSocket connection
    try {
      const baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const wsUrl = baseUrl.replace(/^http/, 'ws');
      const token = localStorage.getItem('auth_token');
      
      const topic = `ui.${tenantId}.${sessionId}.*`;
      const wsEndpoint = `${wsUrl}/mcp-ui/ws?topic=${encodeURIComponent(topic)}${token ? `&token=${token}` : ''}`;
      
      const ws = new WebSocket(wsEndpoint);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log('UI Resource WebSocket connected:', { tenantId, sessionId });
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttemptsRef.current = 0;
      };
      
      ws.onmessage = handleWebSocketMessage;
      
      ws.onclose = (event) => {
        console.log('UI Resource WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        
        // Attempt reconnection if not a clean close
        if (event.code !== 1000 && 
            currentTenantRef.current && 
            currentSessionRef.current && 
            reconnectAttemptsRef.current < maxReconnectAttempts) {
          
          reconnectAttemptsRef.current++;
          const delay = Math.min(
            baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current),
            30000
          );
          
          console.log(`Reconnecting UI Resource WebSocket in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (currentTenantRef.current && currentSessionRef.current) {
              connect(currentTenantRef.current, currentSessionRef.current);
            }
          }, delay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          setConnectionError('Max reconnection attempts reached');
        }
      };
      
      ws.onerror = (error) => {
        console.error('UI Resource WebSocket error:', error);
        setConnectionError('WebSocket connection error');
      };
      
    } catch (error) {
      console.error('Failed to create UI Resource WebSocket connection:', error);
      setConnectionError('Failed to establish WebSocket connection');
    }
  }, [handleWebSocketMessage, hydrate]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect');
      wsRef.current = null;
    }
    
    setIsConnected(false);
    setConnectionError(null);
    currentTenantRef.current = null;
    currentSessionRef.current = null;
    reconnectAttemptsRef.current = 0;
  }, []);

  const clearError = useCallback(() => {
    setConnectionError(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  const value: UIResourceContextType = {
    resources,
    isConnected,
    connectionError,
    isLoading,
    getResources,
    getResourceById,
    getResourcesByType,
    getResourcesByAgent,
    getResourcesByTags,
    connect,
    disconnect,
    tenantConfig,
    setTenantConfig,
    clearError,
  };

  return (
    <UIResourceContext.Provider value={value}>
      {children}
    </UIResourceContext.Provider>
  );
};