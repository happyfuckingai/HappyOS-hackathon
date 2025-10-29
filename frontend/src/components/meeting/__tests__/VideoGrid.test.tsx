import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import VideoGrid from '../VideoGrid';

// Mock LiveKit components
jest.mock('@livekit/components-react', () => ({
  LiveKitRoom: ({ children, onError, onDisconnected }: any) => (
    <div data-testid="livekit-room">
      {children}
      <button onClick={() => onError?.(new Error('Test error'))}>Trigger Error</button>
      <button onClick={() => onDisconnected?.()}>Disconnect</button>
    </div>
  ),
  VideoConference: () => <div data-testid="video-conference">Video Conference</div>,
  RoomAudioRenderer: () => <div data-testid="room-audio-renderer">Audio Renderer</div>,
}));

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

describe('VideoGrid', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockLocalStorage.getItem.mockReturnValue('mock-token');
    console.error = jest.fn();
    console.log = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('shows loading state initially', () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<VideoGrid roomId="test-room" />);

    expect(screen.getByText('Connecting to video...')).toBeInTheDocument();
    expect(screen.getByText('Please wait while we set up your video connection')).toBeInTheDocument();
  });

  it('renders LiveKit room when token is fetched successfully', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ token: 'mock-livekit-token' }),
    });

    render(<VideoGrid roomId="test-room" />);

    await waitFor(() => {
      expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
      expect(screen.getByTestId('video-conference')).toBeInTheDocument();
      expect(screen.getByTestId('room-audio-renderer')).toBeInTheDocument();
    });
  });

  it('shows error state when token fetch fails', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    render(<VideoGrid roomId="test-room" />);

    await waitFor(() => {
      expect(screen.getByText('Connection Error')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /retry connection/i })).toBeInTheDocument();
    });
  });

  it('shows error state when API returns error status', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      statusText: 'Unauthorized',
    });

    render(<VideoGrid roomId="test-room" />);

    await waitFor(() => {
      expect(screen.getByText('Connection Error')).toBeInTheDocument();
      expect(screen.getByText('Failed to get LiveKit token: Unauthorized')).toBeInTheDocument();
    });
  });

  it('shows authentication required when no token is available', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ token: '' }),
    });

    render(<VideoGrid roomId="test-room" />);

    await waitFor(() => {
      expect(screen.getByText('Authentication Required')).toBeInTheDocument();
      expect(screen.getByText('Unable to authenticate with video service')).toBeInTheDocument();
    });
  });

  it('makes API call with correct parameters', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ token: 'mock-token' }),
    });

    render(<VideoGrid roomId="test-room-123" />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/livekit/token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer mock-token',
        },
        body: JSON.stringify({ roomId: 'test-room-123' }),
      });
    });
  });

  it('does not fetch token when roomId is not provided', () => {
    render(<VideoGrid roomId="" />);

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('refetches token when roomId changes', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ token: 'mock-token' }),
    });

    const { rerender } = render(<VideoGrid roomId="room-1" />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    rerender(<VideoGrid roomId="room-2" />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  it('uses environment variable for server URL', async () => {
    const originalEnv = process.env.REACT_APP_LIVEKIT_URL;
    process.env.REACT_APP_LIVEKIT_URL = 'ws://custom-server:8080';

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ token: 'mock-token' }),
    });

    render(<VideoGrid roomId="test-room" />);

    await waitFor(() => {
      expect(screen.getByTestId('livekit-room')).toBeInTheDocument();
    });

    // Restore original env
    process.env.REACT_APP_LIVEKIT_URL = originalEnv;
  });
});