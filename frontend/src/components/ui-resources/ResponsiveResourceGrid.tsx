import React from 'react';
import { UIResource } from '../../types/ui-resources';
import { UIResourceRenderer } from './UIResourceRenderer';
import { cn } from '../../lib/utils';

interface ResponsiveResourceGridProps {
  resources: UIResource[];
  className?: string;
  onResourceError?: (error: Error, resource: UIResource) => void;
}

export const ResponsiveResourceGrid: React.FC<ResponsiveResourceGridProps> = ({
  resources,
  className,
  onResourceError
}) => {
  // Group resources by type for better layout
  const groupedResources = React.useMemo(() => {
    const groups: Record<string, UIResource[]> = {
      card: [],
      list: [],
      form: [],
      chart: [],
    };

    resources.forEach(resource => {
      if (groups[resource.type]) {
        groups[resource.type].push(resource);
      }
    });

    return groups;
  }, [resources]);

  // Determine grid layout based on resource types and counts
  const getGridClasses = () => {
    const totalResources = resources.length;
    
    if (totalResources === 0) return '';
    
    // Single resource - full width
    if (totalResources === 1) {
      return 'grid-cols-1';
    }
    
    // Two resources - side by side on larger screens
    if (totalResources === 2) {
      return 'grid-cols-1 lg:grid-cols-2';
    }
    
    // Three or more - responsive grid
    if (totalResources <= 4) {
      return 'grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3';
    }
    
    // Many resources - dense grid
    return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4';
  };

  // Render resources in optimal order for responsive layout
  const renderResourcesInOrder = () => {
    const orderedResources: UIResource[] = [];
    
    // Priority order: cards first (most important), then lists, charts, forms
    const typeOrder: (keyof typeof groupedResources)[] = ['card', 'list', 'chart', 'form'];
    
    typeOrder.forEach(type => {
      orderedResources.push(...groupedResources[type]);
    });
    
    return orderedResources;
  };

  const orderedResources = renderResourcesInOrder();

  if (orderedResources.length === 0) {
    return (
      <div className={cn('text-center py-8', className)}>
        <div className="text-white/50 text-sm">
          No resources to display
        </div>
      </div>
    );
  }

  return (
    <div className={cn(
      'grid gap-4 auto-rows-max',
      getGridClasses(),
      className
    )}>
      {orderedResources.map((resource, index) => (
        <div
          key={`${resource.id}-${resource.revision}`}
          className={cn(
            'transition-all duration-300 ease-in-out',
            // Special handling for forms - they might need more space
            resource.type === 'form' && orderedResources.length > 2 && 'md:col-span-2 lg:col-span-1',
            // Charts can be wider on larger screens
            resource.type === 'chart' && orderedResources.length > 3 && 'lg:col-span-2 xl:col-span-1'
          )}
          style={{
            // Stagger animation delays for smooth appearance
            animationDelay: `${index * 100}ms`
          }}
        >
          <UIResourceRenderer
            resource={resource}
            onError={onResourceError}
            className="h-full" // Ensure cards fill their grid cell
          />
        </div>
      ))}
    </div>
  );
};