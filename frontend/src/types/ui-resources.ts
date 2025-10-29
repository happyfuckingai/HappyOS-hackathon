// UI Resource Types for MCP UI Hub
// Based on JSON schema version "2025-10-21"

export interface UIResource {
  id: string;
  tenantId: string;
  sessionId: string;
  agentId: string;
  type: 'card' | 'list' | 'form' | 'chart';
  version: string;
  revision: number;
  payload: CardPayload | ListPayload | FormPayload | ChartPayload;
  tags: string[];
  ttlSeconds?: number;
  idempotencyKey?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CardPayload {
  title: string;
  content?: string;
  status?: 'info' | 'success' | 'warning' | 'error';
  actions?: Action[];
}

export interface ListPayload {
  title: string;
  items: string[];
  itemType?: 'text' | 'link' | 'badge';
}

export interface FormPayload {
  title: string;
  fields: FormField[];
  submitUrl?: string;
  submitMethod?: 'POST' | 'PUT' | 'PATCH';
}

export interface ChartPayload {
  title: string;
  chartType: 'line' | 'bar' | 'pie' | 'doughnut';
  data: any;
  options?: any;
}

export interface Action {
  label: string;
  type: 'button' | 'link';
  url?: string;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost';
}

export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'email' | 'password' | 'number' | 'textarea' | 'select' | 'checkbox';
  required?: boolean;
  placeholder?: string;
  options?: string[];
  value?: any;
}

// WebSocket event types for UI resources
export interface UIResourceEvent {
  type: 'create' | 'update' | 'delete';
  resourceId: string;
  resource?: UIResource;
  tenantId: string;
  sessionId: string;
  timestamp: string;
}

// API types for UI resource operations
export interface CreateUIResourceRequest {
  tenantId: string;
  sessionId: string;
  agentId: string;
  id: string;
  type: 'card' | 'list' | 'form' | 'chart';
  version: string;
  payload: CardPayload | ListPayload | FormPayload | ChartPayload;
  tags?: string[];
  ttlSeconds?: number;
  idempotencyKey?: string;
}

export interface PatchOperation {
  op: 'replace' | 'add' | 'remove';
  path: string;
  value?: any;
}

export interface PatchUIResourceRequest {
  ops: PatchOperation[];
}

export interface UIResourceQuery {
  tenantId?: string;
  sessionId?: string;
  agentId?: string;
  tags?: string[];
  type?: 'card' | 'list' | 'form' | 'chart';
}

// Tenant configuration types
export interface TenantConfig {
  tenantId: string;
  domain: string;
  theme: TenantTheme;
  allowedAgents: string[];
  branding: TenantBranding;
}

export interface TenantTheme {
  primaryColor: string;
  secondaryColor: string;
  accentColor: string;
  backgroundColor: string;
  textColor: string;
  borderColor: string;
}

export interface TenantBranding {
  logo: string;
  name: string;
  favicon: string;
  title: string;
}

// Error types
export interface UIResourceError {
  code: string;
  message: string;
  details?: any;
  tenantId?: string;
  resourceId?: string;
  correlationId?: string;
}