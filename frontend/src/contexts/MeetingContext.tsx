import React, { createContext, useContext, useState, ReactNode, useMemo, useCallback } from 'react';
import { MeetingContextType, Participant } from '../types';
import { meetingApi } from '../lib/api';

const MeetingContext = createContext<MeetingContextType | undefined>(undefined);

export const useMeeting = () => {
  const context = useContext(MeetingContext);
  if (context === undefined) {
    throw new Error('useMeeting must be used within a MeetingProvider');
  }
  return context;
};

interface MeetingProviderProps {
  children: ReactNode;
}

export const MeetingProvider: React.FC<MeetingProviderProps> = ({ children }) => {
  const [roomId, setRoomId] = useState<string | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  const createMeeting = useCallback(async (title?: string): Promise<string> => {
    try {
      const response = await meetingApi.createMeeting(title);
      return response.roomId;
    } catch (error) {
      throw error;
    }
  }, []);

  const joinMeeting = useCallback(async (newRoomId: string): Promise<void> => {
    try {
      setIsConnected(false);
      const response = await meetingApi.joinMeeting(newRoomId);
      setRoomId(newRoomId);
      setParticipants(response.participants || []);
      setIsConnected(true);
    } catch (error) {
      setIsConnected(false);
      throw error;
    }
  }, []);

  const leaveMeeting = useCallback(async (): Promise<void> => {
    try {
      if (roomId) {
        await meetingApi.leaveMeeting(roomId);
      }
    } catch (error) {
      console.error('Leave meeting API call failed:', error);
    } finally {
      setRoomId(null);
      setParticipants([]);
      setIsConnected(false);
    }
  }, [roomId]);

  const value: MeetingContextType = useMemo(() => ({
    roomId,
    participants,
    isConnected,
    joinMeeting,
    leaveMeeting,
    createMeeting,
  }), [roomId, participants, isConnected, joinMeeting, leaveMeeting, createMeeting]);

  return (
    <MeetingContext.Provider value={value}>
      {children}
    </MeetingContext.Provider>
  );
};