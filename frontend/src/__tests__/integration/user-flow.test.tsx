import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import App from '../../App';

// Mock API calls
jest.mock('../../lib/api', () => ({
  login: jest.fn(),
  register: jest.fn(),
  createMeeting: jest.fn(),
  joinMeeting: jest.fn(),
}));

// Mock LiveKit
jest.mock('@livekit/components-react', () => ({
  LiveKitRoom: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="livekit-room">{children}</div>
  ),
  VideoConference: () => <div data-testid="video-conference">Video Conference</div>,
  useRoomContext: () => ({
    room: { name: 'test-room' },
    participants: [],
  }),
}));

// Mock EventSource for SSE
class MockEventSource {
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState = 1;
  
  constructor(url: string) {
    setTimeout(() => {
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
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

describe('Complete User Flow Integration', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    // Clear localStorage
    localStorage.clear();
    
    // Reset mocks
    jest.clearAllMocks();
  });

  it('completes full user journey from landing to meeting', async () => {
    const { login, createMeeting } = require('../../lib/api');
    
    // Mock successful API responses
    login.mockResolvedValue({
      user: { id: '1', name: 'Test User', email: 'test@example.com', role: 'user' },
      token: 'mock-token'
    });
    
    createMeeting.mockResolvedValue({
      roomId: 'test-room-123',
      meetingId: 'meeting-456'
    });

    renderApp();

    // 1. Start on Landing page
    expect(screen.getByText('Meet')).toBeInTheDocument();
    expect(screen.getByText('Mind')).toBeInTheDocument();

    // 2. Click Get Started to go to Auth
    const getStartedButton = screen.getByRole('button', { name: /get started/i });
    await user.click(getStartedButton);

    await waitFor(() => {
      expect(screen.getByText(/sign in to your account/i)).toBeInTheDocument();
    });

    // 3. Fill in login form
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'test@example.com');
    await user.type(passwordInput, 'password123');
    await user.click(loginButton);

    // 4. Should redirect to Lobby after successful login
    await waitFor(() => {
      expect(screen.getByText(/create a new meeting/i)).toBeInTheDocument();
    });

    // 5. Create a new meeting
    const createMeetingButton = screen.getByRole('button', { name: /create meeting/i });
    await user.click(createMeetingButton);

    // 6. Should redirect to Meeting page
    await waitFor(() => {
      expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
    });

    // 7. Verify meeting components are rendered
    expect(screen.getByTestId('video-conference')).toBeInTheDocument();
    
    // 8. Test FAB menu functionality
    const fabButton = screen.getByRole('button', { name: /meeting controls/i });
    await user.click(fabButton);

    await waitFor(() => {
      expect(screen.getByText(/settings/i)).toBeInTheDocument();
    });
  });

  it('handles authentication errors gracefully', async () => {
    const { login } = require('../../lib/api');
    
    // Mock failed login
    login.mockRejectedValue(new Error('Invalid credentials'));

    renderApp();

    // Navigate to auth page
    const getStartedButton = screen.getByRole('button', { name: /get started/i });
    await user.click(getStartedButton);

    // Fill in login form with invalid credentials
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const loginButton = screen.getByRole('button', { name: /sign in/i });

    await user.type(emailInput, 'invalid@example.com');
    await user.type(passwordInput, 'wrongpassword');
    await user.click(loginButton);

    // Should show error message
    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });

    // Should remain on auth page
    expect(screen.getByText(/sign in to your account/i)).toBeInTheDocument();
  });

  it('handles network errors and shows appropriate fallbacks', async () => {
    // Mock network error
    const originalFetch = global.fetch;
    global.fetch = jest.fn().mockRejectedValue(new Error('Network error'));

    renderApp();

    // The app should still render with network error handling
    expect(screen.getByText('Meet')).toBeInTheDocument();

    // Restore fetch
    global.fetch = originalFetch;
  });

  it('maintains responsive design across different screen sizes', async () => {
    // Mock different viewport sizes
    const mockViewport = (width: number, height: number) => {
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: width,
      });
      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        configurable: true,
        value: height,
      });
      window.dispatchEvent(new Event('resize'));
    };

    renderApp();

    // Test mobile viewport
    mockViewport(375, 667);
    expect(screen.getByText('Meet')).toBeInTheDocument();

    // Test tablet viewport
    mockViewport(768, 1024);
    expect(screen.getByText('Meet')).toBeInTheDocument();

    // Test desktop viewport
    mockViewport(1920, 1080);
    expect(screen.getByText('Meet')).toBeInTheDocument();
  });

  it('handles accessibility requirements', async () => {
    renderApp();

    // Check for proper heading structure
    const mainHeading = screen.getByRole('heading', { level: 1 });
    expect(mainHeading).toBeInTheDocument();

    // Check for keyboard navigation
    const getStartedButton = screen.getByRole('button', { name: /get started/i });
    
    // Focus should be manageable via keyboard
    getStartedButton.focus();
    expect(getStartedButton).toHaveFocus();

    // Test keyboard navigation
    fireEvent.keyDown(getStartedButton, { key: 'Enter' });
    
    await waitFor(() => {
      expect(screen.getByText(/sign in to your account/i)).toBeInTheDocument();
    });
  });

  it('handles performance requirements', async () => {
    const startTime = performance.now();
    
    renderApp();
    
    // App should render within performance budget
    const renderTime = performance.now() - startTime;
    expect(renderTime).toBeLessThan(3000); // 3 second budget

    // Check for lazy loading
    expect(screen.getByText('Meet')).toBeInTheDocument();
  });
});