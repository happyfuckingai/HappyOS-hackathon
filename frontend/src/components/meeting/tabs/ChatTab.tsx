import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MoreVertical, Wifi, WifiOff } from 'lucide-react';
import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';
import { useSSE } from '../../../contexts/SSEContext';
import { useWebSocket } from '../../../contexts/WebSocketContext';
import { useAuth } from '../../../contexts/AuthContext';

interface ChatTabProps {
  roomId: string;
}

interface ChatMessage {
  id: string;
  type: 'user' | 'ai' | 'system';
  sender: string;
  content: string;
  timestamp: Date;
  isTyping?: boolean;
}

const ChatTab: React.FC<ChatTabProps> = ({ roomId }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'system',
      sender: 'System',
      content: 'Welcome to the meeting chat. AI assistant is ready to help with notes and actions.',
      timestamp: new Date(),
    }
  ]);
  const [newMessage, setNewMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  const { events } = useSSE();
  const { user } = useAuth();
  const { 
    isConnected: wsConnected, 
    lastMessage, 
    sendChatMessage, 
    sendTypingIndicator, 
    connect: connectWs,
    connectionError: wsError 
  } = useWebSocket();

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Connect to WebSocket when component mounts
  useEffect(() => {
    if (roomId && !wsConnected && connectWs) {
      connectWs(roomId);
    }
  }, [roomId, wsConnected, connectWs]);

  // Handle WebSocket messages for real-time chat
  useEffect(() => {
    if (lastMessage) {
      switch (lastMessage.type) {
        case 'chat':
          const chatMessage: ChatMessage = {
            id: `ws-${Date.now()}-${Math.random()}`,
            type: lastMessage.payload.sender === user?.name ? 'user' : 'user',
            sender: lastMessage.payload.sender || 'Unknown',
            content: lastMessage.payload.content,
            timestamp: new Date(lastMessage.timestamp),
          };
          setMessages(prev => [...prev, chatMessage]);
          break;
          
        case 'typing':
          const { sender, isTyping: userTyping } = lastMessage.payload;
          if (sender !== user?.name) {
            setTypingUsers(prev => {
              if (userTyping) {
                return prev.includes(sender) ? prev : [...prev, sender];
              } else {
                return prev.filter(u => u !== sender);
              }
            });
          }
          break;
          
        case 'user_joined':
          const joinMessage: ChatMessage = {
            id: `join-${Date.now()}`,
            type: 'system',
            sender: 'System',
            content: `${lastMessage.payload.user} joined the chat`,
            timestamp: new Date(lastMessage.timestamp),
          };
          setMessages(prev => [...prev, joinMessage]);
          break;
          
        case 'user_left':
          const leaveMessage: ChatMessage = {
            id: `leave-${Date.now()}`,
            type: 'system',
            sender: 'System',
            content: `${lastMessage.payload.user} left the chat`,
            timestamp: new Date(lastMessage.timestamp),
          };
          setMessages(prev => [...prev, leaveMessage]);
          break;
      }
    }
  }, [lastMessage, user?.name]);

  // Handle SSE events for AI responses
  useEffect(() => {
    const latestEvent = events[events.length - 1];
    if (latestEvent && latestEvent.type === 'agent_response') {
      const aiMessage: ChatMessage = {
        id: Date.now().toString(),
        type: 'ai',
        sender: 'AI Assistant',
        content: latestEvent.message,
        timestamp: new Date(latestEvent.timestamp),
      };
      setMessages(prev => [...prev, aiMessage]);
    }
  }, [events]);

  const handleSendMessage = () => {
    if (!newMessage.trim() || !sendChatMessage) return;

    // Send message via WebSocket
    sendChatMessage(newMessage.trim(), roomId);
    
    // Add message to local state immediately for better UX
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      sender: user?.name || 'You',
      content: newMessage.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    
    setNewMessage('');
    inputRef.current?.focus();
    
    // Stop typing indicator
    if (sendTypingIndicator) {
      sendTypingIndicator(false, roomId);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setNewMessage(e.target.value);
    
    // Handle typing indicators
    if (sendTypingIndicator) {
      if (!isTyping && e.target.value.trim()) {
        setIsTyping(true);
        sendTypingIndicator(true, roomId);
      }
      
      // Clear existing timeout
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      
      // Set new timeout to stop typing indicator
      typingTimeoutRef.current = setTimeout(() => {
        setIsTyping(false);
        sendTypingIndicator(false, roomId);
      }, 1000);
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getMessageIcon = (type: ChatMessage['type']) => {
    switch (type) {
      case 'ai':
        return <Bot className="w-4 h-4 text-blue-400" />;
      case 'user':
        return <User className="w-4 h-4 text-green-400" />;
      case 'system':
        return <MoreVertical className="w-4 h-4 text-yellow-400" />;
      default:
        return <User className="w-4 h-4 text-white/60" />;
    }
  };

  const getMessageStyles = (type: ChatMessage['type']) => {
    switch (type) {
      case 'ai':
        return 'bg-blue-500/20 border-blue-500/30';
      case 'user':
        return 'bg-green-500/20 border-green-500/30 ml-8';
      case 'system':
        return 'bg-yellow-500/20 border-yellow-500/30 text-center';
      default:
        return 'bg-white/10 border-white/20';
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Chat Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/10">
        <div className="flex items-center space-x-2">
          <h3 className="text-lg font-semibold text-white">Chat</h3>
          <span className="text-xs text-white/60 bg-white/10 px-2 py-1 rounded-full">
            {messages.filter(m => m.type !== 'system').length} messages
          </span>
        </div>
        
        {/* Connection Status */}
        <div className="flex items-center space-x-4">
          {/* WebSocket Status */}
          <div className="flex items-center space-x-2 text-xs">
            {wsConnected ? (
              <>
                <Wifi className="w-3 h-3 text-green-400" />
                <span className="text-green-300">Connected</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3 h-3 text-red-400" />
                <span className="text-red-300">Disconnected</span>
              </>
            )}
          </div>
          
          {/* AI Status Indicator */}
          <div className="flex items-center space-x-2 text-xs text-white/60">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            <span>AI Assistant Active</span>
          </div>
        </div>
      </div>

      {/* Connection Error */}
      {wsError && (
        <div className="p-3 mb-4 bg-red-500/20 border border-red-500/30 rounded-lg">
          <p className="text-sm text-red-300">Chat connection error: {wsError}</p>
        </div>
      )}

      {/* Messages Area */}
      <ScrollArea className="flex-1 py-4">
        <div className="space-y-4 pr-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`p-3 rounded-lg border backdrop-blur-sm ${getMessageStyles(message.type)}`}
            >
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 mt-0.5">
                  {getMessageIcon(message.type)}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-white/90">
                      {message.sender}
                    </span>
                    <span className="text-xs text-white/50">
                      {formatTime(message.timestamp)}
                    </span>
                  </div>
                  
                  <p className="text-sm text-white/80 whitespace-pre-wrap">
                    {message.content}
                  </p>
                </div>
              </div>
            </div>
          ))}

          {/* Typing Indicators */}
          {typingUsers.length > 0 && (
            <div className="p-3 rounded-lg border bg-white/5 border-white/10">
              <div className="flex items-center space-x-2">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-white/40 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
                <span className="text-sm text-white/60">
                  {typingUsers.join(', ')} {typingUsers.length === 1 ? 'is' : 'are'} typing...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Message Input */}
      <div className="pt-4 border-t border-white/10">
        <div className="flex items-end space-x-2">
          <div className="flex-1">
            <input
              ref={inputRef}
              type="text"
              value={newMessage}
              onChange={handleInputChange}
              onKeyPress={handleKeyPress}
              placeholder="Type a message or ask the AI assistant..."
              className="w-full p-3 rounded-lg bg-white/10 border border-white/20 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent resize-none"
              maxLength={500}
            />
            
            {/* Character Counter */}
            <div className="flex justify-between items-center mt-1 px-1">
              <span className="text-xs text-white/40">
                Press Enter to send, Shift+Enter for new line
              </span>
              <span className="text-xs text-white/40">
                {newMessage.length}/500
              </span>
            </div>
          </div>
          
          <Button
            onClick={handleSendMessage}
            disabled={!newMessage.trim() || !wsConnected}
            className="h-12 w-12 rounded-lg bg-orange-500 hover:bg-orange-600 disabled:bg-white/10 disabled:text-white/40 flex items-center justify-center"
            title={!wsConnected ? 'Chat disconnected' : 'Send message'}
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>
      </div>

      {/* AI Integration Hint */}
      <div className="mt-2 p-2 rounded-md bg-blue-500/10 border border-blue-500/20">
        <p className="text-xs text-blue-300 text-center">
          💡 Ask the AI to take notes, create action items, or summarize the discussion
        </p>
      </div>
    </div>
  );
};

export default ChatTab;