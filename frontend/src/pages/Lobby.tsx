import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMeeting } from '../contexts/MeetingContext';
import { CreateMeetingFormData, JoinMeetingFormData } from '../types';

const Lobby: React.FC = () => {
  const navigate = useNavigate();
  const { createMeeting, joinMeeting } = useMeeting();
  const [isCreating, setIsCreating] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createForm, setCreateForm] = useState<CreateMeetingFormData>({
    title: '',
  });

  const [joinForm, setJoinForm] = useState<JoinMeetingFormData>({
    roomId: '',
  });

  const handleCreateMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    setError(null);

    try {
      const roomId = await createMeeting(createForm.title || undefined);
      navigate(`/meeting/${roomId}`);
    } catch (error: any) {
      setError(error.message || 'Failed to create meeting');
    } finally {
      setIsCreating(false);
    }
  };

  const handleJoinMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsJoining(true);
    setError(null);

    try {
      await joinMeeting(joinForm.roomId);
      navigate(`/meeting/${joinForm.roomId}`);
    } catch (error: any) {
      setError(error.message || 'Failed to join meeting');
    } finally {
      setIsJoining(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-4xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-display font-bold text-white mb-4">
            Ready to Meet?
          </h1>
          <p className="text-xl text-white/70">
            Create a new meeting or join an existing one
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-8 p-4 rounded-lg bg-red-500/20 border border-red-500/30 max-w-md mx-auto">
            <p className="text-red-200 text-center">{error}</p>
          </div>
        )}

        {/* Meeting Cards */}
        <div className="grid md:grid-cols-2 gap-8 max-w-2xl mx-auto">
          {/* Create Meeting Card */}
          <div className="glass-card p-8">
            <div className="text-center mb-6">
              <div className="w-16 h-16 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">Create Meeting</h2>
              <p className="text-white/60 text-sm">Start a new meeting and invite others</p>
            </div>

            <form onSubmit={handleCreateMeeting} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-white/80 mb-2">
                  Meeting Title (Optional)
                </label>
                <input
                  type="text"
                  value={createForm.title}
                  onChange={(e) => setCreateForm({ title: e.target.value })}
                  className="w-full px-4 py-3 glass-input rounded-lg text-white placeholder-white/50"
                  placeholder="Enter meeting title"
                />
              </div>
              <button
                type="submit"
                disabled={isCreating}
                className="w-full py-3 px-4 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
              >
                {isCreating ? 'Creating...' : 'Create Meeting'}
              </button>
            </form>
          </div>

          {/* Join Meeting Card */}
          <div className="glass-card p-8">
            <div className="text-center mb-6">
              <div className="w-16 h-16 bg-blue-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">Join Meeting</h2>
              <p className="text-white/60 text-sm">Enter a meeting ID to join</p>
            </div>

            <form onSubmit={handleJoinMeeting} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-white/80 mb-2">
                  Meeting ID
                </label>
                <input
                  type="text"
                  required
                  value={joinForm.roomId}
                  onChange={(e) => setJoinForm({ roomId: e.target.value })}
                  className="w-full px-4 py-3 glass-input rounded-lg text-white placeholder-white/50"
                  placeholder="Enter meeting ID"
                />
              </div>
              <button
                type="submit"
                disabled={isJoining || !joinForm.roomId.trim()}
                className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
              >
                {isJoining ? 'Joining...' : 'Join Meeting'}
              </button>
            </form>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="text-center mt-12">
          <p className="text-white/60 text-sm mb-4">
            Need help getting started?
          </p>
          <div className="flex justify-center space-x-4">
            <button className="glass-outline-button">
              View Guide
            </button>
            <button className="glass-outline-button">
              Contact Support
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Lobby;