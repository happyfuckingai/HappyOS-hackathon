import React, { useEffect, useState } from 'react';
import { useUIResources } from '../../contexts/UIResourceContext';
import { ResponsiveResourceGrid } from './ResponsiveResourceGrid';
import { UIResource, UIResourceQuery } from '../../types/ui-resources';
import { cn } from '../../lib/utils';

interface UIResourceContainerProps {
  tenantId: string;
  sessionId: string;
  query?: Omit<UIResourceQuery, 'tenantId' | 'sessionId'>;
  className?: string;
  emptyMessage?: string;
  maxResources?: number;
  autoConnect?: boolean;
}

export const UIResourceContainer: React.FC<UIResourceContainerProps> = ({
  tenantId,
  sessionId,
  query = {},
  className,
  emptyMessage = 'No resources to display',
  maxResources,
  autoConnect = true
}) => {
  const {
    getResources,
    isConnected,
    connectionError,
    isLoading,
    connect,
    disconnect,
    clearError
  } = useUIResources();

  const [resourceErrors, setResourceErrors] = useState<Map<string, Error>>(new Map());

  // Auto-connect when component mounts
  useEffect(() => {
    if (autoConnect && tenantId && sessionId) {
      connect(tenantId, sessionId);
    }

    return () => {
      if (autoConnect) {
        disconnect();
      }
    };
  }, [tenantId, sessionId, autoConnect, connect, disconnect]);

  // Get filtered resources
  const resources = getResources({
    tenantId,
    sessionId,
    ...query
  });

  // Apply max resources limit
  const displayResources = maxResources 
    ? resources.slice(0, maxResources)
    : resources;

  const handleResourceError = (error: Error, resource: UIResource) => {
    setResourceErrors(prev => new Map(prev).set(resource.id, error));
  };

  const handleRetryConnection = () => {
    clearError();
    connect(tenantId, sessionId);
  };

  // Loading state
  if (isLoading) {
    return (
      <div className={cn('space-y-4', className)}>
        {[...Array(3)].map((_, index) => (
          <div
            key={index}
            className="glass-card p-6 animate-pulse"
          >
            <div className="h-4 bg-white/10 rounded w-3/4 mb-3" />
            <div className="h-3 bg-white/5 rounded w-full mb-2" />
            <div className="h-3 bg-white/5 rounded w-2/3" />
          </div>
        ))}
      </div>
    );
  }

  // Connection error state
  if (connectionError) {
    return (
      <div className={cn('space-y-4', className)}>
        <div className="glass-card p-6 border-red-500/20 bg-red-500/5">
          <div className="text-red-400 font-medium mb-2">
            Connection Error
          </div>
          <div className="text-red-300/70 text-sm mb-4">
            {connectionError}
          </div>
          <button
            onClick={handleRetryConnection}
            className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-300 rounded-md text-sm transition-colors"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (displayResources.length === 0) {
    return (
      <div className={cn('space-y-4', className)}>
        <div className="glass-card p-8 text-center">
          <div className="text-white/50 text-sm">
            {emptyMessage}
          </div>
          {!isConnected && (
            <div className="text-white/30 text-xs mt-2">
              Connecting to resource stream...
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Connection status indicator */}
      {!isConnected && (
        <div className="glass-card p-3 border-yellow-500/20 bg-yellow-500/5">
          <div className="text-yellow-400 text-sm flex items-center gap-2">
            <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
            Reconnecting to resource stream...
          </div>
        </div>
      )}

      {/* Resource errors summary */}
      {resourceErrors.size > 0 && (
        <div className="glass-card p-3 border-red-500/20 bg-red-500/5">
          <div className="text-red-400 text-sm">
            {resourceErrors.size} resource{resourceErrors.size > 1 ? 's' : ''} failed to render
          </div>
          <button
            onClick={() => setResourceErrors(new Map())}
            className="text-red-300/70 hover:text-red-300 text-xs mt-1 underline"
          >
            Clear errors
          </button>
        </div>
      )}

      {/* Render resources */}
      <ResponsiveResourceGrid
        resources={displayResources}
        onResourceError={handleResourceError}
      />

      {/* Show truncation notice if maxResources is applied */}
      {maxResources && resources.length > maxResources && (
        <div className="glass-card p-3 text-center">
          <div className="text-white/50 text-sm">
            Showing {maxResources} of {resources.length} resources
          </div>
        </div>
      )}
    </div>
  );
};