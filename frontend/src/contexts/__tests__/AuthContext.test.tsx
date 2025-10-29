import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AuthProvider, useAuth } from '../AuthContext';

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

// Mock jwt-decode
jest.mock('jwt-decode', () => ({
  __esModule: true,
  default: jest.fn(() => ({
    id: 'user-123',
    email: 'test@example.com',
    name: 'Test User',
    role: 'user',
    exp: Date.now() / 1000 + 3600, // 1 hour from now
  })),
}));

// Test component that uses AuthContext
const TestComponent: React.FC = () => {
  const { user, isAuthenticated, isLoading, login, register, logout } = useAuth();

  return (
    <div>
      <div data-testid="auth-status">
        {isAuthenticated ? 'Authenticated' : 'Not Authenticated'}
      </div>
      <div data-testid="loading-status">
        {isLoading ? 'Loading' : 'Not Loading'}
      </div>
      <div data-testid="user-info">
        {user ? `${user.name} (${user.email})` : 'No User'}
      </div>
      <button onClick={() => login('test@example.com', 'password')}>Login</button>
      <button onClick={() => register('test@example.com', 'password', 'Test User')}>Register</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

describe('AuthContext', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockLocalStorage.getItem.mockClear();
    mockLocalStorage.setItem.mockClear();
    mockLocalStorage.removeItem.mockClear();
    console.error = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('provides initial unauthenticated state', () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated');
    expect(screen.getByTestId('loading-status')).toHaveTextContent('Not Loading');
    expect(screen.getByTestId('user-info')).toHaveTextContent('No User');
  });

  it('initializes with existing token from localStorage', async () => {
    mockLocalStorage.getItem.mockReturnValue('existing-token');

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated');
      expect(screen.getByTestId('user-info')).toHaveTextContent('Test User (test@example.com)');
    });
  });

  it('handles successful login', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { token: 'new-token' }
      }),
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    
    await act(async () => {
      loginButton.click();
    });

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated');
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('token', 'new-token');
    });
  });

  it('handles login failure', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({
        success: false,
        error: { message: 'Invalid credentials' }
      }),
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    
    await expect(async () => {
      await act(async () => {
        loginButton.click();
      });
    }).rejects.toThrow('Invalid credentials');

    expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated');
  });

  it('handles successful registration', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { token: 'registration-token' }
      }),
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const registerButton = screen.getByText('Register');
    
    await act(async () => {
      registerButton.click();
    });

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated');
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('token', 'registration-token');
    });
  });

  it('handles logout', async () => {
    mockLocalStorage.getItem.mockReturnValue('existing-token');

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for initial authentication
    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated');
    });

    const logoutButton = screen.getByText('Logout');
    
    await act(async () => {
      logoutButton.click();
    });

    expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated');
    expect(screen.getByTestId('user-info')).toHaveTextContent('No User');
    expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('token');
  });

  it('shows loading state during authentication operations', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    
    // Mock a slow API response
    mockFetch.mockImplementation(() => 
      new Promise(resolve => 
        setTimeout(() => resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { token: 'slow-token' }
          }),
        }), 100)
      )
    );

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    
    act(() => {
      loginButton.click();
    });

    // Should show loading state
    expect(screen.getByTestId('loading-status')).toHaveTextContent('Loading');

    // Wait for completion
    await waitFor(() => {
      expect(screen.getByTestId('loading-status')).toHaveTextContent('Not Loading');
      expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated');
    });
  });

  it('throws error when used outside provider', () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    
    expect(() => {
      render(<TestComponent />);
    }).toThrow('useAuth must be used within an AuthProvider');
    
    consoleSpy.mockRestore();
  });

  it('handles network errors during login', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    
    await expect(async () => {
      await act(async () => {
        loginButton.click();
      });
    }).rejects.toThrow('Network error');
  });

  it('makes correct API calls for login', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { token: 'test-token' }
      }),
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const loginButton = screen.getByText('Login');
    
    await act(async () => {
      loginButton.click();
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: 'test@example.com',
        password: 'password',
      }),
    });
  });

  it('makes correct API calls for registration', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { token: 'test-token' }
      }),
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    const registerButton = screen.getByText('Register');
    
    await act(async () => {
      registerButton.click();
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: 'test@example.com',
        password: 'password',
        name: 'Test User',
      }),
    });
  });
});