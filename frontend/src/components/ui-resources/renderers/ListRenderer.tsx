import React from 'react';
import { UIResource, ListPayload } from '../../../types/ui-resources';
import { ThemedCard as Card, ThemedCardHeader as CardHeader, ThemedCardTitle as CardTitle, ThemedCardContent as CardContent } from '../../ui/themed-card';
import { useTenant } from '../../../contexts/TenantContext';
import { cn } from '../../../lib/utils';

interface ListRendererProps {
  resource: UIResource;
}

export const ListRenderer: React.FC<ListRendererProps> = ({ resource }) => {
  const payload = resource.payload as ListPayload;
  const { currentTenant } = useTenant();

  const renderItem = (item: string, index: number) => {
    const itemType = payload.itemType || 'text';
    
    switch (itemType) {
      case 'link':
        // Check if item looks like a URL or has URL format
        const urlMatch = item.match(/^(https?:\/\/[^\s]+)(?:\s+(.+))?$/);
        if (urlMatch) {
          const [, url, label] = urlMatch;
          const linkColor = currentTenant?.theme.primaryColor || '#3b82f6';
        return (
            <a
              key={index}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2 transition-colors hover:opacity-80"
              style={{ color: linkColor }}
            >
              {label || url}
            </a>
          );
        }
        // Fallback to text if not a valid URL
        return <span key={index} className="text-white/80">{item}</span>;
        
      case 'badge':
        // Parse badge format: "label:variant" or just "label"
        const badgeMatch = item.match(/^([^:]+)(?::(.+))?$/);
        const label = badgeMatch?.[1] || item;
        const variant = badgeMatch?.[2] || 'default';
        
        const getBadgeStyles = (variant: string) => {
          switch (variant.toLowerCase()) {
            case 'success':
              return 'bg-green-500/20 text-green-300 border-green-500/30';
            case 'warning':
              return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30';
            case 'error':
            case 'danger':
              return 'bg-red-500/20 text-red-300 border-red-500/30';
            case 'info':
              return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
            default:
              return 'bg-white/10 text-white/80 border-white/20';
          }
        };
        
        return (
          <span
            key={index}
            className={cn(
              'inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border',
              getBadgeStyles(variant)
            )}
          >
            {label}
          </span>
        );
        
      case 'text':
      default:
        return (
          <span key={index} className="text-white/80">
            {item}
          </span>
        );
    }
  };

  return (
    <Card className="transition-all duration-200 hover:shadow-lg">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">{payload.title}</CardTitle>
      </CardHeader>
      
      <CardContent className="pt-0">
        {payload.items.length === 0 ? (
          <div className="text-white/50 text-sm italic">
            No items to display
          </div>
        ) : (
          <div className="space-y-2">
            {payload.items.map((item, index) => (
              <div
                key={index}
                className={cn(
                  'flex items-center gap-2 text-sm',
                  payload.itemType === 'badge' ? 'flex-wrap' : ''
                )}
              >
                {payload.itemType !== 'badge' && (
                  <span className="text-white/40 text-xs">•</span>
                )}
                {renderItem(item, index)}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};