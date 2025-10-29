import React from 'react';
import { UIResource } from '../../types/ui-resources';
import { CardRenderer } from './renderers/CardRenderer';
import { ListRenderer } from './renderers/ListRenderer';
import { FormRenderer } from './renderers/FormRenderer';
import { ChartRenderer } from './renderers/ChartRenderer';
import { ErrorBoundary } from '../common/ErrorBoundary';
import { cn } from '../../lib/utils';

interface UIResourceRendererProps {
  resource: UIResource;
  className?: string;
  onError?: (error: Error, resource: UIResource) => void;
}

export const UIResourceRenderer: React.FC<UIResourceRendererProps> = ({
  resource,
  className,
  onError
}) => {
  const handleError = (error: Error) => {
    console.error('Error rendering UI resource:', error, resource);
    onError?.(error, resource);
  };

  const renderResource = () => {
    switch (resource.type) {
      case 'card':
        return <CardRenderer resource={resource} />;
      case 'list':
        return <ListRenderer resource={resource} />;
      case 'form':
        return <FormRenderer resource={resource} />;
      case 'chart':
        return <ChartRenderer resource={resource} />;
      default:
        throw new Error(`Unknown resource type: ${(resource as any).type}`);
    }
  };

  return (
    <ErrorBoundary
      fallback={
        <div className="glass-card p-4 border-red-500/20 bg-red-500/5">
          <div className="text-red-400 text-sm font-medium mb-2">
            Failed to render resource
          </div>
          <div className="text-red-300/70 text-xs">
            Resource ID: {resource.id}
          </div>
          <div className="text-red-300/70 text-xs">
            Type: {resource.type}
          </div>
        </div>
      }
      onError={handleError}
    >
      <div 
        className={cn(
          "ui-resource",
          `ui-resource--${resource.type}`,
          `ui-resource--agent-${resource.agentId}`,
          resource.tags.map(tag => `ui-resource--tag-${tag}`).join(' '),
          className
        )}
        data-resource-id={resource.id}
        data-resource-type={resource.type}
        data-agent-id={resource.agentId}
        data-tenant-id={resource.tenantId}
        data-session-id={resource.sessionId}
        data-revision={resource.revision}
      >
        {renderResource()}
      </div>
    </ErrorBoundary>
  );
};