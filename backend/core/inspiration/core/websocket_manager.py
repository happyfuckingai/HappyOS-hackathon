"""
WebSocket manager for HappyOS.

This module provides functionality to manage WebSocket connections
and send messages to connected clients.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Set, Optional, Callable
import uuid

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Manages WebSocket connections and message distribution.
    
    This class handles:
    - Connection management
    - Message broadcasting
    - User-specific messaging
    - Window object distribution
    """
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        self.connections: Dict[str, Dict[str, Any]] = {}  # connection_id -> connection_info
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self.message_handlers: Dict[str, Callable] = {}  # message_type -> handler
    
    def register_connection(self, connection_id: str, websocket: Any, user_id: Optional[str] = None) -> None:
        """
        Register a new WebSocket connection.
        
        Args:
            connection_id: Unique ID for the connection
            websocket: WebSocket connection object
            user_id: Optional user ID associated with the connection
        """
        self.connections[connection_id] = {
            "websocket": websocket,
            "user_id": user_id,
            "connected_at": asyncio.get_event_loop().time()
        }
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
        
        logger.info(f"Registered WebSocket connection: {connection_id} (User: {user_id})")
    
    def unregister_connection(self, connection_id: str) -> None:
        """
        Unregister a WebSocket connection.
        
        Args:
            connection_id: Connection ID to unregister
        """
        if connection_id in self.connections:
            user_id = self.connections[connection_id].get("user_id")
            
            # Remove from user connections
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            
            # Remove connection
            del self.connections[connection_id]
            
            logger.info(f"Unregistered WebSocket connection: {connection_id} (User: {user_id})")
    
    def register_message_handler(self, message_type: str, handler: Callable) -> None:
        """
        Register a handler for a specific message type.
        
        Args:
            message_type: Type of message to handle
            handler: Handler function
        """
        self.message_handlers[message_type] = handler
        logger.info(f"Registered message handler for type: {message_type}")
    
    async def handle_message(self, connection_id: str, message: Dict[str, Any]) -> None:
        """
        Handle an incoming message.
        
        Args:
            connection_id: Connection ID that sent the message
            message: Message content
        """
        message_type = message.get("type")
        
        if message_type in self.message_handlers:
            try:
                # Add connection info to message
                connection_info = self.connections.get(connection_id, {})
                message["connection_id"] = connection_id
                message["user_id"] = connection_info.get("user_id")
                
                # Call handler
                await self.message_handlers[message_type](message)
            except Exception as e:
                logger.error(f"Error handling message of type {message_type}: {str(e)}")
        else:
            logger.warning(f"No handler registered for message type: {message_type}")
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: Message to broadcast
        """
        serialized_message = json.dumps(message)
        
        for connection_id, connection_info in list(self.connections.items()):
            try:
                websocket = connection_info.get("websocket")
                if websocket and not websocket.closed:
                    await websocket.send(serialized_message)
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_id}: {str(e)}")
                # Connection might be dead, unregister it
                self.unregister_connection(connection_id)
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific user (all their connections).
        
        Args:
            user_id: User ID to send to
            message: Message to send
            
        Returns:
            True if message was sent to at least one connection, False otherwise
        """
        if user_id not in self.user_connections:
            logger.warning(f"No connections found for user: {user_id}")
            return False
        
        serialized_message = json.dumps(message)
        sent_to_any = False
        
        for connection_id in list(self.user_connections.get(user_id, set())):
            try:
                connection_info = self.connections.get(connection_id)
                if not connection_info:
                    continue
                
                websocket = connection_info.get("websocket")
                if websocket and not websocket.closed:
                    await websocket.send(serialized_message)
                    sent_to_any = True
            except Exception as e:
                logger.error(f"Error sending to connection {connection_id}: {str(e)}")
                # Connection might be dead, unregister it
                self.unregister_connection(connection_id)
        
        return sent_to_any
    
    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific connection.
        
        Args:
            connection_id: Connection ID to send to
            message: Message to send
            
        Returns:
            True if message was sent, False otherwise
        """
        if connection_id not in self.connections:
            logger.warning(f"Connection not found: {connection_id}")
            return False
        
        try:
            connection_info = self.connections.get(connection_id)
            websocket = connection_info.get("websocket")
            
            if websocket and not websocket.closed:
                serialized_message = json.dumps(message)
                await websocket.send(serialized_message)
                return True
            else:
                logger.warning(f"WebSocket closed for connection: {connection_id}")
                self.unregister_connection(connection_id)
                return False
        except Exception as e:
            logger.error(f"Error sending to connection {connection_id}: {str(e)}")
            self.unregister_connection(connection_id)
            return False
    
    async def send_window(self, window_obj: Dict[str, Any], user_id: Optional[str] = None) -> bool:
        """
        Send a window object to the frontend.
        
        Args:
            window_obj: Window object to send
            user_id: Optional user ID to send to (if None, broadcast to all)
            
        Returns:
            True if message was sent, False otherwise
        """
        message = {
            "type": "window",
            "window": window_obj,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        if user_id:
            return await self.send_to_user(user_id, message)
        else:
            await self.broadcast(message)
            return True
    
    def get_connection_count(self) -> int:
        """
        Get the number of active connections.
        
        Returns:
            Number of active connections
        """
        return len(self.connections)
    
    def get_user_connection_count(self, user_id: str) -> int:
        """
        Get the number of connections for a specific user.
        
        Args:
            user_id: User ID to check
            
        Returns:
            Number of connections for the user
        """
        return len(self.user_connections.get(user_id, set()))
    
    def generate_connection_id(self) -> str:
        """
        Generate a unique connection ID.
        
        Returns:
            Unique connection ID
        """
        return f"conn_{uuid.uuid4().hex[:8]}"


# Singleton instance
websocket_manager = WebSocketManager()