import React from 'react';
import { AppShellProps } from '../../types';
import { useTenant } from '../../contexts/TenantContext';
import Header from './Header';

const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const { currentTenant, isLoading } = useTenant();

  // Show loading state while tenant is being determined
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="glass-card p-8 text-center max-w-md mx-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <h3 className="text-lg font-semibold text-white mb-2">Loading Application</h3>
          <p className="text-white/60 text-sm">Initializing tenant configuration...</p>
        </div>
      </div>
    );
  }

  return (
    <div 
      className="min-h-screen flex flex-col bg-aurora-wash"
      style={{
        backgroundColor: currentTenant?.theme.backgroundColor || '#0f172a',
      }}
    >
      <Header />
      <main className="flex-1 relative">
        <div 
          className="absolute inset-0 bg-radial-spark pointer-events-none opacity-20"
          style={{
            background: `radial-gradient(circle at 50% 50%, ${currentTenant?.theme.primaryColor || '#2563eb'}20 0%, transparent 70%)`,
          }}
        />
        <div className="relative z-10 h-full">
          {children}
        </div>
      </main>
    </div>
  );
};

export default AppShell;