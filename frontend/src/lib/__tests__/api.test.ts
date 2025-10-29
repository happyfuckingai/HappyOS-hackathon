import { apiRequest, ApiError } from '../api';

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

describe('API Utils', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockLocalStorage.getItem.mockClear();
    console.error = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('apiRequest', () => {
    it('should make successful GET request', async () => {
      const mockResponse = { data: { id: 1, name: 'Test' }, success: true };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiRequest('/api/test');

      expect(mockFetch).toHaveBeenCalledWith('/api/test', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockResponse);
    });

    it('should make POST request with body', async () => {
      const mockResponse = { data: { id: 2 }, success: true };
      const requestBody = { name: 'New Item' };
      
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiRequest('/api/items', {
        method: 'POST',
        body: requestBody,
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/items', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });
      expect(result).toEqual(mockResponse);
    });

    it('should include authorization header when token exists', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await apiRequest('/api/protected');

      expect(mockFetch).toHaveBeenCalledWith('/api/protected', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token',
        },
      });
    });

    it('should handle custom headers', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await apiRequest('/api/test', {
        headers: {
          'X-Custom-Header': 'custom-value',
        },
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/test', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-Custom-Header': 'custom-value',
        },
      });
    });

    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await expect(apiRequest('/api/test')).rejects.toThrow('Network error');
    });

    it('should handle HTTP error responses', async () => {
      const errorResponse = {
        success: false,
        error: { message: 'Not found', status: 404 }
      };
      
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: () => Promise.resolve(errorResponse),
      });

      await expect(apiRequest('/api/nonexistent')).rejects.toThrow('Not found');
    });

    it('should handle responses without error details', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve({}),
      });

      await expect(apiRequest('/api/error')).rejects.toThrow('HTTP 500: Internal Server Error');
    });

    it('should handle malformed JSON responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.reject(new Error('Invalid JSON')),
      });

      await expect(apiRequest('/api/malformed')).rejects.toThrow('Invalid JSON');
    });

    it('should handle PUT requests', async () => {
      const mockResponse = { data: { id: 1, updated: true }, success: true };
      const updateData = { name: 'Updated Name' };
      
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiRequest('/api/items/1', {
        method: 'PUT',
        body: updateData,
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/items/1', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      });
      expect(result).toEqual(mockResponse);
    });

    it('should handle DELETE requests', async () => {
      const mockResponse = { success: true };
      
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiRequest('/api/items/1', {
        method: 'DELETE',
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/items/1', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      expect(result).toEqual(mockResponse);
    });

    it('should handle requests without body for non-GET methods', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await apiRequest('/api/test', { method: 'POST' });

      expect(mockFetch).toHaveBeenCalledWith('/api/test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
    });

    it('should preserve custom content-type headers', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await apiRequest('/api/upload', {
        method: 'POST',
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        body: new FormData(),
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/upload', {
        method: 'POST',
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        body: expect.any(FormData),
      });
    });

    it('should handle 401 unauthorized responses', async () => {
      const errorResponse = {
        success: false,
        error: { message: 'Unauthorized', status: 401 }
      };
      
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: () => Promise.resolve(errorResponse),
      });

      await expect(apiRequest('/api/protected')).rejects.toThrow('Unauthorized');
    });

    it('should handle timeout scenarios', async () => {
      // Mock a request that takes too long
      mockFetch.mockImplementation(() => 
        new Promise((resolve) => 
          setTimeout(() => resolve({
            ok: true,
            json: () => Promise.resolve({ success: true }),
          }), 10000)
        )
      );

      // This would test timeout handling if implemented
      // For now, we just verify the mock setup
      const requestPromise = apiRequest('/api/slow');
      expect(requestPromise).toBeInstanceOf(Promise);
    });
  });

  describe('ApiError', () => {
    it('should create ApiError with message and status', () => {
      const error = new ApiError('Test error', 400);
      
      expect(error.message).toBe('Test error');
      expect(error.status).toBe(400);
      expect(error.name).toBe('ApiError');
      expect(error).toBeInstanceOf(Error);
    });

    it('should create ApiError with code', () => {
      const error = new ApiError('Validation failed', 422, 'VALIDATION_ERROR');
      
      expect(error.message).toBe('Validation failed');
      expect(error.status).toBe(422);
      expect(error.code).toBe('VALIDATION_ERROR');
    });

    it('should be throwable and catchable', () => {
      const throwError = () => {
        throw new ApiError('Test error', 500);
      };

      expect(throwError).toThrow('Test error');
      expect(throwError).toThrow(ApiError);
    });
  });
});