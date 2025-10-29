import React from 'react';
import { UIResource, CardPayload } from '../../../types/ui-resources';
import { ThemedCard as Card, ThemedCardHeader as CardHeader, ThemedCardTitle as CardTitle, ThemedCardContent as CardContent, ThemedCardFooter as CardFooter } from '../../ui/themed-card';
import { ThemedButton as Button } from '../../ui/themed-button';
import { useTenant } from '../../../contexts/TenantContext';
import { cn } from '../../../lib/utils';

interface CardRendererProps {
  resource: UIResource;
}

export const CardRenderer: React.FC<CardRendererProps> = ({ resource }) => {
  const payload = resource.payload as CardPayload;
  const { currentTenant } = useTenant();

  const getStatusStyles = (status?: string) => {
    const primaryColor = currentTenant?.theme.primaryColor || '#2563eb';
    
    switch (status) {
      case 'success':
        return 'border-green-500/20 bg-green-500/5';
      case 'warning':
        return 'border-yellow-500/20 bg-yellow-500/5';
      case 'error':
        return 'border-red-500/20 bg-red-500/5';
      case 'info':
      default:
        return `border-[${primaryColor}]/20 bg-[${primaryColor}]/5`;
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'success':
        return '✓';
      case 'warning':
        return '⚠';
      case 'error':
        return '✕';
      case 'info':
      default:
        return 'ℹ';
    }
  };

  const handleActionClick = async (action: any) => {
    if (action.type === 'link' && action.url) {
      window.open(action.url, '_blank', 'noopener,noreferrer');
    } else if (action.type === 'button' && action.url) {
      try {
        const method = action.method || 'GET';
        const response = await fetch(action.url, {
          method,
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          },
        });
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        console.log('Action completed successfully');
      } catch (error) {
        console.error('Action failed:', error);
      }
    }
  };

  return (
    <Card className={cn(
      'transition-all duration-200 hover:shadow-lg',
      getStatusStyles(payload.status)
    )}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          {payload.status && (
            <span className="text-sm opacity-70">
              {getStatusIcon(payload.status)}
            </span>
          )}
          {payload.title}
        </CardTitle>
      </CardHeader>
      
      {payload.content && (
        <CardContent className="pt-0">
          <div className="text-white/80 text-sm leading-relaxed whitespace-pre-wrap">
            {payload.content}
          </div>
        </CardContent>
      )}
      
      {payload.actions && payload.actions.length > 0 && (
        <CardFooter className="pt-0 gap-2 flex-wrap">
          {payload.actions.map((action, index) => (
            <Button
              key={index}
              variant={action.variant || 'default'}
              size="sm"
              onClick={() => handleActionClick(action)}
              className="text-xs"
            >
              {action.label}
            </Button>
          ))}
        </CardFooter>
      )}
    </Card>
  );
};