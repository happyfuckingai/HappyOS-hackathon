import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import { ErrorBoundary } from '../../components/common/ErrorBoundary';
import { NetworkErrorHandler } from '../../components/common/NetworkErrorHandler';
import { AuthProvider } from '../../contexts/AuthContext';

// Mock fetch for network error testing
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock navigator.onLine
Object.defineProperty(navigator, 'onLine', {
  writable: true,
  value: true,
});

// Component that simulates network requests
const NetworkTestComponent: React.FC = () => {
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  const makeRequest = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/test');
      if (!response.ok) {
        throw new Error('Network request failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button onClick={makeRequest} disabled={loading}>
        {loading ? 'Loading...' : 'Make Request'}
      </button>
      {error && <div role="alert">Error: {error}</div>}
    </div>
  );
};

// Component that throws errors for testing
const ErrorThrowingComponent: React.FC<{ shouldThrow: boolean }> = ({ shouldThrow }) => {
  if (shouldThrow) {
    throw new Error('Component error for testing');
  }
  return <div>Component loaded successfully</div>;
};

const TestApp: React.FC<{ throwError?: boolean; networkError?: boolean }> = ({ 
  throwError = false, 
  networkError = false 
}) => {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <NetworkErrorHandler>
          <AuthProvider>
            <div>
              <h1>Test Application</h1>
              {throwError && <ErrorThrowingComponent shouldThrow={true} />}
              {networkError && <NetworkTestComponent />}
              {!throwError && !networkError && <div>App loaded successfully</div>}
            </div>
          </AuthProvider>
        </NetworkErrorHandler>
      </ErrorBoundary>
    </BrowserRouter>
  );
};

describe('Error Handling Integration', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    // Reset navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    });
    
    // Suppress console.error for error boundary tests
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders application successfully when no errors occur', () => {
    render(<TestApp />);

    expect(screen.getByText('Test Application')).toBeInTheDocument();
    expect(screen.getByText('App loaded successfully')).toBeInTheDocument();
  });

  it('catches and displays component errors with error boundary', () => {
    render(<TestApp throwError={true} />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/We encountered an unexpected error/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /refresh page/i })).toBeInTheDocument();
  });

  it('handles network errors gracefully', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network request failed'));

    render(<TestApp networkError={true} />);

    const requestButton = screen.getByRole('button', { name: /make request/i });
    fireEvent.click(requestButton);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Error: Network request failed');
    });
  });

  it('detects offline state and shows appropriate UI', async () => {
    // Simulate going offline
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: false,
    });

    // Trigger offline event
    const offlineEvent = new Event('offline');
    window.dispatchEvent(offlineEvent);

    render(<TestApp />);

    await waitFor(() => {
      expect(screen.getByText('No Internet Connection')).toBeInTheDocument();
      expect(screen.getByText(/Please check your internet connection/)).toBeInTheDocument();
    });
  });

  it('recovers when coming back online', async () => {
    // Start offline
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: false,
    });

    render(<TestApp />);

    // Trigger offline event
    const offlineEvent = new Event('offline');
    window.dispatchEvent(offlineEvent);

    await waitFor(() => {
      expect(screen.getByText('No Internet Connection')).toBeInTheDocument();
    });

    // Come back online
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    });

    const onlineEvent = new Event('online');
    window.dispatchEvent(onlineEvent);

    await waitFor(() => {
      expect(screen.queryByText('No Internet Connection')).not.toBeInTheDocument();
      expect(screen.getByText('Test Application')).toBeInTheDocument();
    });
  });

  it('provides retry functionality for network errors', async () => {
    // Mock health check endpoint
    mockFetch.mockImplementation((url) => {
      if (url === '/api/health') {
        return Promise.resolve({ ok: true });
      }
      return Promise.reject(new Error('Network error'));
    });

    // Start offline
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: false,
    });

    render(<TestApp />);

    // Trigger offline event
    const offlineEvent = new Event('offline');
    window.dispatchEvent(offlineEvent);

    await waitFor(() => {
      expect(screen.getByText('No Internet Connection')).toBeInTheDocument();
    });

    // Try to retry
    const retryButton = screen.getByRole('button', { name: /try again/i });
    
    // Come back online
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    });

    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.queryByText('No Internet Connection')).not.toBeInTheDocument();
    });
  });

  it('shows loading states during network operations', async () => {
    mockFetch.mockImplementation(() => 
      new Promise(resolve => setTimeout(() => resolve({ ok: true }), 100))
    );

    render(<TestApp networkError={true} />);

    const requestButton = screen.getByRole('button', { name: /make request/i });
    fireEvent.click(requestButton);

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(requestButton).toBeDisabled();

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      expect(requestButton).not.toBeDisabled();
    });
  });

  it('handles multiple error types simultaneously', async () => {
    // Simulate both offline and component error
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: false,
    });

    render(<TestApp throwError={true} />);

    // Error boundary should take precedence over network handler
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('provides accessible error messages', () => {
    render(<TestApp throwError={true} />);

    // Error boundary should provide accessible content
    const retryButton = screen.getByRole('button', { name: /try again/i });
    const refreshButton = screen.getByRole('button', { name: /refresh page/i });

    expect(retryButton).toHaveAttribute('aria-label');
    expect(refreshButton).toHaveAttribute('aria-label');
  });
});