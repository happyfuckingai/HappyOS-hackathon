import axios, { AxiosResponse } from 'axios';
import { 
  UIResource, 
  CreateUIResourceRequest, 
  PatchUIResourceRequest, 
  UIResourceQuery,
  UIResourceError 
} from '../types/ui-resources';

// Create axios instance for UI resource API
const uiResourceClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 10000,
});

// Add auth token to requests
uiResourceClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle response errors
uiResourceClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/auth';
    }
    
    // Transform error to UIResourceError format
    const uiError: UIResourceError = {
      code: error.response?.data?.error?.code || 'UNKNOWN_ERROR',
      message: error.response?.data?.error?.message || error.message || 'Unknown error occurred',
      details: error.response?.data?.error?.details,
      tenantId: error.response?.data?.error?.tenantId,
      resourceId: error.response?.data?.error?.resourceId,
      correlationId: error.response?.data?.error?.correlationId,
    };
    
    return Promise.reject(uiError);
  }
);

export const uiResourceApi = {
  /**
   * Create a new UI resource
   */
  async createResource(request: CreateUIResourceRequest): Promise<UIResource> {
    const response: AxiosResponse<UIResource> = await uiResourceClient.post('/mcp-ui/resources', request);
    return response.data;
  },

  /**
   * Update a UI resource using JSON Patch operations
   */
  async patchResource(resourceId: string, request: PatchUIResourceRequest): Promise<UIResource> {
    const encodedId = encodeURIComponent(resourceId);
    const response: AxiosResponse<UIResource> = await uiResourceClient.patch(
      `/mcp-ui/resources/${encodedId}`, 
      request
    );
    return response.data;
  },

  /**
   * Delete a UI resource
   */
  async deleteResource(resourceId: string): Promise<void> {
    const encodedId = encodeURIComponent(resourceId);
    await uiResourceClient.delete(`/mcp-ui/resources/${encodedId}`);
  },

  /**
   * Get UI resources with optional filtering
   */
  async getResources(query?: UIResourceQuery): Promise<UIResource[]> {
    const params = new URLSearchParams();
    
    if (query?.tenantId) params.append('tenantId', query.tenantId);
    if (query?.sessionId) params.append('sessionId', query.sessionId);
    if (query?.agentId) params.append('agentId', query.agentId);
    if (query?.type) params.append('type', query.type);
    if (query?.tags) {
      query.tags.forEach(tag => params.append('tags', tag));
    }
    
    const response: AxiosResponse<UIResource[]> = await uiResourceClient.get(
      `/mcp-ui/resources?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get a specific UI resource by ID
   */
  async getResource(resourceId: string): Promise<UIResource> {
    const encodedId = encodeURIComponent(resourceId);
    const response: AxiosResponse<UIResource> = await uiResourceClient.get(
      `/mcp-ui/resources/${encodedId}`
    );
    return response.data;
  },

  /**
   * Get hydration data for a tenant/session
   */
  async getHydrationData(tenantId: string, sessionId: string): Promise<UIResource[]> {
    const response: AxiosResponse<UIResource[]> = await uiResourceClient.get(
      `/mcp-ui/hydrate?tenantId=${tenantId}&sessionId=${sessionId}`
    );
    return response.data;
  },
};

export default uiResourceApi;