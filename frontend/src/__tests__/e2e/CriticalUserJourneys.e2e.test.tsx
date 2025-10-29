import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import App from '../../App';

// Mock fetch for E2E tests
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

// Mock LiveKit components with more realistic behavior
jest.mock('@livekit/components-react', () => ({
  LiveKitRoom: ({ children, onConnected, onDisconnected, onError }: any) => {
    React.useEffect(() => {
      // Simulate connection after a delay
      const timer = setTimeout(() => {
        onConnected?.();
      }, 100);
      return () => clearTimeout(timer);
    }, [onConnected]);

    return (
      <div data-testid="livekit-room">
        {children}
        <button onClick={() => onError?.(new Error('Connection failed'))}>
          Simulate Error
        </button>
        <button onClick={() => onDisconnected?.()}>
          Simulate Disconnect
        </button>
      </div>
    );
  },
  VideoConference: () => (
    <div data-testid="video-conference">
      <div data-testid="local-video">Local Video</div>
      <div data-testid="remote-videos">Remote Videos</div>
    </div>
  ),
  RoomAudioRenderer: () => <div data-testid="room-audio-renderer">Audio</div>,
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
    // Simulate connection opening
    setTimeout(() => {
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 50);
  }
  
  close() {
    this.readyState = 2;
  }
  
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }

  // Method to simulate receiving messages
  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }
}

(global as any).EventSource = MockEventSource;

// Mock WebSocket
class MockWebSocket {
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readyState: number = 1;
  
  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 50);
  }
  
  send(data: string) {
    // Echo back for testing
    setTimeout(() => {
      if (this.onmessage) {
        this.onmessage(new MessageEvent('message', { data }));
      }
    }, 10);
  }
  
  close() {
    this.readyState = 3;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }
}

(global as any).WebSocket = MockWebSocket;

