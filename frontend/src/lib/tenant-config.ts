import { TenantConfig } from '../types/ui-resources';

// Environment variable helper
const getEnvVar = (key: string, defaultValue: string = ''): string => {
  return process.env[key] || defaultValue;
};

// Build tenant configuration from environment variables or defaults
const buildTenantConfig = (
  tenantId: string,
  defaultConfig: Omit<TenantConfig, 'tenantId'>
): TenantConfig => {
  const envPrefix = `REACT_APP_${tenantId.toUpperCase()}_`;
  
  return {
    tenantId,
    domain: getEnvVar(`${envPrefix}DOMAIN`) || getEnvVar('REACT_APP_DOMAIN') || defaultConfig.domain,
    theme: {
      primaryColor: getEnvVar(`${envPrefix}PRIMARY_COLOR`) || getEnvVar('REACT_APP_PRIMARY_COLOR') || defaultConfig.theme.primaryColor,
      secondaryColor: getEnvVar(`${envPrefix}SECONDARY_COLOR`) || getEnvVar('REACT_APP_SECONDARY_COLOR') || defaultConfig.theme.secondaryColor,
      accentColor: getEnvVar(`${envPrefix}ACCENT_COLOR`) || getEnvVar('REACT_APP_ACCENT_COLOR') || defaultConfig.theme.accentColor,
      backgroundColor: getEnvVar(`${envPrefix}BACKGROUND_COLOR`) || defaultConfig.theme.backgroundColor,
      textColor: getEnvVar(`${envPrefix}TEXT_COLOR`) || defaultConfig.theme.textColor,
      borderColor: getEnvVar(`${envPrefix}BORDER_COLOR`) || defaultConfig.theme.borderColor,
    },
    allowedAgents: defaultConfig.allowedAgents,
    branding: {
      logo: getEnvVar(`${envPrefix}LOGO`) || defaultConfig.branding.logo,
      name: getEnvVar(`${envPrefix}NAME`) || getEnvVar('REACT_APP_TENANT_NAME') || defaultConfig.branding.name,
      favicon: getEnvVar(`${envPrefix}FAVICON`) || defaultConfig.branding.favicon,
      title: getEnvVar(`${envPrefix}TITLE`) || getEnvVar('REACT_APP_TENANT_TITLE') || defaultConfig.branding.title,
    },
  };
};

// Default configurations (fallback when environment variables are not set)
const DEFAULT_CONFIGS = {
  meetmind: {
    domain: 'meetmind.se',
    theme: {
      primaryColor: '#2563eb',      // Blue
      secondaryColor: '#1e40af',
      accentColor: '#3b82f6',
      backgroundColor: '#0f172a',
      textColor: '#ffffff',
      borderColor: '#334155',
    },
    allowedAgents: ['meetmind-summarizer'],
    branding: {
      logo: '/logos/meetmind-logo.svg',
      name: 'MeetMind',
      favicon: '/favicons/meetmind-favicon.ico',
      title: 'MeetMind - AI Meeting Intelligence',
    },
  },
  agentsvea: {
    domain: 'agentsvea.se',
    theme: {
      primaryColor: '#059669',      // Green
      secondaryColor: '#047857',
      accentColor: '#10b981',
      backgroundColor: '#0f172a',
      textColor: '#ffffff',
      borderColor: '#334155',
    },
    allowedAgents: ['agent-svea'],
    branding: {
      logo: '/logos/agentsvea-logo.svg',
      name: 'Agent Svea',
      favicon: '/favicons/agentsvea-favicon.ico',
      title: 'Agent Svea - Bokföring & Accounting',
    },
  },
  feliciasfi: {
    domain: 'feliciasfi.com',
    theme: {
      primaryColor: '#dc2626',      // Red
      secondaryColor: '#b91c1c',
      accentColor: '#ef4444',
      backgroundColor: '#0f172a',
      textColor: '#ffffff',
      borderColor: '#334155',
    },
    allowedAgents: ['felicia-core'],
    branding: {
      logo: '/logos/felicia-logo.svg',
      name: 'Felicia\'s Finance',
      favicon: '/favicons/felicia-favicon.ico',
      title: 'Felicia\'s Finance - Trading & Analytics',
    },
  },
};

