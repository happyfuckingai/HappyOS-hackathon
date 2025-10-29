import React from 'react';
import { useTenant } from '../../contexts/TenantContext';
import { ThemedButton } from './themed-button';
import { cn } from '../../lib/utils';

interface TenantSwitcherProps {
  className?: string;
  size?: 'sm' | 'default' | 'lg';
}

export const TenantSwitcher: React.FC<TenantSwitcherProps> = ({ 
  className, 
  size = 'sm' 
}) => {
  const { currentTenant, availableTenants, setTenant, isLoading } = useTenant();

  if (isLoading) {
    return (
      <div className={cn('flex gap-2', className)}>
        {[...Array(3)].map((_, index) => (
          <div
            key={index}
            className="h-8 w-20 bg-white/10 rounded animate-pulse"
          />
        ))}
      </div>
    );
  }

  return (
    <div className={cn('flex gap-2', className)}>
      {availableTenants.map((tenant) => (
        <ThemedButton
          key={tenant.tenantId}
          variant={currentTenant?.tenantId === tenant.tenantId ? 'default' : 'outline'}
          size={size}
          onClick={() => setTenant(tenant.tenantId)}
          className="text-xs"
          style={{
            backgroundColor: currentTenant?.tenantId === tenant.tenantId 
              ? tenant.theme.primaryColor 
              : 'transparent',
            borderColor: tenant.theme.primaryColor,
            color: currentTenant?.tenantId === tenant.tenantId 
              ? 'white' 
              : tenant.theme.primaryColor,
          }}
        >
          {tenant.branding.name}
        </ThemedButton>
      ))}
    </div>
  );
};