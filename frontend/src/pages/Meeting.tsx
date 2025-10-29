import React, { useEffect, Suspense, lazy } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMeeting } from '../contexts/MeetingContext';
import { useSSE } from '../contexts/SSEContext';

// Lazy load heavy meeting components
const VideoGrid = lazy(() => import('../components/meeting/VideoGrid'));
const SideParticipants = lazy(() => import('../components/meeting/SideParticipants'));
const FabMenu = lazy(() => import('../components/meeting/FabMenu'));

// Component loading fallback
const ComponentLoader: React.FC<{ name: string }> = ({ name }) => (
  <div className="flex items-center justify-center h-full">
    <div className="glass-section p-4 text-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500 mx-auto mb-2"></div>
      <p className="text-white/60 text-sm">Loading {name}...</p>
    </div>
  </div>
);

const Meeting: React.FC = () => {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const { joinMeeting, leaveMeeting, isConnected } = useMeeting();
  const { connect, disconnect } = useSSE();

  useEffect(() => {
    if (!roomId) {
      navigate('/lobby');
      return;
    }

    // Join meeting and connect to SSE
    const initializeMeeting = async () => {
      try {
        await joinMeeting(roomId);
        connect(roomId);
      } catch (error) {
        console.error('Failed to join meeting:', error);
        navigate('/lobby');
      }
    };

    initializeMeeting();

    // Cleanup on unmount
    return () => {
      leaveMeeting();
      disconnect();
    };
  }, [roomId, joinMeeting, leaveMeeting, connect, disconnect, navigate]);

  // Leave meeting handler will be implemented in FAB menu
  // const handleLeaveMeeting = async () => {
  //   try {
  //     await leaveMeeting();
  //     navigate('/lobby');
  //   } catch (error) {
  //     console.error('Failed to leave meeting:', error);
  //     navigate('/lobby');
  //   }
  // };

  if (!isConnected) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="glass-card p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-white/70">Connecting to meeting...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Meeting Content - Responsive Grid Layout */}
      <div className="flex-1 flex flex-col lg:flex-row min-h-0">
        {/* Video Area - 9/12 on desktop, full width on mobile */}
        <div className="flex-1 lg:w-3/4 relative bg-black/20 min-h-0">
          <Suspense fallback={<ComponentLoader name="Video Grid" />}>
            <VideoGrid roomId={roomId!} />
          </Suspense>
        </div>

        {/* Participants Sidebar - 3/12 on desktop, hidden on mobile (will be accessible via FAB) */}
        <div className="hidden lg:flex lg:w-1/4 lg:min-w-[320px] lg:max-w-[400px] flex-col border-l border-white/10 bg-white/5 backdrop-blur-md">
          <Suspense fallback={<ComponentLoader name="Participants" />}>
            <SideParticipants roomId={roomId!} />
          </Suspense>
        </div>
      </div>

      {/* FAB Menu - Always visible, positioned for mobile and desktop */}
      <Suspense fallback={null}>
        <FabMenu roomId={roomId!} />
      </Suspense>
    </div>
  );
};

export default Meeting;