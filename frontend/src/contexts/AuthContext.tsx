import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback, useMemo } from 'react';
import { AuthContextType, User } from '../types';
import { authApi } from '../lib/api';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

// Token storage keys
const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Clear all auth data
  const clearAuthData = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    setUser(null);
  }, []);

  // Initialize auth state on mount
  useEffect(() => {
    const initializeAuth = async () => {
      const token = localStorage.getItem(TOKEN_KEY);
      if (token) {
        try {
          const userData = await authApi.validateToken(token);
          setUser(userData);
        } catch (error) {
          console.error('Token validation failed:', error);
          clearAuthData();
        }
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, [clearAuthData]);

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    setIsLoading(true);
    try {
      const response = await authApi.login(email, password);
      
      // Store tokens
      localStorage.setItem(TOKEN_KEY, response.token);
      // Note: refreshToken will be implemented when backend supports it
      
      setUser(response.user);
    } catch (error: any) {
      // Provide more specific error messages
      const message = error.response?.data?.error?.message || error.message || 'Login failed';
      throw new Error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (email: string, password: string, name: string): Promise<void> => {
    setIsLoading(true);
    try {
      const response = await authApi.register(email, password, name);
      
      // Store tokens
      localStorage.setItem(TOKEN_KEY, response.token);
      // Note: refreshToken will be implemented when backend supports it
      
      setUser(response.user);
    } catch (error: any) {
      // Provide more specific error messages
      const message = error.response?.data?.error?.message || error.message || 'Registration failed';
      throw new Error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      // Attempt to logout on server
      await authApi.logout();
    } catch (error) {
      // Continue with logout even if API call fails
      console.error('Logout API call failed:', error);
    } finally {
      clearAuthData();
      setIsLoading(false);
    }
  }, [clearAuthData]);

  const value: AuthContextType = useMemo(() => ({
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
  }), [user, isLoading, login, register, logout]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};