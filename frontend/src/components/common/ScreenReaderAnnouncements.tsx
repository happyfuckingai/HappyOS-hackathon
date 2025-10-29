import React, { useEffect, useState } from 'react';

interface AnnouncementProps {
  message: string;
  priority: 'polite' | 'assertive';
  clearAfter?: number;
}

export const ScreenReaderAnnouncement: React.FC<AnnouncementProps> = ({
  message,
  priority = 'polite',
  clearAfter = 5000,
}) => {
  const [currentMessage, setCurrentMessage] = useState(message);

  useEffect(() => {
    setCurrentMessage(message);
    
    if (clearAfter > 0) {
      const timer = setTimeout(() => {
        setCurrentMessage('');
      }, clearAfter);
      
      return () => clearTimeout(timer);
    }
  }, [message, clearAfter]);

  if (!currentMessage) return null;

  return (
    <div
      aria-live={priority}
      aria-atomic="true"
      className="sr-only"
      role="status"
    >
      {currentMessage}
    </div>
  );
};

// Hook for managing screen reader announcements
export const useScreenReaderAnnouncements = () => {
  const [announcements, setAnnouncements] = useState<Array<{
    id: string;
    message: string;
    priority: 'polite' | 'assertive';
    timestamp: number;
  }>>([]);

  const announce = (message: string, priority: 'polite' | 'assertive' = 'polite') => {
    const id = `announcement-${Date.now()}-${Math.random()}`;
    const announcement = {
      id,
      message,
      priority,
      timestamp: Date.now(),
    };

    setAnnouncements(prev => [...prev, announcement]);

    // Remove announcement after 5 seconds
    setTimeout(() => {
      setAnnouncements(prev => prev.filter(a => a.id !== id));
    }, 5000);
  };

  const clearAnnouncements = () => {
    setAnnouncements([]);
  };

  return {
    announcements,
    announce,
    clearAnnouncements,
  };
};

// Component to render all active announcements
export const ScreenReaderAnnouncementContainer: React.FC = () => {
  const { announcements } = useScreenReaderAnnouncements();

  return (
    <div className="sr-only" aria-live="polite" aria-atomic="false">
      {announcements.map(announcement => (
        <div key={announcement.id} aria-live={announcement.priority}>
          {announcement.message}
        </div>
      ))}
    </div>
  );
};