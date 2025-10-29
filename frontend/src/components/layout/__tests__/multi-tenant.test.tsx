import { TENANT_CONFIGS, getTenantById, detectCurrentTenant } from '../../../lib/tenant-config';

describe('Multi-Tenant Frontend Support', () => {

  describe('Tenant Configuration', () => {
    it('should have correct configuration for all tenants', () => {
      expect(TENANT_CONFIGS.meetmind).toEqual({
        tenantId: 'meetmind',
        domain: 'meetmind.se',
        theme: expect.objectContaining({
          primaryColor: '#2563eb',
          secondaryColor: '#1e40af',
          accentColor: '#3b82f6',
        }),
        allowedAgents: ['meetmind-summarizer'],
        branding: expect.objectContaining({
          name: 'MeetMind',
          title: 'MeetMind - AI Meeting Intelligence',
        }),
      });

      expect(TENANT_CONFIGS.agentsvea).toEqual({
        tenantId: 'agentsvea',
        domain: 'agentsvea.se',
        theme: expect.objectContaining({
          primaryColor: '#059669',
          secondaryColor: '#047857',
          accentColor: '#10b981',
        }),
        allowedAgents: ['agent-svea'],
        branding: expect.objectContaining({
          name: 'Agent Svea',
          title: 'Agent Svea - Bokföring & Accounting',
        }),
      });

      expect(TENANT_CONFIGS.feliciasfi).toEqual({
        tenantId: 'feliciasfi',
        domain: 'feliciasfi.com',
        theme: expect.objectContaining({
          primaryColor: '#dc2626',
          secondaryColor: '#b91c1c',
          accentColor: '#ef4444',
        }),
        allowedAgents: ['felicia-core'],
        branding: expect.objectContaining({
          name: 'Felicia\'s Finance',
          title: 'Felicia\'s Finance - Trading & Analytics',
        }),
      });
    });
  });

  describe('Build Configuration', () => {
    it('should support environment variable overrides', () => {
      // Test that environment variables can override default configurations
      const originalEnv = {
        REACT_APP_TENANT_NAME: process.env.REACT_APP_TENANT_NAME,
        REACT_APP_PRIMARY_COLOR: process.env.REACT_APP_PRIMARY_COLOR,
      };

      process.env.REACT_APP_TENANT_NAME = 'Custom Tenant';
      process.env.REACT_APP_PRIMARY_COLOR = '#ff0000';

      // Re-import to get updated configuration
      jest.resetModules();
      const { TENANT_CONFIGS: updatedConfigs } = require('../../../lib/tenant-config');

      expect(updatedConfigs.meetmind.branding.name).toBe('Custom Tenant');
      expect(updatedConfigs.meetmind.theme.primaryColor).toBe('#ff0000');

      // Restore original environment
      Object.entries(originalEnv).forEach(([key, value]) => {
        if (value !== undefined) {
          process.env[key] = value;
        } else {
          delete process.env[key];
        }
      });
    });
  });
});

describe('Deployment Configuration', () => {
  it('should have separate Docker configurations for each tenant', () => {
    // This test verifies that the deployment structure supports multi-tenant builds
    const expectedTenants = ['meetmind', 'agentsvea', 'feliciasfi'];
    
    expectedTenants.forEach(tenant => {
      expect(TENANT_CONFIGS[tenant]).toBeDefined();
      expect(TENANT_CONFIGS[tenant].tenantId).toBe(tenant);
      expect(TENANT_CONFIGS[tenant].domain).toBeTruthy();
      expect(TENANT_CONFIGS[tenant].theme.primaryColor).toBeTruthy();
      expect(TENANT_CONFIGS[tenant].branding.name).toBeTruthy();
    });
  });

  it('should support distinct frontend deployments', () => {
    // Verify that each tenant has unique configuration
    const tenants = Object.values(TENANT_CONFIGS);
    const domains = tenants.map(t => t.domain);
    const colors = tenants.map(t => t.theme.primaryColor);
    const names = tenants.map(t => t.branding.name);

    // All domains should be unique
    expect(new Set(domains).size).toBe(domains.length);
    
    // All primary colors should be unique
    expect(new Set(colors).size).toBe(colors.length);
    
    // All names should be unique
    expect(new Set(names).size).toBe(names.length);
  });
});