// Build tenant configurations with environment variable support
export const TENANT_CONFIGS: Record<string, TenantConfig> = {
  meetmind: buildTenantConfig('meetmind', DEFAULT_CONFIGS.meetmind),
  agentsvea: buildTenantConfig('agentsvea', DEFAULT_CONFIGS.agentsvea),
  feliciasfi: buildTenantConfig('feliciasfi', DEFAULT_CONFIGS.feliciasfi),
};

// Get tenant config by domain
export const getTenantByDomain = (domain: string): TenantConfig | null => {
  const tenant = Object.values(TENANT_CONFIGS).find(config => 
    config.domain === domain || 
    domain.includes(config.domain.replace('www.', ''))
  );
  return tenant || null;
};

// Get tenant config by ID
export const getTenantById = (tenantId: string): TenantConfig | null => {
  return TENANT_CONFIGS[tenantId] || null;
};

// Detect tenant from current URL
export const detectCurrentTenant = (): TenantConfig | null => {
  if (typeof window === 'undefined') return null;
  
  const hostname = window.location.hostname;
  
  // Check for exact domain matches
  const tenant = getTenantByDomain(hostname);
  if (tenant) return tenant;
  
  // Fallback for development/localhost
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    // Check for tenant parameter in URL
    const urlParams = new URLSearchParams(window.location.search);
    const tenantParam = urlParams.get('tenant');
    if (tenantParam && TENANT_CONFIGS[tenantParam]) {
      return TENANT_CONFIGS[tenantParam];
    }
    
    // Default to meetmind for development
    return TENANT_CONFIGS.meetmind;
  }
  
  return null;
};

// Generate CSS custom properties for tenant theme
export const generateThemeCSS = (theme: TenantConfig['theme']): string => {
  return `
    :root {
      --tenant-primary: ${theme.primaryColor};
      --tenant-secondary: ${theme.secondaryColor};
      --tenant-accent: ${theme.accentColor};
      --tenant-background: ${theme.backgroundColor};
      --tenant-text: ${theme.textColor};
      --tenant-border: ${theme.borderColor};
    }
  `;
};

// Apply theme to document
export const applyTenantTheme = (config: TenantConfig): void => {
  if (typeof document === 'undefined') return;
  
  // Update document title
  document.title = config.branding.title;
  
  // Update favicon
  const favicon = document.querySelector('link[rel="icon"]') as HTMLLinkElement;
  if (favicon) {
    favicon.href = config.branding.favicon;
  }
  
  // Apply CSS custom properties
  const themeCSS = generateThemeCSS(config.theme);
  
  // Remove existing tenant theme
  const existingStyle = document.getElementById('tenant-theme');
  if (existingStyle) {
    existingStyle.remove();
  }
  
  // Add new tenant theme
  const style = document.createElement('style');
  style.id = 'tenant-theme';
  style.textContent = themeCSS;
  document.head.appendChild(style);
  
  // Add tenant class to body for additional styling
  document.body.className = document.body.className
    .replace(/tenant-\w+/g, '') // Remove existing tenant classes
    .trim();
  document.body.classList.add(`tenant-${config.tenantId}`);
};

// Get theme-aware CSS classes
export const getThemeClasses = (config: TenantConfig | null) => {
  if (!config) return {};
  
  return {
    primary: `bg-[${config.theme.primaryColor}] text-white`,
    primaryHover: `hover:bg-[${config.theme.secondaryColor}]`,
    accent: `bg-[${config.theme.accentColor}] text-white`,
    border: `border-[${config.theme.borderColor}]`,
    text: `text-[${config.theme.textColor}]`,
    background: `bg-[${config.theme.backgroundColor}]`,
  };
};