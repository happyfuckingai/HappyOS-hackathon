import React, { useEffect, useState, useCallback } from 'react';
import { useUIResources } from '../../contexts/UIResourceContext';
import { ResourceFilter } from './ResourceFilter';
import { ResourceSorter } from './ResourceSorter';
import { ResourceGrouper } from './ResourceGrouper';
import { ResponsiveResourceGrid } from './ResponsiveResourceGrid';
import { UIResource, UIResourceQuery } from '../../types/ui-resources';
import { ThemedButton as Button } from '../ui/themed-button';
import { cn } from '../../lib/utils';

interface EnhancedUIResourceContainerProps {
  tenantId: string;
  sessionId: string;
  query?: Omit<UIResourceQuery, 'tenantId' | 'sessionId'>;
  className?: string;
  emptyMessage?: string;
  maxResources?: number;
  autoConnect?: boolean;
  showFilters?: boolean;
  showSorting?: boolean;
  showGrouping?: boolean;
  defaultView?: 'grid' | 'grouped';
}

export const EnhancedUIResourceContainer: React.FC<EnhancedUIResourceContainerProps> = ({
  tenantId,
  sessionId,
  query = {},
  className,
  emptyMessage = 'No resources to display',
  maxResources,
  autoConnect = true,
  showFilters = true,
  showSorting = true,
  showGrouping = true,
  defaultView = 'grid'
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
  const [filteredResources, setFilteredResources] = useState<UIResource[]>([]);
  const [sortedResources, setSortedResources] = useState<UIResource[]>([]);
  const [currentView, setCurrentView] = useState<'grid' | 'grouped'>(defaultView);
  const [showFilterPanel, setShowFilterPanel] = useState(false);

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

  // Get base resources
  const baseResources = getResources({
    tenantId,
    sessionId,
    ...query
  });

  // Initialize filtered resources when base resources change
  useEffect(() => {
    setFilteredResources(baseResources);
  }, [baseResources]);

  // Apply max resources limit to final sorted resources
  const displayResources = maxResources 
    ? sortedResources.slice(0, maxResources)
    : sortedResources;

  const handleResourceError = useCallback((error: Error, resource: UIResource) => {
    setResourceErrors(prev => new Map(prev).set(resource.id, error));
  }, []);

  const handleRetryConnection = () => {
    clearError();
    connect(tenantId, sessionId);
  };

  const handleFilterChange = useCallback((filtered: UIResource[]) => {
    setFilteredResources(filtered);
  }, []);

  const handleSortChange = useCallback((sorted: UIResource[]) => {
    setSortedResources(sorted);
  }, []);

  const toggleFilterPanel = () => {
    setShowFilterPanel(prev => !prev);
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
          <Button
            onClick={handleRetryConnection}
            variant="outline"
            size="sm"
            className="border-red-500/50 text-red-400 hover:bg-red-500/10"
          >
            Retry Connection
          </Button>
        </div>
      </div>
    );
  }

  // Empty state
  if (baseResources.length === 0) {
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

      {/* Controls */}
      <div className="flex items-center justify-between gap-4 p-3 glass-card">
        <div className="flex items-center gap-4">
          <div className="text-sm text-white/70">
            {displayResources.length} of {baseResources.length} resources
          </div>
          
          {(showFilters || showSorting || showGrouping) && (
            <div className="flex items-center gap-2">
              {showFilters && (
                <Button
                  variant={showFilterPanel ? 'default' : 'outline'}
                  size="sm"
                  onClick={toggleFilterPanel}
                  className="text-xs"
                >
                  🔍 Filters
                </Button>
              )}
              
              {showGrouping && (
                <div className="flex gap-1">
                  <Button
                    variant={currentView === 'grid' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setCurrentView('grid')}
                    className="text-xs"
                  >
                    Grid
                  </Button>
                  <Button
                    variant={currentView === 'grouped' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setCurrentView('grouped')}
                    className="text-xs"
                  >
                    Grouped
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Resource errors summary */}
        {resourceErrors.size > 0 && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setResourceErrors(new Map())}
            className="text-xs text-red-400 hover:text-red-300"
          >
            Clear {resourceErrors.size} error{resourceErrors.size > 1 ? 's' : ''}
          </Button>
        )}
      </div>

      {/* Filter Panel */}
      {showFilters && showFilterPanel && (
        <ResourceFilter
          resources={baseResources}
          onFilterChange={handleFilterChange}
        />
      )}

      {/* Sorting */}
      {showSorting && currentView === 'grid' && (
        <ResourceSorter
          resources={filteredResources}
          onSortChange={handleSortChange}
        />
      )}

      {/* Resource Display */}
      {currentView === 'grouped' ? (
        <ResourceGrouper
          resources={filteredResources}
          onResourceError={handleResourceError}
        />
      ) : (
        <ResponsiveResourceGrid
          resources={displayResources}
          onResourceError={handleResourceError}
        />
      )}

      {/* Show truncation notice if maxResources is applied */}
      {maxResources && sortedResources.length > maxResources && (
        <div className="glass-card p-3 text-center">
          <div className="text-white/50 text-sm">
            Showing {maxResources} of {sortedResources.length} resources
          </div>
        </div>
      )}
    </div>
  );
};