import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { TenantConfig } from '../types/ui-resources';
import { 
  detectCurrentTenant, 
  getTenantById, 
  applyTenantTheme,
  TENANT_CONFIGS 
} from '../lib/tenant-config';

interface TenantContextType {
  currentTenant: TenantConfig | null;
  setTenant: (tenantId: string) => void;
  isLoading: boolean;
  availableTenants: TenantConfig[];
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export const useTenant = () => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return context;
};

interface TenantProviderProps {
  children: ReactNode;
  defaultTenant?: string;
}

export const TenantProvider: React.FC<TenantProviderProps> = ({ 
  children, 
  defaultTenant 
}) => {
  const [currentTenant, setCurrentTenant] = useState<TenantConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const availableTenants = Object.values(TENANT_CONFIGS);

  const setTenant = (tenantId: string) => {
    const tenant = getTenantById(tenantId);
    if (tenant) {
      setCurrentTenant(tenant);
      applyTenantTheme(tenant);
      
      // Store tenant preference in localStorage
      localStorage.setItem('preferred_tenant', tenantId);
      
      // Update URL parameter for development
      if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        const url = new URL(window.location.href);
        url.searchParams.set('tenant', tenantId);
        window.history.replaceState({}, '', url.toString());
      }
    }
  };

  // Initialize tenant on mount
  useEffect(() => {
    const initializeTenant = () => {
      let tenant: TenantConfig | null = null;

      // 1. Check for environment variable (for distinct deployments)
      const envTenantId = process.env.REACT_APP_TENANT_ID;
      if (envTenantId && TENANT_CONFIGS[envTenantId]) {
        tenant = TENANT_CONFIGS[envTenantId];
      }

      // 2. Try to detect from URL/domain
      if (!tenant) {
        tenant = detectCurrentTenant();
      }

      // 3. If not found, try default tenant prop
      if (!tenant && defaultTenant) {
        tenant = getTenantById(defaultTenant);
      }

      // 4. If still not found, try localStorage preference
      if (!tenant) {
        const storedTenant = localStorage.getItem('preferred_tenant');
        if (storedTenant) {
          tenant = getTenantById(storedTenant);
        }
      }

      // 5. Final fallback to meetmind
      if (!tenant) {
        tenant = TENANT_CONFIGS.meetmind;
      }

      if (tenant) {
        setCurrentTenant(tenant);
        applyTenantTheme(tenant);
      }

      setIsLoading(false);
    };

    initializeTenant();
  }, [defaultTenant]);

  // Listen for URL changes (for SPA navigation)
  useEffect(() => {
    const handleLocationChange = () => {
      const tenant = detectCurrentTenant();
      if (tenant && tenant.tenantId !== currentTenant?.tenantId) {
        setCurrentTenant(tenant);
        applyTenantTheme(tenant);
      }
    };

    // Listen for popstate events (back/forward navigation)
    window.addEventListener('popstate', handleLocationChange);
    
    return () => {
      window.removeEventListener('popstate', handleLocationChange);
    };
  }, [currentTenant]);

  const value: TenantContextType = {
    currentTenant,
    setTenant,
    isLoading,
    availableTenants,
  };

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  );
};