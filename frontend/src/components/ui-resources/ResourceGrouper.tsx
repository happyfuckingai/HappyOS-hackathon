import React, { useState, useMemo } from 'react';
import { UIResource } from '../../types/ui-resources';
import { UIResourceRenderer } from './UIResourceRenderer';
import { ThemedButton as Button } from '../ui/themed-button';
import { ThemedCard as Card, ThemedCardContent as CardContent } from '../ui/themed-card';
import { cn } from '../../lib/utils';

type GroupBy = 'none' | 'type' | 'agentId' | 'tags' | 'date';

interface ResourceGrouperProps {
  resources: UIResource[];
  onResourceError?: (error: Error, resource: UIResource) => void;
  className?: string;
}

export const ResourceGrouper: React.FC<ResourceGrouperProps> = ({
  resources,
  onResourceError,
  className
}) => {
  const [groupBy, setGroupBy] = useState<GroupBy>('none');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  const groupOptions: { value: GroupBy; label: string }[] = [
    { value: 'none', label: 'No Grouping' },
    { value: 'type', label: 'By Type' },
    { value: 'agentId', label: 'By Agent' },
    { value: 'tags', label: 'By Tags' },
    { value: 'date', label: 'By Date' },
  ];

  const groupedResources = useMemo(() => {
    if (groupBy === 'none') {
      return { 'All Resources': resources };
    }

    const groups: Record<string, UIResource[]> = {};

    resources.forEach(resource => {
      let groupKeys: string[] = [];

      switch (groupBy) {
        case 'type':
          groupKeys = [resource.type.charAt(0).toUpperCase() + resource.type.slice(1)];
          break;
        case 'agentId':
          groupKeys = [resource.agentId];
          break;
        case 'tags':
          groupKeys = resource.tags.length > 0 ? resource.tags : ['Untagged'];
          break;
        case 'date':
          const date = new Date(resource.updatedAt);
          const today = new Date();
          const yesterday = new Date(today);
          yesterday.setDate(yesterday.getDate() - 1);
          
          if (date.toDateString() === today.toDateString()) {
            groupKeys = ['Today'];
          } else if (date.toDateString() === yesterday.toDateString()) {
            groupKeys = ['Yesterday'];
          } else {
            groupKeys = [date.toLocaleDateString()];
          }
          break;
        default:
          groupKeys = ['Other'];
      }

      groupKeys.forEach(key => {
        if (!groups[key]) {
          groups[key] = [];
        }
        groups[key].push(resource);
      });
    });

    // Sort groups by name, but put 'Today' and 'Yesterday' first for date grouping
    const sortedGroups: Record<string, UIResource[]> = {};
    const sortedKeys = Object.keys(groups).sort((a, b) => {
      if (groupBy === 'date') {
        if (a === 'Today') return -1;
        if (b === 'Today') return 1;
        if (a === 'Yesterday') return -1;
        if (b === 'Yesterday') return 1;
      }
      return a.localeCompare(b);
    });

    sortedKeys.forEach(key => {
      sortedGroups[key] = groups[key];
    });

    return sortedGroups;
  }, [resources, groupBy]);

  const toggleGroupExpansion = (groupName: string) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupName)) {
      newExpanded.delete(groupName);
    } else {
      newExpanded.add(groupName);
    }
    setExpandedGroups(newExpanded);
  };

  const expandAllGroups = () => {
    setExpandedGroups(new Set(Object.keys(groupedResources)));
  };

  const collapseAllGroups = () => {
    setExpandedGroups(new Set());
  };

  // Auto-expand groups when grouping changes
  React.useEffect(() => {
    if (groupBy === 'none') {
      setExpandedGroups(new Set(['All Resources']));
    } else {
      setExpandedGroups(new Set(Object.keys(groupedResources)));
    }
  }, [groupBy, groupedResources]);

  const getGroupIcon = (groupName: string) => {
    switch (groupBy) {
      case 'type':
        const type = groupName.toLowerCase();
        switch (type) {
          case 'card': return '📋';
          case 'list': return '📝';
          case 'form': return '📄';
          case 'chart': return '📊';
          default: return '📦';
        }
      case 'agentId':
        return '🤖';
      case 'tags':
        return '🏷️';
      case 'date':
        return '📅';
      default:
        return '📁';
    }
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Group Controls */}
      <div className="flex items-center justify-between p-3 glass-card">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white/90">
            Group by:
          </span>
          <div className="flex gap-2">
            {groupOptions.map(option => (
              <Button
                key={option.value}
                variant={groupBy === option.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => setGroupBy(option.value)}
                className="text-xs"
              >
                {option.label}
              </Button>
            ))}
          </div>
        </div>

        {groupBy !== 'none' && Object.keys(groupedResources).length > 1 && (
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={expandAllGroups}
              className="text-xs text-white/60 hover:text-white"
            >
              Expand All
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={collapseAllGroups}
              className="text-xs text-white/60 hover:text-white"
            >
              Collapse All
            </Button>
          </div>
        )}
      </div>

      {/* Grouped Resources */}
      <div className="space-y-4">
        {Object.entries(groupedResources).map(([groupName, groupResources]) => {
          const isExpanded = expandedGroups.has(groupName);
          const showGroupHeader = groupBy !== 'none';

          return (
            <div key={groupName} className="space-y-2">
              {showGroupHeader && (
                <div
                  className="flex items-center gap-3 p-3 glass-card cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => toggleGroupExpansion(groupName)}
                >
                  <span className="text-lg">{getGroupIcon(groupName)}</span>
                  <div className="flex-1">
                    <h3 className="font-medium text-white">
                      {groupName}
                    </h3>
                    <p className="text-sm text-white/60">
                      {groupResources.length} resource{groupResources.length !== 1 ? 's' : ''}
                    </p>
                  </div>
                  <span className="text-white/40">
                    {isExpanded ? '▼' : '▶'}
                  </span>
                </div>
              )}

              {isExpanded && (
                <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {groupResources.map(resource => (
                    <UIResourceRenderer
                      key={`${resource.id}-${resource.revision}`}
                      resource={resource}
                      onError={onResourceError}
                      className="transition-all duration-300 ease-in-out"
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {Object.keys(groupedResources).length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <div className="text-white/50 text-sm">
              No resources to display
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};