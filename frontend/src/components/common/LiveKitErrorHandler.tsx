import React, { useState, useEffect } from 'react';
import { VideoOff, MicOff, Wifi, AlertTriangle, RefreshCw } from 'lucide-react';
import { ConnectionState, Room } from 'livekit-client';

interface LiveKitErrorHandlerProps {
  room?: Room;
  children: React.ReactNode;
}

interface LiveKitError {
  type: 'connection' | 'media' | 'permission' | 'network_quality';
  message: string;
  recoverable: boolean;
  action?: string;
}

export const LiveKitErrorHandler: React.FC<LiveKitErrorHandlerProps> = ({ room, children }) => {
  const [error, setError] = useState<LiveKitError | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    room?.state || ConnectionState.Disconnected
  );
  const [retryAttempts, setRetryAttempts] = useState(0);

  useEffect(() => {
    if (!room) return;

    const handleConnectionStateChange = (state: ConnectionState) => {
      setConnectionState(state);
      
      switch (state) {
        case ConnectionState.Disconnected:
          if (retryAttempts < 3) {
            setError({
              type: 'connection',
              message: 'Connection lost. Attempting to reconnect...',
              recoverable: true,
              action: 'Reconnecting automatically'
            });
          } else {
            setError({
              type: 'connection',
              message: 'Unable to maintain connection to the meeting. Please check your internet connection.',
              recoverable: true,
              action: 'Manual retry required'
            });
          }
          break;
        case ConnectionState.Reconnecting:
          setError({
            type: 'connection',
            message: 'Reconnecting to the meeting...',
            recoverable: true,
            action: 'Please wait'
          });
          break;
        case ConnectionState.Connected:
          setError(null);
          setRetryAttempts(0);
          break;
      }
    };

    const handleMediaDeviceError = (error: any) => {
      if (error.name === 'NotAllowedError') {
        setError({
          type: 'permission',
          message: 'Camera and microphone access denied. Please allow permissions and refresh.',
          recoverable: true,
          action: 'Check browser permissions'
        });
      } else if (error.name === 'NotFoundError') {
        setError({
          type: 'media',
          message: 'No camera or microphone found. Please connect a device and try again.',
          recoverable: true,
          action: 'Connect media devices'
        });
      } else {
        setError({
          type: 'media',
          message: 'Unable to access camera or microphone. Please check your device settings.',
          recoverable: true,
          action: 'Check device settings'
        });
      }
    };

    const handleDisconnected = (reason?: any) => {
      if (reason?.code === 4003) {
        setError({
          type: 'connection',
          message: 'You have been removed from the meeting.',
          recoverable: false,
          action: 'Contact meeting host'
        });
      } else if (reason?.code === 4004) {
        setError({
          type: 'connection',
          message: 'Meeting has ended.',
          recoverable: false,
          action: 'Return to lobby'
        });
      }
    };

    room.on('connectionStateChanged', handleConnectionStateChange);
    room.on('mediaDevicesError', handleMediaDeviceError);
    room.on('disconnected', handleDisconnected);

    return () => {
      room.off('connectionStateChanged', handleConnectionStateChange);
      room.off('mediaDevicesError', handleMediaDeviceError);
      room.off('disconnected', handleDisconnected);
    };
  }, [room, retryAttempts]);

  const handleRetry = async () => {
    if (!room || !error?.recoverable) return;

    setRetryAttempts(prev => prev + 1);
    setError(null);

    try {
      if (room.state === ConnectionState.Disconnected) {
        // Note: Reconnection should be handled by LiveKit's automatic reconnection
        // Manual reconnection requires URL and token which we don't have here
        console.log('Room disconnected, waiting for automatic reconnection...');
        setError({
          type: 'connection',
          message: 'Waiting for automatic reconnection...',
          recoverable: true,
          action: 'Please wait or refresh the page'
        });
      }
    } catch (err) {
      console.error('Failed to reconnect:', err);
      setError({
        type: 'connection',
        message: 'Failed to reconnect. Please refresh the page and try again.',
        recoverable: false,
        action: 'Refresh page'
      });
    }
  };

  const getErrorIcon = () => {
    switch (error?.type) {
      case 'media':
        return <VideoOff className="h-8 w-8 text-orange-400" />;
      case 'permission':
        return <MicOff className="h-8 w-8 text-orange-400" />;
      case 'network_quality':
        return <Wifi className="h-8 w-8 text-orange-400" />;
      default:
        return <AlertTriangle className="h-8 w-8 text-orange-400" />;
    }
  };

  if (error && error.type !== 'network_quality') {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="glass-panel p-6 max-w-md w-full mx-4 text-center">
          <div className="flex justify-center mb-4">
            {getErrorIcon()}
          </div>
          
          <h3 className="text-lg font-semibold text-white mb-2">
            Connection Issue
          </h3>
          
          <p className="text-gray-300 mb-4">
            {error.message}
          </p>

          {error.action && (
            <p className="text-sm text-gray-400 mb-4">
              {error.action}
            </p>
          )}

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            {error.recoverable && (
              <button
                onClick={handleRetry}
                className="glass-button px-4 py-2 rounded-lg text-white hover:bg-white/15 transition-colors flex items-center justify-center gap-2"
                aria-label="Retry connection"
              >
                <RefreshCw className="h-4 w-4" />
                Try Again
              </button>
            )}
            
            <button
              onClick={() => window.location.href = '/lobby'}
              className="bg-orange-500 hover:bg-orange-600 px-4 py-2 rounded-lg text-white transition-colors"
              aria-label="Return to lobby"
            >
              Return to Lobby
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Show connection status indicator for network quality issues
  if (connectionState === ConnectionState.Reconnecting) {
    return (
      <>
        {children}
        <div className="fixed top-4 right-4 glass-panel px-3 py-2 text-sm text-white z-40">
          <div className="flex items-center gap-2">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-orange-400 border-t-transparent"></div>
            Reconnecting...
          </div>
        </div>
      </>
    );
  }

  return <>{children}</>;
};

// Hook for handling LiveKit errors in components
export const useLiveKitError = () => {
  const [error, setError] = useState<LiveKitError | null>(null);

  const handleLiveKitError = (error: any, context?: string) => {
    console.error('LiveKit error:', error, context);

    if (error.name === 'NotAllowedError') {
      setError({
        type: 'permission',
        message: 'Media permissions denied. Please allow camera and microphone access.',
        recoverable: true,
      });
    } else if (error.name === 'NotFoundError') {
      setError({
        type: 'media',
        message: 'No media devices found. Please connect a camera or microphone.',
        recoverable: true,
      });
    } else if (error.message?.includes('connection')) {
      setError({
        type: 'connection',
        message: 'Unable to connect to the meeting. Please check your internet connection.',
        recoverable: true,
      });
    } else {
      setError({
        type: 'connection',
        message: 'An unexpected error occurred. Please try again.',
        recoverable: true,
      });
    }
  };

  const clearError = () => setError(null);

  return { error, handleLiveKitError, clearError };
};