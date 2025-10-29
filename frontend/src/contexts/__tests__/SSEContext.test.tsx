import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SSEProvider, useSSE } from '../SSEContext';

// Mock EventSource
class MockEventSource {
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState: number = 0;
  private listeners: { [key: string]: EventListener[] } = {};
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  
  constructor(url: string) {
    this.url = url;
    this.readyState = MockEventSource.CONNECTING;
    
    // Simulate connection opening immediately
    Promise.resolve().then(() => {
      this.readyState = MockEventSource.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    });
  }
  
  close() {
    this.readyState = MockEventSource.CLOSED;
  }
  
  addEventListener(type: string, listener: EventListener) {
    if (!this.listeners[type]) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(listener);
  }
  
  removeEventListener(type: string, listener: EventListener) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter(l => l !== listener);
    }
  }
  
  dispatchEvent(event: Event): boolean {
    return true;
  }
}

// Mock global EventSource
(global as any).EventSource = MockEventSource;

// Test component that uses SSE context
const TestComponent: React.FC = () => {
  const { isConnected, events, connect, disconnect, connectionError, isReconnecting } = useSSE();
  
  return (
    <div>
      <div data-testid="connection-status">
        {isConnected ? 'Connected' : 'Disconnected'}
      </div>
      <div data-testid="connection-error">
        {connectionError || 'No error'}
      </div>
      <div data-testid="reconnecting-status">
        {isReconnecting ? 'Reconnecting' : 'Not reconnecting'}
      </div>
      <div data-testid="events-count">
        {events.length}
      </div>
      <button onClick={() => connect('test-room-123')}>Connect</button>
      <button onClick={disconnect}>Disconnect</button>
    </div>
  );
};

describe('SSEContext', () => {
  beforeEach(() => {
    // Reset navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    });
  });

  it('should provide initial state', () => {
    render(
      <SSEProvider>
        <TestComponent />
      </SSEProvider>
    );

    expect(screen.getByTestId('connection-status')).toHaveTextContent('Disconnected');
    expect(screen.getByTestId('connection-error')).toHaveTextContent('No error');
    expect(screen.getByTestId('reconnecting-status')).toHaveTextContent('Not reconnecting');
    expect(screen.getByTestId('events-count')).toHaveTextContent('0');
  });

  it('should handle connection', async () => {
    render(
      <SSEProvider>
        <TestComponent />
      </SSEProvider>
    );

    const connectButton = screen.getByText('Connect');
    connectButton.click();

    await waitFor(() => {
      expect(screen.getByTestId('connection-status')).toHaveTextContent('Connected');
    });
  });

  it('should handle disconnection', async () => {
    render(
      <SSEProvider>
        <TestComponent />
      </SSEProvider>
    );

    const connectButton = screen.getByText('Connect');
    const disconnectButton = screen.getByText('Disconnect');
    
    connectButton.click();
    
    await waitFor(() => {
      expect(screen.getByTestId('connection-status')).toHaveTextContent('Connected');
    });

    disconnectButton.click();

    await waitFor(() => {
      expect(screen.getByTestId('connection-status')).toHaveTextContent('Disconnected');
    });
  });

  it('should throw error when used outside provider', () => {
    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    
    expect(() => {
      render(<TestComponent />);
    }).toThrow('useSSE must be used within an SSEProvider');
    
    consoleSpy.mockRestore();
  });
});