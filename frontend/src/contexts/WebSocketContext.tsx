import React, { createContext, useContext, useState, useEffect, ReactNode, useRef, useCallback } from 'react';
import { WebSocketContextType, WebSocketMessage } from '../types';

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const useWebSocket = () => {
    const context = useContext(WebSocketContext);
    if (context === undefined) {
        throw new Error('useWebSocket must be used within a WebSocketProvider');
    }
    return context;
};

interface WebSocketProviderProps {
    children: ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
    const [connectionError, setConnectionError] = useState<string | null>(null);
    const [isReconnecting, setIsReconnecting] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const currentRoomIdRef = useRef<string | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const reconnectAttemptsRef = useRef(0);
    const messageQueueRef = useRef<WebSocketMessage[]>([]);

    const maxReconnectAttempts = 5;
    const baseReconnectDelay = 1000; // 1 second

    const clearReconnectTimeout = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
    }, []);

    const getReconnectDelay = useCallback(() => {
        // Exponential backoff with jitter
        const delay = Math.min(
            baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current),
            30000 // Max 30 seconds
        );
        return delay + Math.random() * 1000; // Add jitter
    }, []);

    const processMessageQueue = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN && messageQueueRef.current.length > 0) {
            const queue = [...messageQueueRef.current];
            messageQueueRef.current = [];

            queue.forEach(message => {
                try {
                    wsRef.current?.send(JSON.stringify(message));
                } catch (error) {
                    console.error('Failed to send queued message:', error);
                    // Re-queue the message
                    messageQueueRef.current.push(message);
                }
            });
        }
    }, []);

    const handleMessage = useCallback((event: MessageEvent) => {
        try {
            const message: WebSocketMessage = JSON.parse(event.data);
            setLastMessage(message);

            // Handle different message types
            switch (message.type) {
                case 'chat':
                    // Chat messages are handled by components listening to lastMessage
                    break;
                case 'typing':
                    // Typing indicators
                    break;
                case 'user_joined':
                case 'user_left':
                    // User presence updates
                    break;
                case 'error':
                    console.error('WebSocket error message:', message.payload);
                    setConnectionError(message.payload.error || 'Unknown error');
                    break;
                default:
                    console.log('Unknown WebSocket message type:', message.type);
            }
        } catch (error) {
            console.error('Failed to parse WebSocket message:', error, event.data);
        }
    }, []);

    const disconnect = useCallback(() => {
        clearReconnectTimeout();

        if (wsRef.current) {
            // Send leave room message before closing
            if (wsRef.current.readyState === WebSocket.OPEN && currentRoomIdRef.current) {
                const leaveMessage: WebSocketMessage = {
                    type: 'leave_room',
                    payload: { roomId: currentRoomIdRef.current },
                    timestamp: new Date().toISOString(),
                };
                wsRef.current.send(JSON.stringify(leaveMessage));
            }

            wsRef.current.close(1000, 'Client disconnect');
            wsRef.current = null;
        }

        setIsConnected(false);
        setIsReconnecting(false);
        setConnectionError(null);
        setLastMessage(null);
        currentRoomIdRef.current = null;
        reconnectAttemptsRef.current = 0;
        messageQueueRef.current = [];
    }, [clearReconnectTimeout]);

    const connect = useCallback((roomId: string) => {
        // Close existing connection
        disconnect();

        currentRoomIdRef.current = roomId;
        setConnectionError(null);
        setIsReconnecting(reconnectAttemptsRef.current > 0);

        try {
            const baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
            const wsUrl = baseUrl.replace(/^http/, 'ws');
            const token = localStorage.getItem('auth_token');

            // Create WebSocket connection with authentication
            const wsEndpoint = `${wsUrl}/ws/chat/${roomId}${token ? `?token=${token}` : ''}`;
            const ws = new WebSocket(wsEndpoint);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log('WebSocket connected for room:', roomId);
                setIsConnected(true);
                setConnectionError(null);
                setIsReconnecting(false);
                reconnectAttemptsRef.current = 0;

                // Process any queued messages
                processMessageQueue();

                // Send join room message
                const joinMessage: WebSocketMessage = {
                    type: 'join_room',
                    payload: { roomId },
                    timestamp: new Date().toISOString(),
                };
                ws.send(JSON.stringify(joinMessage));
            };

            ws.onmessage = handleMessage;

            ws.onclose = (event) => {
                console.log('WebSocket closed:', event.code, event.reason);
                setIsConnected(false);

                // Only attempt to reconnect if it wasn't a clean close
                if (event.code !== 1000 && currentRoomIdRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
                    reconnectAttemptsRef.current++;
                    const delay = getReconnectDelay();

                    console.log(`Attempting to reconnect WebSocket in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
                    setIsReconnecting(true);

                    reconnectTimeoutRef.current = setTimeout(() => {
                        if (currentRoomIdRef.current) {
                            connect(currentRoomIdRef.current);
                        }
                    }, delay);
                } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
                    setConnectionError('Max reconnection attempts reached');
                    setIsReconnecting(false);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                setConnectionError('WebSocket connection error');
            };

        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            setConnectionError('Failed to establish WebSocket connection');
            setIsConnected(false);
        }
    }, [handleMessage, getReconnectDelay, processMessageQueue, disconnect]);

    const sendMessage = useCallback((message: WebSocketMessage) => {
        if (!wsRef.current) {
            console.error('WebSocket not connected');
            return;
        }

        // Add timestamp if not present
        const messageWithTimestamp = {
            ...message,
            timestamp: message.timestamp || new Date().toISOString(),
        };

        if (wsRef.current.readyState === WebSocket.OPEN) {
            try {
                wsRef.current.send(JSON.stringify(messageWithTimestamp));
            } catch (error) {
                console.error('Failed to send WebSocket message:', error);
                // Queue the message for retry
                messageQueueRef.current.push(messageWithTimestamp);
            }
        } else {
            // Queue the message if not connected
            messageQueueRef.current.push(messageWithTimestamp);
            console.log('WebSocket not ready, message queued');
        }
    }, []);

    const sendChatMessage = useCallback((content: string, roomId: string) => {
        const message: WebSocketMessage = {
            type: 'chat',
            payload: {
                content,
                roomId,
                sender: 'current_user', // TODO: Get from auth context
            },
            timestamp: new Date().toISOString(),
        };
        sendMessage(message);
    }, [sendMessage]);

    const sendTypingIndicator = useCallback((isTyping: boolean, roomId: string) => {
        const message: WebSocketMessage = {
            type: 'typing',
            payload: {
                isTyping,
                roomId,
                sender: 'current_user', // TODO: Get from auth context
            },
            timestamp: new Date().toISOString(),
        };
        sendMessage(message);
    }, [sendMessage]);

    const retry = useCallback(() => {
        if (currentRoomIdRef.current) {
            reconnectAttemptsRef.current = 0;
            connect(currentRoomIdRef.current);
        }
    }, [connect]);

    useEffect(() => {
        return () => {
            disconnect();
        };
    }, [disconnect]);

    const value: WebSocketContextType = {
        isConnected,
        sendMessage,
        lastMessage,
        // Extended interface for better UX
        connectionError,
        isReconnecting,
        connect,
        disconnect,
        sendChatMessage,
        sendTypingIndicator,
        retry,
    };

    return (
        <WebSocketContext.Provider value={value}>
            {children}
        </WebSocketContext.Provider>
    );
};