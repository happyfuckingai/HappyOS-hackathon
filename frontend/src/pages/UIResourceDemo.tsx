import React, { useState } from 'react';
import { EnhancedUIResourceContainer } from '../components/ui-resources';
import { useUIResources } from '../contexts/UIResourceContext';
import { useTenant } from '../contexts/TenantContext';
import { ThemedButton as Button } from '../components/ui/themed-button';
import { ThemedCard as Card, ThemedCardHeader as CardHeader, ThemedCardTitle as CardTitle, ThemedCardContent as CardContent } from '../components/ui/themed-card';
import { TenantSwitcher } from '../components/ui/tenant-switcher';
import { UIResource } from '../types/ui-resources';

const UIResourceDemo: React.FC = () => {
  const { connect, disconnect, isConnected, connectionError } = useUIResources();
  const { currentTenant: tenantConfig } = useTenant();
  const [currentSession, setCurrentSession] = useState<string>('demo-session');

  // Sample resources for demo
  const sampleResources: Partial<UIResource>[] = [
    {
      id: 'mm://meetmind/demo-session/meetmind-summarizer/summary-card',
      type: 'card',
      payload: {
        title: 'Meeting Summary',
        content: 'Discussed Q4 planning and budget allocation. Key decisions made on resource allocation.',
        status: 'info',
        actions: [
          { label: 'View Details', type: 'button', variant: 'default' },
          { label: 'Share', type: 'button', variant: 'outline' }
        ]
      },
      tags: ['meeting', 'summary']
    },
    {
      id: 'mm://meetmind/demo-session/meetmind-summarizer/action-items',
      type: 'list',
      payload: {
        title: 'Action Items',
        items: [
          'Review budget proposal by Friday',
          'Schedule follow-up meeting with stakeholders',
          'Prepare Q4 roadmap presentation'
        ],
        itemType: 'text'
      },
      tags: ['actions', 'todo']
    },
    {
      id: 'mm://agentsvea/demo-session/agent-svea/cost-chart',
      type: 'chart',
      payload: {
        title: 'Cost Distribution',
        chartType: 'pie',
        data: {
          labels: ['Office Rent', 'Utilities', 'Software', 'Marketing'],
          datasets: [{
            data: [4500, 800, 1200, 2000]
          }]
        }
      },
      tags: ['costs', 'analysis']
    },
    {
      id: 'mm://feliciasfi/demo-session/felicia-core/market-data',
      type: 'list',
      payload: {
        title: 'Market Overview',
        items: [
          'BTC ↑1.2%:success',
          'OMXS30 −0.4%:error',
          'PnL +3.1%:success',
          'Risk Level:warning'
        ],
        itemType: 'badge'
      },
      tags: ['finance', 'market']
    },
    {
      id: 'mm://feliciasfi/demo-session/felicia-core/trade-form',
      type: 'form',
      payload: {
        title: 'Quick Trade',
        fields: [
          {
            name: 'symbol',
            label: 'Symbol',
            type: 'select',
            required: true,
            options: ['BTC', 'ETH', 'OMXS30', 'SPY']
          },
          {
            name: 'amount',
            label: 'Amount',
            type: 'number',
            required: true,
            placeholder: '0.00'
          },
          {
            name: 'orderType',
            label: 'Order Type',
            type: 'select',
            options: ['Market', 'Limit', 'Stop']
          }
        ]
      },
      tags: ['trading', 'form']
    }
  ];

  const handleConnect = () => {
    if (tenantConfig) {
      connect(tenantConfig.tenantId, currentSession);
    }
  };

  const handleDisconnect = () => {
    disconnect();
  };



  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-purple-900 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="text-2xl text-white">
              UI Resource Renderer Demo
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Tenant Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-white/90">
                Select Tenant:
              </label>
              <TenantSwitcher />
              {tenantConfig && (
                <div className="text-xs text-white/60">
                  Current: {tenantConfig.branding.name} ({tenantConfig.tenantId})
                </div>
              )}
            </div>

            {/* Session Input */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-white/90">
                Session ID:
              </label>
              <input
                type="text"
                value={currentSession}
                onChange={(e) => setCurrentSession(e.target.value)}
                className="w-full px-3 py-2 bg-white/5 border border-white/20 rounded-md text-white placeholder:text-white/50 focus:border-white/40 focus:outline-none"
                placeholder="Enter session ID"
              />
            </div>

            {/* Connection Controls */}
            <div className="flex items-center gap-4">
              <Button
                onClick={handleConnect}
                disabled={!tenantConfig || !currentSession}
                variant="default"
                size="sm"
              >
                Connect
              </Button>
              <Button
                onClick={handleDisconnect}
                disabled={!isConnected}
                variant="outline"
                size="sm"
              >
                Disconnect
              </Button>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`} />
                <span className="text-sm text-white/70">
                  {isConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>

            {connectionError && (
              <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-md p-2">
                {connectionError}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sample Resources Display */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white">Sample Resources</h3>
            <div className="space-y-4">
              {sampleResources.map((resource, index) => (
                <Card key={index} className="glass-card">
                  <CardContent className="p-4">
                    <div className="text-sm text-white/70 mb-2">
                      Type: {resource.type} | Tags: {resource.tags?.join(', ')}
                    </div>
                    <pre className="text-xs text-white/50 bg-white/5 p-2 rounded overflow-x-auto">
                      {JSON.stringify(resource.payload, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-white">Live Resources</h3>
            <EnhancedUIResourceContainer
              tenantId={tenantConfig?.tenantId || 'meetmind'}
              sessionId={currentSession}
              emptyMessage="No resources available. Connect to see live updates."
              autoConnect={false}
              showFilters={true}
              showSorting={true}
              showGrouping={true}
              defaultView="grid"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default UIResourceDemo;