const renderApp = () => {
  return render(
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
};

describe('Critical User Journeys E2E Tests', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockLocalStorage.getItem.mockClear();
    mockLocalStorage.setItem.mockClear();
    mockLocalStorage.removeItem.mockClear();
    
    // Start with no stored token
    mockLocalStorage.getItem.mockReturnValue(null);
    
    // Suppress console for tests
    console.error = jest.fn();
    console.log = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Complete Meeting Journey', () => {
    it('completes full journey from landing to active meeting', async () => {
      const user = userEvent.setup();

      // Mock all required API calls
      mockFetch
        // Login
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { token: 'auth-token' }
          }),
        })
        // Create meeting
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { roomId: 'meeting-room-123' }
          }),
        })
        // Get LiveKit token
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ token: 'livekit-token' }),
        });

      renderApp();

      // Step 1: Start on landing page
      expect(screen.getByText('Meet')).toBeInTheDocument();
      expect(screen.getByText('Mind')).toBeInTheDocument();

      // Step 2: Navigate to authentication
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      await waitFor(() => {
        expect(screen.getByText('Welcome Back')).toBeInTheDocument();
      });

      // Step 3: Complete login
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');

      const loginButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(loginButton);

      // Step 4: Navigate to lobby
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
        expect(screen.getByText('Join Meeting')).toBeInTheDocument();
      });

      // Step 5: Create a meeting
      const createMeetingButton = screen.getByRole('button', { name: /create meeting/i });
      await user.click(createMeetingButton);

      // Step 6: Verify meeting page loads
      await waitFor(() => {
        expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
        expect(screen.getByTestId('video-conference')).toBeInTheDocument();
      });

      // Step 7: Verify meeting components are present
      expect(screen.getByTestId('local-video')).toBeInTheDocument();
      expect(screen.getByTestId('room-audio-renderer')).toBeInTheDocument();

      // Verify all API calls were made correctly
      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('token', 'auth-token');
    });

    it('completes join meeting journey', async () => {
      const user = userEvent.setup();

      // Mock authenticated state
      mockLocalStorage.getItem.mockReturnValue('existing-token');

      // Mock LiveKit token API
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ token: 'livekit-token' }),
      });

      renderApp();

      // Should start on lobby (authenticated)
      await waitFor(() => {
        expect(screen.getByText('Join Meeting')).toBeInTheDocument();
      });

      // Enter room ID
      const roomIdInput = screen.getByPlaceholderText(/enter room id/i);
      await user.type(roomIdInput, 'existing-room-456');

      // Join meeting
      const joinButton = screen.getByRole('button', { name: /join meeting/i });
      await user.click(joinButton);

      // Verify meeting loads
      await waitFor(() => {
        expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
      });

      expect(mockFetch).toHaveBeenCalledWith('/api/livekit/token', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ roomId: 'existing-room-456' }),
      }));
    });
  });

  describe('Meeting Interaction Journey', () => {
    beforeEach(() => {
      // Mock authenticated state
      mockLocalStorage.getItem.mockReturnValue('valid-token');
      
      // Mock meeting APIs
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { roomId: 'test-room' }
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ token: 'livekit-token' }),
        });
    });

    it('handles meeting controls and interactions', async () => {
      const user = userEvent.setup();

      renderApp();

      // Navigate to lobby and create meeting
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create meeting/i });
      await user.click(createButton);

      // Wait for meeting to load
      await waitFor(() => {
        expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
      });

      // Test FAB menu interaction
      const fabButton = screen.getByRole('button', { name: /meeting controls/i });
      await user.click(fabButton);

      // Should open controls panel
      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
        expect(screen.getByText('Chat')).toBeInTheDocument();
        expect(screen.getByText('Share & Recording')).toBeInTheDocument();
      });

      // Test settings tab
      const settingsTab = screen.getByRole('tab', { name: /settings/i });
      await user.click(settingsTab);

      // Should show device controls
      expect(screen.getByText(/microphone/i)).toBeInTheDocument();
      expect(screen.getByText(/camera/i)).toBeInTheDocument();

      // Test chat tab
      const chatTab = screen.getByRole('tab', { name: /chat/i });
      await user.click(chatTab);

      // Should show chat interface
      const chatInput = screen.getByPlaceholderText(/type a message/i);
      expect(chatInput).toBeInTheDocument();

      // Send a chat message
      await user.type(chatInput, 'Hello everyone!');
      const sendButton = screen.getByRole('button', { name: /send/i });
      await user.click(sendButton);

      // Message should appear in chat
      await waitFor(() => {
        expect(screen.getByText('Hello everyone!')).toBeInTheDocument();
      });
    });

    it('handles real-time AI features', async () => {
      const user = userEvent.setup();

      renderApp();

      // Create and join meeting
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create meeting/i });
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
      });

      // AI panel should be visible
      expect(screen.getByText('AI Notes')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();

      // Simulate receiving AI events
      const mockSSE = new MockEventSource('/api/sse/test-room');
      
      // Simulate note event
      mockSSE.simulateMessage({
        type: 'note',
        content: 'Important discussion about project timeline',
        speaker: 'Test User',
        timestamp: new Date().toISOString(),
      });

      // Note should appear in AI panel
      await waitFor(() => {
        expect(screen.getByText('Important discussion about project timeline')).toBeInTheDocument();
      });

      // Simulate action item
      mockSSE.simulateMessage({
        type: 'action',
        description: 'Follow up on budget approval',
        assignee: 'Test User',
        timestamp: new Date().toISOString(),
      });

      // Action should appear in actions tab
      const actionsTab = screen.getByRole('tab', { name: /actions/i });
      await user.click(actionsTab);

      await waitFor(() => {
        expect(screen.getByText('Follow up on budget approval')).toBeInTheDocument();
      });
    });
  });

  describe('Error Recovery Journey', () => {
    it('recovers from connection failures', async () => {
      const user = userEvent.setup();

      // Mock authenticated state
      mockLocalStorage.getItem.mockReturnValue('valid-token');

      // Mock initial success then failure
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { roomId: 'test-room' }
          }),
        })
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ token: 'livekit-token' }),
        });

      renderApp();

      // Create meeting
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create meeting/i });
      await user.click(createButton);

      // Should show connection error
      await waitFor(() => {
        expect(screen.getByText('Connection Error')).toBeInTheDocument();
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      // Retry connection
      const retryButton = screen.getByRole('button', { name: /retry connection/i });
      await user.click(retryButton);

      // Should eventually connect
      await waitFor(() => {
        expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
      });
    });

    it('handles offline/online transitions', async () => {
      const user = userEvent.setup();

      // Mock authenticated state
      mockLocalStorage.getItem.mockReturnValue('valid-token');

      renderApp();

      // Start online
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      // Simulate going offline
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: false,
      });

      const offlineEvent = new Event('offline');
      window.dispatchEvent(offlineEvent);

      // Should show offline indicator
      await waitFor(() => {
        expect(screen.getByText('No Internet Connection')).toBeInTheDocument();
      });

      // Simulate coming back online
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true,
      });

      const onlineEvent = new Event('online');
      window.dispatchEvent(onlineEvent);

      // Should recover
      await waitFor(() => {
        expect(screen.queryByText('No Internet Connection')).not.toBeInTheDocument();
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });
    });
  });

  describe('Session Management Journey', () => {
    it('handles session expiration gracefully', async () => {
      const user = userEvent.setup();

      // Start with valid token
      mockLocalStorage.getItem.mockReturnValue('valid-token');

      renderApp();

      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      // Simulate token expiration during API call
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({
          success: false,
          error: { message: 'Token expired' }
        }),
      });

      const createButton = screen.getByRole('button', { name: /create meeting/i });
      await user.click(createButton);

      // Should redirect to auth page
      await waitFor(() => {
        expect(screen.getByText('Welcome Back')).toBeInTheDocument();
      });

      // Token should be removed
      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('token');
    });

    it('persists user session across page refreshes', async () => {
      // Mock valid token in localStorage
      mockLocalStorage.getItem.mockReturnValue('persistent-token');

      renderApp();

      // Should automatically authenticate and go to lobby
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      // User should be authenticated without login
      expect(mockFetch).not.toHaveBeenCalledWith('/api/auth/login', expect.anything());
    });
  });

  describe('Multi-User Meeting Journey', () => {
    it('simulates multi-user meeting interactions', async () => {
      const user = userEvent.setup();

      // Mock authenticated state
      mockLocalStorage.getItem.mockReturnValue('valid-token');

      // Mock meeting creation and LiveKit token
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            data: { roomId: 'multi-user-room' }
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ token: 'livekit-token' }),
        });

      renderApp();

      // Create meeting
      await waitFor(() => {
        expect(screen.getByText('Create Meeting')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create meeting/i });
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
      });

      // Simulate participants joining
      const participantsList = screen.getByTestId('participants-list');
      expect(participantsList).toBeInTheDocument();

      // Simulate chat messages from other participants
      const mockWS = new MockWebSocket('ws://localhost/chat');
      
      // Simulate receiving a message
      mockWS.onmessage?.({
        data: JSON.stringify({
          type: 'chat_message',
          content: 'Hello from another participant!',
          sender: 'Other User',
          timestamp: new Date().toISOString(),
        })
      } as MessageEvent);

      // Message should appear in chat
      const fabButton = screen.getByRole('button', { name: /meeting controls/i });
      await user.click(fabButton);

      const chatTab = screen.getByRole('tab', { name: /chat/i });
      await user.click(chatTab);

      await waitFor(() => {
        expect(screen.getByText('Hello from another participant!')).toBeInTheDocument();
      });
    });
  });
});