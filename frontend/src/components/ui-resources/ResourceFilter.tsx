import React, { useState, useMemo } from 'react';
import { UIResource } from '../../types/ui-resources';
import { ThemedButton as Button } from '../ui/themed-button';
import { Input } from '../ui/input';
import { useTenant } from '../../contexts/TenantContext';
import { cn } from '../../lib/utils';

interface ResourceFilterProps {
  resources: UIResource[];
  onFilterChange: (filteredResources: UIResource[]) => void;
  className?: string;
}

export const ResourceFilter: React.FC<ResourceFilterProps> = ({
  resources,
  onFilterChange,
  className
}) => {
  // const { currentTenant } = useTenant(); // Available for future theming
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedType, setSelectedType] = useState<UIResource['type'] | 'all'>('all');
  const [selectedAgent, setSelectedAgent] = useState<string>('all');
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());

  // Extract unique values for filter options
  const filterOptions = useMemo(() => {
    const types = new Set<UIResource['type']>();
    const agents = new Set<string>();
    const tags = new Set<string>();

    resources.forEach(resource => {
      types.add(resource.type);
      agents.add(resource.agentId);
      resource.tags.forEach(tag => tags.add(tag));
    });

    return {
      types: Array.from(types).sort(),
      agents: Array.from(agents).sort(),
      tags: Array.from(tags).sort(),
    };
  }, [resources]);

  // Filter resources based on current filters
  const filteredResources = useMemo(() => {
    let filtered = resources;

    // Search term filter
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(resource => {
        const payload = resource.payload as any;
        const searchableText = [
          resource.id,
          resource.type,
          resource.agentId,
          payload.title,
          payload.content,
          ...resource.tags
        ].join(' ').toLowerCase();
        
        return searchableText.includes(term);
      });
    }

    // Type filter
    if (selectedType !== 'all') {
      filtered = filtered.filter(resource => resource.type === selectedType);
    }

    // Agent filter
    if (selectedAgent !== 'all') {
      filtered = filtered.filter(resource => resource.agentId === selectedAgent);
    }

    // Tags filter
    if (selectedTags.size > 0) {
      filtered = filtered.filter(resource => 
        resource.tags.some(tag => selectedTags.has(tag))
      );
    }

    return filtered;
  }, [resources, searchTerm, selectedType, selectedAgent, selectedTags]);

  // Update parent component when filters change
  React.useEffect(() => {
    onFilterChange(filteredResources);
  }, [filteredResources, onFilterChange]);

  const handleTagToggle = (tag: string) => {
    const newSelectedTags = new Set(selectedTags);
    if (newSelectedTags.has(tag)) {
      newSelectedTags.delete(tag);
    } else {
      newSelectedTags.add(tag);
    }
    setSelectedTags(newSelectedTags);
  };

  const clearAllFilters = () => {
    setSearchTerm('');
    setSelectedType('all');
    setSelectedAgent('all');
    setSelectedTags(new Set());
  };

  const hasActiveFilters = searchTerm || selectedType !== 'all' || selectedAgent !== 'all' || selectedTags.size > 0;

  return (
    <div className={cn('space-y-4 p-4 glass-card', className)}>
      {/* Search */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-white/90">
          Search Resources
        </label>
        <Input
          type="text"
          placeholder="Search by title, content, or tags..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="bg-white/5 border-white/20 text-white placeholder:text-white/50"
        />
      </div>

      {/* Type Filter */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-white/90">
          Resource Type
        </label>
        <div className="flex flex-wrap gap-2">
          <Button
            variant={selectedType === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSelectedType('all')}
            className="text-xs"
          >
            All Types
          </Button>
          {filterOptions.types.map(type => (
            <Button
              key={type}
              variant={selectedType === type ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedType(type)}
              className="text-xs capitalize"
            >
              {type}
            </Button>
          ))}
        </div>
      </div>

      {/* Agent Filter */}
      {filterOptions.agents.length > 1 && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-white/90">
            Agent
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              variant={selectedAgent === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedAgent('all')}
              className="text-xs"
            >
              All Agents
            </Button>
            {filterOptions.agents.map(agent => (
              <Button
                key={agent}
                variant={selectedAgent === agent ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedAgent(agent)}
                className="text-xs"
              >
                {agent}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Tags Filter */}
      {filterOptions.tags.length > 0 && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-white/90">
            Tags
          </label>
          <div className="flex flex-wrap gap-2">
            {filterOptions.tags.map(tag => (
              <Button
                key={tag}
                variant={selectedTags.has(tag) ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTagToggle(tag)}
                className="text-xs"
              >
                #{tag}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Filter Summary and Clear */}
      <div className="flex items-center justify-between pt-2 border-t border-white/10">
        <div className="text-xs text-white/60">
          {filteredResources.length} of {resources.length} resources
        </div>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearAllFilters}
            className="text-xs text-white/60 hover:text-white"
          >
            Clear Filters
          </Button>
        )}
      </div>
    </div>
  );
};