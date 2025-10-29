import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import App from '../../App';

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
    exp: Date.now() / 1000 + 3600,
  })),
}));

// Mock LiveKit components
jest.mock('@livekit/components-react', () => ({
  LiveKitRoom: ({ children }: any) => <div data-testid="livekit-room">{children}</div>,
  VideoConference: () => <div data-testid="video-conference">Video Conference</div>,
  RoomAudioRenderer: () => <div data-testid="room-audio-renderer">Audio Renderer</div>,
}));

// Mock EventSource for SSE
class MockEventSource {
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState: number = 1;
  
  constructor(url: string) {
    this.url = url;
  }
  
  close() {
    this.readyState = 2;
  }
  
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
}

(global as any).EventSource = MockEventSource;

const renderApp = () => {
  return render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
};

describe('User Flow Integration Tests', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockLocalStorage.getItem.mockClear();
    mockLocalStorage.setItem.mockClear();
    mockLocalStorage.removeItem.mockClear();
    
    // Start with no stored token
    mockLocalStorage.getItem.mockReturnValue(null);
    
    // Suppress console errors for tests
    console.error = jest.fn();
    console.log = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Authentication Flow', () => {
    it('completes full login flow from landing to lobby', async () => {
      const user = userEvent.setup();

      // Mock successful login
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: { token: 'login-token' }
        }),
      });

      renderApp();

      // Should start on landing page
      expect(screen.getByText('Meet')).toBeInTheDocument();
      expect(screen.getByText('Mind')).toBeInTheDocument();

      // Click Get Started
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      // Should navigate to auth page
      await waitFor(() => {
        expect(screen.getByText('Welcome Back')).toBeInTheDocument();
      });

      // Fill in login form
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');

      // Submit login
      const loginButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(loginButton);

      // Should navigate to lobby after successful login
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
        expect(screen.getByText('Join Meeting')).toBeInTheDocument();
      });

      // Verify token was stored
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('token', 'login-token');
    });

    it('completes full registration flow', async () => {
      const user = userEvent.setup();

      // Mock successful registration
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: { token: 'registration-token' }
        }),
      });

      renderApp();

      // Navigate to auth page
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      await waitFor(() => {
        expect(screen.getByText('Welcome Back')).toBeInTheDocument();
      });

      // Switch to register tab
      const registerTab = screen.getByRole('tab', { name: /sign up/i });
      await user.click(registerTab);

      // Fill in registration form
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText('Password');
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      
      await user.type(nameInput, 'Test User');
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'password123');

      // Submit registration
      const registerButton = screen.getByRole('button', { name: /create account/i });
      await user.click(registerButton);

      // Should navigate to lobby after successful registration
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('token', 'registration-token');
    });

    it('handles authentication errors gracefully', async () => {
      const user = userEvent.setup();

      // Mock failed login
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({
          success: false,
          error: { message: 'Invalid credentials' }
        }),
      });

      renderApp();

      // Navigate to auth and attempt login
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      
      await user.type(emailInput, 'wrong@example.com');
      await user.type(passwordInput, 'wrongpassword');

      const loginButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(loginButton);

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText('Invalid credentials')).toBeInTheDocument();
      });

      // Should remain on auth page
      expect(screen.getByText('Welcome Back')).toBeInTheDocument();
    });
  });

  describe('Meeting Flow', () => {
    beforeEach(() => {
      // Mock authenticated state
      mockLocalStorage.getItem.mockReturnValue('valid-token');
    });

    it('completes create meeting flow', async () => {
      const user = userEvent.setup();

      // Mock create meeting API
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          data: { roomId: 'new-room-123' }
        }),
      });

      // Mock LiveKit token API
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ token: 'livekit-token' }),
      });

      renderApp();

      // Should start on lobby (authenticated)
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      // Create a new meeting
      const createButton = screen.getByRole('button', { name: /create meeting/i });
      await user.click(createButton);

      // Should navigate to meeting page
      await waitFor(() => {
        expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
      });

      // Verify API calls
      expect(mockFetch).toHaveBeenCalledWith('/api/meetings', expect.objectContaining({
        method: 'POST',
      }));
    });

    it('completes join meeting flow', async () => {
      const user = userEvent.setup();

      // Mock LiveKit token API
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ token: 'livekit-token' }),
      });

      renderApp();

      // Should start on lobby
      await waitFor(() => {
        expect(screen.getByText('Join Meeting')).toBeInTheDocument();
      });

      // Enter room ID and join
      const roomIdInput = screen.getByPlaceholderText(/enter room id/i);
      await user.type(roomIdInput, 'existing-room-456');

      const joinButton = screen.getByRole('button', { name: /join meeting/i });
      await user.click(joinButton);

      // Should navigate to meeting page
      await waitFor(() => {
        expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
      });
    });

    it('handles meeting creation errors', async () => {
      const user = userEvent.setup();

      // Mock failed meeting creation
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({
          success: false,
          error: { message: 'Failed to create meeting' }
        }),
      });

      renderApp();

      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create meeting/i });
      await user.click(createButton);

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText('Failed to create meeting')).toBeInTheDocument();
      });

      // Should remain on lobby
      expect(screen.getByText('Create Meeting')).toBeInTheDocument();
    });
  });

  describe('Navigation Flow', () => {
    it('redirects unauthenticated users to auth page', async () => {
      renderApp();

      // Try to navigate directly to lobby
      window.history.pushState({}, '', '/lobby');

      await waitFor(() => {
        // Should redirect to auth page
        expect(screen.getByText('Welcome Back')).toBeInTheDocument();
      });
    });

    it('allows authenticated users to access protected routes', async () => {
      // Mock authenticated state
      mockLocalStorage.getItem.mockReturnValue('valid-token');

      renderApp();

      // Navigate to lobby
      window.history.pushState({}, '', '/lobby');

      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });
    });

    it('handles logout and redirects to landing', async () => {
      const user = userEvent.setup();
      
      // Start authenticated
      mockLocalStorage.getItem.mockReturnValue('valid-token');

      renderApp();

      // Navigate to lobby
      window.history.pushState({}, '', '/lobby');

      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      // Find and click logout (assuming it's in header or menu)
      const logoutButton = screen.getByRole('button', { name: /logout/i });
      await user.click(logoutButton);

      // Should redirect to landing page
      await waitFor(() => {
        expect(screen.getByText('Meet')).toBeInTheDocument();
        expect(screen.getByText('Mind')).toBeInTheDocument();
      });

      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('token');
    });
  });

  describe('Error Recovery Flow', () => {
    it('recovers from network errors', async () => {
      const user = userEvent.setup();

      // Mock network failure then success
      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { token: 'recovery-token' }
          }),
        });

      renderApp();

      // Navigate to auth
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      });

      // Attempt login (will fail)
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');

      const loginButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(loginButton);

      // Should show network error
      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      // Retry login (will succeed)
      await user.click(loginButton);

      // Should navigate to lobby
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });
    });
  });
});