import axios, { AxiosResponse } from 'axios';
import { User, Meeting, Participant, ApiResponse } from '../types';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 10000,
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle response errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/auth';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  async login(email: string, password: string): Promise<{ user: User; token: string; refreshToken?: string }> {
    const response: AxiosResponse<ApiResponse<{ user: User; token: string; refreshToken?: string }>> = await api.post('/auth/login', {
      email,
      password,
    });
    
    if (!response.data.success) {
      throw new Error(response.data.error?.message || 'Login failed');
    }
    
    return response.data.data!;
  },

  async register(email: string, password: string, name: string): Promise<{ user: User; token: string; refreshToken?: string }> {
    const response: AxiosResponse<ApiResponse<{ user: User; token: string; refreshToken?: string }>> = await api.post('/auth/register', {
      email,
      password,
      name,
    });
    
    if (!response.data.success) {
      throw new Error(response.data.error?.message || 'Registration failed');
    }
    
    return response.data.data!;
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout');
  },

  async validateToken(token: string): Promise<User> {
    const response: AxiosResponse<ApiResponse<User>> = await api.get('/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    
    if (!response.data.success) {
      throw new Error(response.data.error?.message || 'Token validation failed');
    }
    
    return response.data.data!;
  },
};

// Meeting API
export const meetingApi = {
  async createMeeting(title?: string): Promise<{ roomId: string; meeting: Meeting }> {
    const response: AxiosResponse<ApiResponse<{ roomId: string; meeting: Meeting }>> = await api.post('/meetings', {
      title,
    });
    
    if (!response.data.success) {
      throw new Error(response.data.error?.message || 'Failed to create meeting');
    }
    
    return response.data.data!;
  },

  async joinMeeting(roomId: string): Promise<{ participants: Participant[]; meeting: Meeting }> {
    const response: AxiosResponse<ApiResponse<{ participants: Participant[]; meeting: Meeting }>> = await api.post(`/meetings/${roomId}/join`);
    
    if (!response.data.success) {
      throw new Error(response.data.error?.message || 'Failed to join meeting');
    }
    
    return response.data.data!;
  },

  async leaveMeeting(roomId: string): Promise<void> {
    const response: AxiosResponse<ApiResponse<void>> = await api.post(`/meetings/${roomId}/leave`);
    
    if (!response.data.success) {
      throw new Error(response.data.error?.message || 'Failed to leave meeting');
    }
  },

  async getMeeting(roomId: string): Promise<Meeting> {
    const response: AxiosResponse<ApiResponse<Meeting>> = await api.get(`/meetings/${roomId}`);
    
    if (!response.data.success) {
      throw new Error(response.data.error?.message || 'Failed to get meeting');
    }
    
    return response.data.data!;
  },
};

// LiveKit API
export const livekitApi = {
  async getToken(roomId: string): Promise<{ token: string }> {
    const response: AxiosResponse<ApiResponse<{ token: string }>> = await api.post(`/livekit/token`, {
      roomId,
    });
    
    if (!response.data.success) {
      throw new Error(response.data.error?.message || 'Failed to get LiveKit token');
    }
    
    return response.data.data!;
  },
};

export default api;