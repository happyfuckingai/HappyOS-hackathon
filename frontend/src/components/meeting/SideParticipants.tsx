import React, { useMemo, useCallback, memo } from 'react';
import { useMeeting } from '../../contexts/MeetingContext';
import { useAuth } from '../../contexts/AuthContext';
import { SideParticipantsProps, Participant } from '../../types';

const SideParticipants: React.FC<SideParticipantsProps> = memo(({ roomId }) => {
  const { participants } = useMeeting();
  const { user } = useAuth();

  // Memoize participant list to prevent unnecessary re-renders
  const sortedParticipants = useMemo(() => {
    return [...participants].sort((a, b) => {
      // Sort by join time, earliest first
      return new Date(a.joinedAt).getTime() - new Date(b.joinedAt).getTime();
    });
  }, [participants]);

  const formatJoinTime = useCallback((joinedAt: string) => {
    const joinTime = new Date(joinedAt);
    const now = new Date();
    const diffMs = now.getTime() - joinTime.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    
    return joinTime.toLocaleDateString();
  }, []);

  const getParticipantInitials = useCallback((name: string) => {
    return name
      .split(' ')
      .map(word => word.charAt(0))
      .join('')
      .toUpperCase()
      .slice(0, 2);
  }, []);

  const getStatusIndicators = useCallback((participant: Participant) => {
    const indicators = [];
    
    // Microphone status
    indicators.push(
      <div
        key="mic"
        className={`w-2 h-2 rounded-full ${
          participant.isMuted ? 'bg-red-400' : 'bg-green-400'
        }`}
        title={participant.isMuted ? 'Microphone muted' : 'Microphone active'}
      />
    );
    
    // Camera status
    indicators.push(
      <div
        key="camera"
        className={`w-2 h-2 rounded-full ${
          participant.isCameraOff ? 'bg-red-400' : 'bg-green-400'
        }`}
        title={participant.isCameraOff ? 'Camera off' : 'Camera on'}
      />
    );
    
    // Hand raised status
    if (participant.isHandRaised) {
      indicators.push(
        <div
          key="hand"
          className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"
          title="Hand raised"
        />
      );
    }
    
    return indicators;
  }, []);

  const ParticipantItem: React.FC<{ participant: Participant; isCurrentUser?: boolean }> = memo(({ 
    participant, 
    isCurrentUser = false 
  }) => (
    <div className="flex items-center space-x-3 p-3 glass-section rounded-lg hover:bg-white/10 transition-colors">
      <div 
        className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
          isCurrentUser ? 'bg-orange-500' : 'bg-blue-500'
        }`}
      >
        <span className="text-white text-sm font-medium">
          {isCurrentUser ? 'You' : getParticipantInitials(participant.name)}
        </span>
      </div>
      
      <div className="flex-1 min-w-0">
        <p className="text-white text-sm font-medium truncate">
          {isCurrentUser ? `${participant.name} (You)` : participant.name}
        </p>
        <p className="text-white/60 text-xs">
          {formatJoinTime(participant.joinedAt)}
        </p>
      </div>
      
      <div className="flex space-x-1 flex-shrink-0">
        {getStatusIndicators(participant)}
      </div>
    </div>
  ));

  ParticipantItem.displayName = 'ParticipantItem';

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-white/10 flex-shrink-0">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Participants</h3>
          <div className="glass-badge">
            <span>{participants.length + 1}</span>
          </div>
        </div>
      </div>
      
      {/* Participants List */}
      <div className="flex-1 overflow-y-auto glass-scroll p-4">
        <div className="space-y-3">
          {/* Current User - Always shown first */}
          <ParticipantItem
            participant={{
              id: user?.id || 'current-user',
              name: user?.name || 'You',
              avatar: user?.avatar,
              isMuted: false, // This would come from LiveKit state
              isCameraOff: false, // This would come from LiveKit state
              isHandRaised: false, // This would come from LiveKit state
              joinedAt: new Date().toISOString(),
            }}
            isCurrentUser={true}
          />
          
          {/* Other Participants */}
          {sortedParticipants.map((participant) => (
            <ParticipantItem
              key={participant.id}
              participant={participant}
            />
          ))}
          
          {/* Empty State */}
          {participants.length === 0 && (
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-white/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <p className="text-white/60 text-sm">Waiting for others to join...</p>
              <p className="text-white/40 text-xs mt-1">Share the meeting link to invite participants</p>
            </div>
          )}
        </div>
      </div>
      
      {/* Footer with meeting info */}
      <div className="p-4 border-t border-white/10 flex-shrink-0">
        <div className="glass-section p-3 text-center">
          <p className="text-white/60 text-xs mb-1">Meeting ID</p>
          <p className="text-white text-sm font-mono">{roomId}</p>
        </div>
      </div>
    </div>
  );
});

SideParticipants.displayName = 'SideParticipants';

export default SideParticipants;