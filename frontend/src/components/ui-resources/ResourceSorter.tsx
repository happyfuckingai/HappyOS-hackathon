import React, { useState } from 'react';
import { UIResource } from '../../types/ui-resources';
import { ThemedButton as Button } from '../ui/themed-button';
import { cn } from '../../lib/utils';

type SortField = 'updatedAt' | 'createdAt' | 'type' | 'agentId' | 'title';
type SortDirection = 'asc' | 'desc';

interface ResourceSorterProps {
  resources: UIResource[];
  onSortChange: (sortedResources: UIResource[]) => void;
  className?: string;
}

export const ResourceSorter: React.FC<ResourceSorterProps> = ({
  resources,
  onSortChange,
  className
}) => {
  const [sortField, setSortField] = useState<SortField>('updatedAt');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const sortOptions: { field: SortField; label: string }[] = [
    { field: 'updatedAt', label: 'Last Updated' },
    { field: 'createdAt', label: 'Created' },
    { field: 'type', label: 'Type' },
    { field: 'agentId', label: 'Agent' },
    { field: 'title', label: 'Title' },
  ];

  const sortResources = React.useCallback((field: SortField, direction: SortDirection) => {
    const sorted = [...resources].sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (field) {
        case 'updatedAt':
        case 'createdAt':
          aValue = new Date(a[field]).getTime();
          bValue = new Date(b[field]).getTime();
          break;
        case 'type':
        case 'agentId':
          aValue = a[field];
          bValue = b[field];
          break;
        case 'title':
          aValue = (a.payload as any).title || '';
          bValue = (b.payload as any).title || '';
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return direction === 'asc' ? -1 : 1;
      if (aValue > bValue) return direction === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [resources]);

  React.useEffect(() => {
    const sorted = sortResources(sortField, sortDirection);
    onSortChange(sorted);
  }, [resources, sortField, sortDirection, sortResources, onSortChange]);

  const handleSortFieldChange = (field: SortField) => {
    if (field === sortField) {
      // Toggle direction if same field
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new field with default direction
      setSortField(field);
      setSortDirection(field === 'updatedAt' || field === 'createdAt' ? 'desc' : 'asc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (field !== sortField) return '';
    return sortDirection === 'asc' ? '↑' : '↓';
  };

  return (
    <div className={cn('flex items-center gap-2 p-3 glass-card', className)}>
      <span className="text-sm font-medium text-white/90 mr-2">
        Sort by:
      </span>
      <div className="flex flex-wrap gap-2">
        {sortOptions.map(option => (
          <Button
            key={option.field}
            variant={sortField === option.field ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleSortFieldChange(option.field)}
            className="text-xs"
          >
            {option.label} {getSortIcon(option.field)}
          </Button>
        ))}
      </div>
    </div>
  );
};