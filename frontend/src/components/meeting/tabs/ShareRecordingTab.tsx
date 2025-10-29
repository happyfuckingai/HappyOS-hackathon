import React, { useState } from 'react';
import { Copy, Share2, Users, UserPlus, Circle, Square, Download, ExternalLink } from 'lucide-react';
import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';

interface ShareRecordingTabProps {
  roomId: string;
}

const ShareRecordingTab: React.FC<ShareRecordingTabProps> = ({ roomId }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [inviteEmail, setInviteEmail] = useState('');
  const [copySuccess, setCopySuccess] = useState(false);

  // Generate meeting link
  const meetingLink = `${window.location.origin}/meeting/${roomId}`;

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(meetingLink);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (error) {
      console.error('Failed to copy link:', error);
    }
  };

  const handleStartRecording = () => {
    setIsRecording(true);
    // TODO: Integrate with backend recording service
    console.log('Starting recording for room:', roomId);
  };

  const handleStopRecording = () => {
    setIsRecording(false);
    // TODO: Stop recording and save
    console.log('Stopping recording for room:', roomId);
  };

  const handleInviteParticipant = () => {
    if (!inviteEmail.trim()) return;
    
    // TODO: Send invitation email
    console.log('Inviting participant:', inviteEmail);
    setInviteEmail('');
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Simulate recording timer
  React.useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isRecording) {
      interval = setInterval(() => {
        setRecordingDuration(prev => prev + 1);
      }, 1000);
    } else {
      setRecordingDuration(0);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  return (
    <ScrollArea className="h-full pr-4">
      <div className="space-y-6">
        {/* Meeting Link Sharing */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Share Meeting</h3>
          
          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-white/5 border border-white/10">
              <label className="text-sm font-medium text-white/80 mb-2 block">Meeting Link</label>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={meetingLink}
                  readOnly
                  className="flex-1 p-2 rounded-md bg-white/10 border border-white/20 text-white text-sm focus:outline-none"
                />
                <Button
                  onClick={handleCopyLink}
                  variant="outline"
                  className={`glass-button hover:bg-white/15 ${
                    copySuccess ? 'bg-green-500/20 border-green-500/60 text-green-400' : 'text-white'
                  }`}
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
              {copySuccess && (
                <p className="text-xs text-green-400 mt-1">Link copied to clipboard!</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Button
                variant="outline"
                className="glass-button text-white hover:bg-white/15 h-12 flex items-center justify-center space-x-2"
                onClick={() => {
                  if (navigator.share) {
                    navigator.share({
                      title: 'Join my meeting',
                      text: 'Join my MeetMind meeting',
                      url: meetingLink,
                    });
                  }
                }}
              >
                <Share2 className="w-5 h-5" />
                <span>Share</span>
              </Button>
              
              <Button
                variant="outline"
                className="glass-button text-white hover:bg-white/15 h-12 flex items-center justify-center space-x-2"
                onClick={() => window.open(meetingLink, '_blank')}
              >
                <ExternalLink className="w-5 h-5" />
                <span>Open</span>
              </Button>
            </div>
          </div>
        </div>    
    {/* Invite Participants */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Invite Participants</h3>
          
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="Enter email address"
                className="flex-1 p-2 rounded-md bg-white/10 border border-white/20 text-white placeholder-white/50 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
              />
              <Button
                onClick={handleInviteParticipant}
                disabled={!inviteEmail.trim()}
                className="bg-orange-500 hover:bg-orange-600 disabled:bg-white/10 disabled:text-white/40"
              >
                <UserPlus className="w-4 h-4" />
              </Button>
            </div>
            
            <p className="text-xs text-white/60">
              Participants will receive an email invitation with the meeting link
            </p>
          </div>
        </div>

        {/* Recording Controls */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Recording</h3>
          
          <div className="space-y-3">
            {!isRecording ? (
              <Button
                onClick={handleStartRecording}
                variant="outline"
                className="w-full glass-button text-white hover:bg-white/15 h-12 flex items-center justify-center space-x-2"
              >
                <Circle className="w-5 h-5 text-red-400" />
                <span>Start Recording</span>
              </Button>
            ) : (
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-red-500/20 border border-red-500/60">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 bg-red-400 rounded-full animate-pulse"></div>
                      <span className="text-red-400 font-medium">Recording</span>
                    </div>
                    <span className="text-red-400 font-mono text-sm">
                      {formatDuration(recordingDuration)}
                    </span>
                  </div>
                </div>
                
                <Button
                  onClick={handleStopRecording}
                  variant="outline"
                  className="w-full bg-red-500/20 border-red-500/60 text-red-400 hover:bg-red-500/30 h-12 flex items-center justify-center space-x-2"
                >
                  <Square className="w-5 h-5" />
                  <span>Stop Recording</span>
                </Button>
              </div>
            )}
            
            <p className="text-xs text-white/60">
              Recordings are automatically saved and can be downloaded after the meeting
            </p>
          </div>
        </div>

        {/* Meeting Info & Stats */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Meeting Info</h3>
          
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-white/5 border border-white/10 text-center">
              <div className="text-2xl font-bold text-white">3</div>
              <div className="text-xs text-white/60">Participants</div>
            </div>
            
            <div className="p-3 rounded-lg bg-white/5 border border-white/10 text-center">
              <div className="text-2xl font-bold text-white">12:34</div>
              <div className="text-xs text-white/60">Duration</div>
            </div>
          </div>
          
          <div className="p-3 rounded-lg bg-white/5 border border-white/10">
            <div className="text-center space-y-1">
              <p className="text-white/60 text-xs">Meeting ID</p>
              <p className="text-white text-sm font-mono">{roomId}</p>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Quick Actions</h3>
          
          <div className="space-y-2">
            <Button
              variant="outline"
              className="w-full glass-button text-white hover:bg-white/15 h-10 flex items-center justify-center space-x-2"
            >
              <Download className="w-4 h-4" />
              <span>Download Meeting Notes</span>
            </Button>
            
            <Button
              variant="outline"
              className="w-full glass-button text-white hover:bg-white/15 h-10 flex items-center justify-center space-x-2"
            >
              <Users className="w-4 h-4" />
              <span>Manage Participants</span>
            </Button>
          </div>
        </div>
      </div>
    </ScrollArea>
  );
};

export default ShareRecordingTab;