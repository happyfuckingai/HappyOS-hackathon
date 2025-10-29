import React, { useEffect, useState, useCallback, memo } from 'react';
import {
  LiveKitRoom,
  VideoConference,
  RoomAudioRenderer,
} from '@livekit/components-react';
import '@livekit/components-styles';
import { VideoGridProps } from '../../types';

const VideoGrid: React.FC<VideoGridProps> = memo(({ roomId }) => {
  const [token, setToken] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // LiveKit server URL - this should come from environment variables
  const serverUrl = process.env.REACT_APP_LIVEKIT_URL || 'ws://localhost:7880';

  useEffect(() => {
    const fetchToken = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        // Fetch token from backend API
        const response = await fetch(`/api/livekit/token`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
          },
          body: JSON.stringify({ roomId }),
        });

        if (!response.ok) {
          throw new Error(`Failed to get LiveKit token: ${response.statusText}`);
        }

        const data = await response.json();
        setToken(data.token);
      } catch (err) {
        console.error('Error fetching LiveKit token:', err);
        setError(err instanceof Error ? err.message : 'Failed to connect to video service');
      } finally {
        setIsLoading(false);
      }
    };

    if (roomId) {
      fetchToken();
    }
  }, [roomId]);

  const handleDisconnected = useCallback(() => {
    console.log('Disconnected from LiveKit room');
    setToken('');
  }, []);

  const handleError = useCallback((error: Error) => {
    console.error('LiveKit error:', error);
    setError(error.message);
  }, []);

  if (isLoading) {
    return (
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="glass-section text-center max-w-md mx-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <h3 className="text-lg font-semibold text-white mb-2">Connecting to video...</h3>
          <p className="text-white/60 text-sm">Please wait while we set up your video connection</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="glass-section text-center max-w-md mx-4">
          <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">Connection Error</h3>
          <p className="text-white/60 text-sm mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="glass-outline-button glass-outline-button--accent"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="glass-section text-center max-w-md mx-4">
          <div className="w-16 h-16 bg-yellow-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">Authentication Required</h3>
          <p className="text-white/60 text-sm">Unable to authenticate with video service</p>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 bg-black/10">
      <LiveKitRoom
        video={true}
        audio={true}
        token={token}
        serverUrl={serverUrl}
        data-lk-theme="default"
        style={{ height: '100%' }}
        onDisconnected={handleDisconnected}
        onError={handleError}
        className="lk-video-conference-custom"
      >
        {/* Main video conference component */}
        <VideoConference 
          chatMessageFormatter={undefined}
          SettingsComponent={undefined}
        />
        
        {/* Audio renderer for participants */}
        <RoomAudioRenderer />
      </LiveKitRoom>
    </div>
  );
});

VideoGrid.displayName = 'VideoGrid';

export default VideoGrid;