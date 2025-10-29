import React, { useState, useEffect } from 'react';
import { WifiOff, RefreshCw, AlertCircle } from 'lucide-react';

interface NetworkErrorHandlerProps {
  children: React.ReactNode;
}

interface NetworkError {
  type: 'offline' | 'timeout' | 'server_error' | 'connection_failed';
  message: string;
  retryable: boolean;
}

export const NetworkErrorHandler: React.FC<NetworkErrorHandlerProps> = ({ children }) => {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [networkError, setNetworkError] = useState<NetworkError | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setNetworkError(null);
      setRetryCount(0);
    };

    const handleOffline = () => {
      setIsOnline(false);
      setNetworkError({
        type: 'offline',
        message: 'You appear to be offline. Please check your internet connection.',
        retryable: true,
      });
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleRetry = async () => {
    if (retryCount >= 3) {
      setNetworkError({
        type: 'connection_failed',
        message: 'Unable to establish connection after multiple attempts. Please refresh the page.',
        retryable: false,
      });
      return;
    }

    setRetryCount(prev => prev + 1);
    
    try {
      // Test connectivity with a simple fetch
      const response = await fetch('/api/health', {
        method: 'HEAD',
        cache: 'no-cache',
      });
      
      if (response.ok) {
        setNetworkError(null);
        setRetryCount(0);
      } else {
        throw new Error('Server responded with error');
      }
    } catch (error) {
      setNetworkError({
        type: 'server_error',
        message: 'Server is currently unavailable. Please try again in a moment.',
        retryable: retryCount < 2,
      });
    }
  };

  if (!isOnline || networkError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-900 to-blue-800">
        <div className="glass-panel p-8 max-w-md w-full mx-4 text-center">
          <div className="flex justify-center mb-4">
            {!isOnline ? (
              <WifiOff className="h-12 w-12 text-orange-400" />
            ) : (
              <AlertCircle className="h-12 w-12 text-orange-400" />
            )}
          </div>
          
          <h2 className="text-xl font-semibold text-white mb-2">
            {!isOnline ? 'No Internet Connection' : 'Connection Problem'}
          </h2>
          
          <p className="text-gray-300 mb-6">
            {networkError?.message || 'Please check your internet connection and try again.'}
          </p>

          {retryCount > 0 && (
            <p className="text-sm text-gray-400 mb-4">
              Retry attempt {retryCount} of 3
            </p>
          )}

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            {(networkError?.retryable !== false) && (
              <button
                onClick={handleRetry}
                disabled={retryCount >= 3}
                className="glass-button px-4 py-2 rounded-lg text-white hover:bg-white/15 transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Retry connection"
              >
                <RefreshCw className="h-4 w-4" />
                {retryCount > 0 ? 'Retrying...' : 'Try Again'}
              </button>
            )}
            
            <button
              onClick={() => window.location.reload()}
              className="bg-orange-500 hover:bg-orange-600 px-4 py-2 rounded-lg text-white transition-colors"
              aria-label="Refresh the page"
            >
              Refresh Page
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

// Hook for handling network errors in components
export const useNetworkError = () => {
  const [error, setError] = useState<NetworkError | null>(null);

  const handleNetworkError = (error: any) => {
    if (!navigator.onLine) {
      setError({
        type: 'offline',
        message: 'You appear to be offline. Please check your internet connection.',
        retryable: true,
      });
    } else if (error.code === 'NETWORK_ERROR' || error.message?.includes('fetch')) {
      setError({
        type: 'connection_failed',
        message: 'Unable to connect to the server. Please try again.',
        retryable: true,
      });
    } else if (error.response?.status >= 500) {
      setError({
        type: 'server_error',
        message: 'Server error occurred. Please try again later.',
        retryable: true,
      });
    } else if (error.code === 'TIMEOUT') {
      setError({
        type: 'timeout',
        message: 'Request timed out. Please check your connection and try again.',
        retryable: true,
      });
    }
  };

  const clearError = () => setError(null);

  return { error, handleNetworkError, clearError };
};