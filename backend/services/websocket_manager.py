"""
WebSocket Connection Management for MCP UI Hub

Enhanced WebSocket system with:
- Tenant/session topic routing
- Connection authentication and authorization
- Connection lifecycle management (connect/disconnect/cleanup)
- Topic-based message routing system
- Event broadcasting for resource create/update/delete
- Hydration and initial state loading
- Connection health monitoring and dead connection cleanup

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Callable
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..modules.auth import verify_jwt_token
from ..modules.models.ui_resource import UIResource
from ..services.observability import get_logger

logger = get_logger(__name__)


class WebSocketConnection(BaseModel):
    """WebSocket connection metadata"""
    connection_id: str
    websocket: WebSocket
    tenant_id: str
    session_id: str
    topic: str
    authenticated: bool = False
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    connected_at: str
    last_ping: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class WebSocketEvent(BaseModel):
    """WebSocket event structure"""
    type: str  # create, update, delete, hydration, heartbeat, ping, pong
    tenant_id: str
    session_id: str
    resource_id: Optional[str] = None
    agent_id: Optional[str] = None
    resource: Optional[Dict[str, Any]] = None
    old_resource: Optional[Dict[str, Any]] = None
    resources: Optional[List[Dict[str, Any]]] = None  # For hydration
    timestamp: str
    connection_id: Optional[str] = None
    message: Optional[str] = None


class TopicManager:
    """Manages WebSocket topic subscriptions and routing"""
    
    def __init__(self):
        # topic -> set of connection_ids
        self.topic_subscriptions: Dict[str, Set[str]] = {}
        # connection_id -> set of topics
        self.connection_topics: Dict[str, Set[str]] = {}
    
    def subscribe(self, connection_id: str, topic: str) -> None:
        """Subscribe connection to a topic"""
        if topic not in self.topic_subscriptions:
            self.topic_subscriptions[topic] = set()
        self.topic_subscriptions[topic].add(connection_id)
        
        if connection_id not in self.connection_topics:
            self.connection_topics[connection_id] = set()
        self.connection_topics[connection_id].add(topic)
        
        logger.debug(f"Connection {connection_id} subscribed to topic {topic}")
    
    def unsubscribe(self, connection_id: str, topic: str) -> None:
        """Unsubscribe connection from a topic"""
        if topic in self.topic_subscriptions:
            self.topic_subscriptions[topic].discard(connection_id)
            if not self.topic_subscriptions[topic]:
                del self.topic_subscriptions[topic]
        
        if connection_id in self.connection_topics:
            self.connection_topics[connection_id].discard(topic)
            if not self.connection_topics[connection_id]:
                del self.connection_topics[connection_id]
        
        logger.debug(f"Connection {connection_id} unsubscribed from topic {topic}")
    
    def unsubscribe_all(self, connection_id: str) -> None:
        """Unsubscribe connection from all topics"""
        if connection_id not in self.connection_topics:
            return
        
        topics = self.connection_topics[connection_id].copy()
        for topic in topics:
            self.unsubscribe(connection_id, topic)
    
    def get_subscribers(self, topic: str) -> Set[str]:
        """Get all connection IDs subscribed to a topic"""
        return self.topic_subscriptions.get(topic, set()).copy()
    
    def get_topic_pattern_subscribers(self, pattern: str) -> Set[str]:
        """Get subscribers for topic pattern (e.g., ui.tenant.* matches ui.tenant.session1)"""
        subscribers = set()
        
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            for topic in self.topic_subscriptions:
                if topic.startswith(prefix):
                    subscribers.update(self.topic_subscriptions[topic])
        else:
            subscribers = self.get_subscribers(pattern)
        
        return subscribers
    
    def get_tenant_subscribers(self, tenant_id: str) -> Set[str]:
        """Get all subscribers for a specific tenant"""
        pattern = f"ui.{tenant_id}.*"
        return self.get_topic_pattern_subscribers(pattern)
    
    def get_session_subscribers(self, tenant_id: str, session_id: str) -> Set[str]:
        """Get all subscribers for a specific tenant/session"""
        topic = f"ui.{tenant_id}.{session_id}"
        return self.get_subscribers(topic)
    
    def filter_subscribers_by_agent(self, subscribers: Set[str], agent_id: str) -> Set[str]:
        """Filter subscribers by agent ID (if connection has agent restriction)"""
        filtered = set()
        
        for connection_id in subscribers:
            if connection_id in self.connections:
                connection = self.connections[connection_id]
                # If connection has no agent restriction or matches the agent
                if not connection.agent_id or connection.agent_id == agent_id:
                    filtered.add(connection_id)
        
        return filtered


class WebSocketManager:
    """
    Enhanced WebSocket connection manager with tenant isolation and topic routing
    
    Features:
    - Connection authentication and authorization
    - Topic-based message routing
    - Connection lifecycle management
    - Health monitoring and cleanup
    - Event broadcasting
    - Hydration support
    """
    
    def __init__(self, resource_provider: Optional[Callable] = None):
        # connection_id -> WebSocketConnection
        self.connections: Dict[str, WebSocketConnection] = {}
        self.topic_manager = TopicManager()
        self.resource_provider = resource_provider  # Function to get resources for hydration
        
        # Health monitoring
        self.heartbeat_interval = 30  # seconds
        self.connection_timeout = 300  # 5 minutes
        self._cleanup_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start background tasks"""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if not self._heartbeat_task:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        logger.info("WebSocket manager started")
    
    async def stop(self):
        """Stop background tasks and close all connections"""
        # Cancel background tasks
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        
        # Close all connections
        for connection in list(self.connections.values()):
            await self._disconnect_connection(connection.connection_id, code=1001, reason="Server shutdown")
        
        logger.info("WebSocket manager stopped")
    
    def validate_topic_format(self, topic: str) -> tuple[bool, Optional[str]]:
        """
        Validate topic format: ui.{tenantId}.{sessionId}
        
        Returns:
            (is_valid, error_message)
        """
        if not topic.startswith("ui."):
            return False, "Topic must start with 'ui.'"
        
        parts = topic.split(".")
        if len(parts) != 3:
            return False, "Topic must be in format: ui.{tenantId}.{sessionId}"
        
        _, tenant_id, session_id = parts
        
        # Validate tenant_id format
        if not tenant_id or not tenant_id.replace('-', '').isalnum():
            return False, "Invalid tenant ID format"
        
        # Validate session_id format
        if not session_id or not session_id.replace('-', '').replace('_', '').isalnum():
            return False, "Invalid session ID format"
        
        return True, None
    
    def validate_tenant_access(self, jwt_claims: Dict, tenant_id: str, session_id: str) -> bool:
        """Validate JWT scopes for tenant/session access"""
        scopes = jwt_claims.get("scopes", [])
        
        # Check for read access
        required_scopes = [
            f"ui:read:{tenant_id}:{session_id}",
            f"ui:read:{tenant_id}:*",
            f"ui:write:{tenant_id}:{session_id}",
            f"ui:write:{tenant_id}:*"
        ]
        
        return any(scope in scopes for scope in required_scopes)
    
    async def authenticate_connection(self, websocket: WebSocket, token: Optional[str]) -> tuple[bool, Optional[Dict], Optional[str]]:
        """
        Authenticate WebSocket connection using JWT token
        
        Returns:
            (is_authenticated, jwt_claims, error_message)
        """
        if not token:
            return False, None, "Missing authentication token"
        
        try:
            jwt_claims = verify_jwt_token(token)
            return True, jwt_claims, None
        except Exception as e:
            logger.warning(f"WebSocket authentication failed: {e}")
            return False, None, f"Authentication failed: {str(e)}"
    
    async def connect(self, websocket: WebSocket, topic: str, token: Optional[str] = None) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Handle new WebSocket connection with authentication and topic validation
        
        Returns:
            (success, connection_id, error_message)
        """
        # Validate topic format
        is_valid, error_msg = self.validate_topic_format(topic)
        if not is_valid:
            return False, None, error_msg
        
        # Extract tenant and session from topic
        _, tenant_id, session_id = topic.split(".")
        
        # Authenticate connection
        authenticated, jwt_claims, auth_error = await self.authenticate_connection(websocket, token)
        if not authenticated:
            return False, None, auth_error
        
        # Validate tenant access
        if not self.validate_tenant_access(jwt_claims, tenant_id, session_id):
            return False, None, f"Insufficient permissions for tenant {tenant_id}, session {session_id}"
        
        # Create connection
        connection_id = str(uuid4())
        connection = WebSocketConnection(
            connection_id=connection_id,
            websocket=websocket,
            tenant_id=tenant_id,
            session_id=session_id,
            topic=topic,
            authenticated=True,
            user_id=jwt_claims.get("sub"),
            agent_id=jwt_claims.get("agentId"),
            connected_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Store connection
        self.connections[connection_id] = connection
        
        # Subscribe to topic
        self.topic_manager.subscribe(connection_id, topic)
        
        logger.info(f"WebSocket connected: {connection_id} to topic {topic} (tenant: {tenant_id}, session: {session_id})")
        
        # Send hydration data
        await self._send_hydration(connection)
        
        return True, connection_id, None
    
    async def disconnect(self, connection_id: str, code: int = 1000, reason: str = "Normal closure") -> None:
        """Handle WebSocket disconnection"""
        await self._disconnect_connection(connection_id, code, reason)
    
    async def handle_reconnection(self, websocket: WebSocket, topic: str, token: Optional[str] = None, last_connection_id: Optional[str] = None) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Handle WebSocket reconnection with state recovery
        
        Args:
            websocket: New WebSocket connection
            topic: Topic to connect to
            token: Authentication token
            last_connection_id: Previous connection ID for state recovery
            
        Returns:
            (success, new_connection_id, error_message)
        """
        try:
            # First, establish new connection normally
            success, new_connection_id, error_msg = await self.connect(websocket, topic, token)
            
            if not success:
                return False, None, error_msg
            
            # If we have a previous connection ID, attempt recovery
            if last_connection_id:
                try:
                    from .hydration_service import get_hydration_service
                    
                    hydration_service = get_hydration_service()
                    
                    # Attempt to recover missed updates
                    recovery_success = await hydration_service.handle_connection_recovery(new_connection_id, self)
                    
                    if recovery_success:
                        logger.info(f"Successfully recovered connection state from {last_connection_id} to {new_connection_id}")
                    else:
                        logger.info(f"No recovery state found for {last_connection_id}, performed normal hydration for {new_connection_id}")
                    
                except Exception as e:
                    logger.warning(f"Connection recovery failed for {last_connection_id} -> {new_connection_id}: {e}")
                    # Recovery failure is not fatal - connection is still established
            
            return True, new_connection_id, None
            
        except Exception as e:
            logger.error(f"Reconnection failed for topic {topic}: {e}")
            return False, None, str(e)
    
    async def _disconnect_connection(self, connection_id: str, code: int = 1000, reason: str = "Normal closure") -> None:
        """Internal method to disconnect a connection"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        try:
            # Close WebSocket if still open
            if connection.websocket.client_state.name != "DISCONNECTED":
                await connection.websocket.close(code=code, reason=reason)
        except Exception as e:
            logger.warning(f"Error closing WebSocket {connection_id}: {e}")
        
        # Unsubscribe from all topics
        self.topic_manager.unsubscribe_all(connection_id)
        
        # Remove connection
        del self.connections[connection_id]
        
        logger.info(f"WebSocket disconnected: {connection_id} from topic {connection.topic} (reason: {reason})")
    
    async def _send_hydration(self, connection: WebSocketConnection) -> None:
        """Send hydration data (existing resources) to newly connected client"""
        try:
            # Use hydration service if available
            from .hydration_service import get_hydration_service, HydrationRequest
            
            hydration_service = get_hydration_service()
            
            # Create hydration request
            hydration_request = HydrationRequest(
                tenant_id=connection.tenant_id,
                session_id=connection.session_id,
                connection_id=connection.connection_id,
                include_expired=False  # Don't include expired resources by default
            )
            
            # Perform hydration
            response = await hydration_service.hydrate_connection(hydration_request)
            
            # Create hydration event
            event = WebSocketEvent(
                type="hydration",
                tenant_id=connection.tenant_id,
                session_id=connection.session_id,
                resources=response.resources,
                timestamp=response.timestamp,
                connection_id=connection.connection_id,
                message=f"Hydrated {response.filtered_count} resources"
            )
            
            # Send to connection
            await self._send_to_connection(connection.connection_id, event)
            
            logger.info(f"Sent hydration with {response.filtered_count} resources to connection {connection.connection_id}")
            
        except Exception as e:
            logger.warning(f"Hydration service failed for connection {connection.connection_id}, using fallback: {e}")
            
            # Fallback to resource provider if hydration service fails
            await self._send_fallback_hydration(connection)
    
    async def _send_fallback_hydration(self, connection: WebSocketConnection) -> None:
        """Fallback hydration using resource provider"""
        if not self.resource_provider:
            logger.warning("No resource provider configured for hydration")
            return
        
        try:
            # Get existing resources for this tenant/session
            if asyncio.iscoroutinefunction(self.resource_provider):
                resources = await self.resource_provider(connection.tenant_id, connection.session_id)
            else:
                resources = self.resource_provider(connection.tenant_id, connection.session_id)
            
            # Convert resources to dict format
            resource_dicts = []
            for resource in resources:
                try:
                    if hasattr(resource, 'model_dump'):
                        resource_dicts.append(resource.model_dump())
                    elif hasattr(resource, 'dict'):
                        resource_dicts.append(resource.dict())
                    else:
                        resource_dicts.append(resource)
                except Exception as e:
                    logger.warning(f"Failed to serialize resource for hydration: {e}")
            
            # Create hydration event
            event = WebSocketEvent(
                type="hydration",
                tenant_id=connection.tenant_id,
                session_id=connection.session_id,
                resources=resource_dicts,
                timestamp=datetime.now(timezone.utc).isoformat(),
                connection_id=connection.connection_id,
                message=f"Fallback hydration with {len(resource_dicts)} resources"
            )
            
            # Send to connection
            await self._send_to_connection(connection.connection_id, event)
            
            logger.info(f"Sent fallback hydration with {len(resource_dicts)} resources to connection {connection.connection_id}")
            
        except Exception as e:
            logger.error(f"Failed to send fallback hydration to connection {connection.connection_id}: {e}")
    
    async def broadcast_event(self, event: WebSocketEvent) -> int:
        """
        Broadcast event to all subscribers of the relevant topic
        
        Returns:
            Number of connections the event was sent to
        """
        topic = f"ui.{event.tenant_id}.{event.session_id}"
        subscribers = self.topic_manager.get_subscribers(topic)
        
        sent_count = 0
        failed_connections = []
        
        for connection_id in subscribers:
            try:
                await self._send_to_connection(connection_id, event)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send event to connection {connection_id}: {e}")
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self._disconnect_connection(connection_id, code=1011, reason="Send failed")
        
        if sent_count > 0:
            logger.debug(f"Broadcasted {event.type} event to {sent_count} connections on topic {topic}")
        
        return sent_count
    
    async def _send_to_connection(self, connection_id: str, event: WebSocketEvent) -> None:
        """Send event to a specific connection"""
        if connection_id not in self.connections:
            raise ValueError(f"Connection {connection_id} not found")
        
        connection = self.connections[connection_id]
        
        try:
            message = event.model_dump_json()
            await connection.websocket.send_text(message)
        except Exception as e:
            # Connection is likely dead, will be cleaned up by caller
            raise e
    
    async def handle_client_message(self, connection_id: str, message: str) -> None:
        """Handle incoming message from client"""
        if connection_id not in self.connections:
            logger.warning(f"Received message from unknown connection: {connection_id}")
            return
        
        connection = self.connections[connection_id]
        
        try:
            # Try to parse as JSON
            data = json.loads(message)
            message_type = data.get("type", "unknown")
            
            if message_type == "ping":
                # Respond with pong
                pong_event = WebSocketEvent(
                    type="pong",
                    tenant_id=connection.tenant_id,
                    session_id=connection.session_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    connection_id=connection_id,
                    message=data.get("message", "pong")
                )
                await self._send_to_connection(connection_id, pong_event)
                
                # Update last ping time
                connection.last_ping = datetime.now(timezone.utc).isoformat()
                
            elif message_type == "heartbeat":
                # Update connection heartbeat
                connection.last_ping = datetime.now(timezone.utc).isoformat()
                
            else:
                # Echo back unknown messages
                echo_event = WebSocketEvent(
                    type="echo",
                    tenant_id=connection.tenant_id,
                    session_id=connection.session_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    connection_id=connection_id,
                    message=f"echo: {message}"
                )
                await self._send_to_connection(connection_id, echo_event)
                
        except json.JSONDecodeError:
            # Handle plain text messages
            echo_event = WebSocketEvent(
                type="echo",
                tenant_id=connection.tenant_id,
                session_id=connection.session_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                connection_id=connection_id,
                message=f"echo: {message}"
            )
            await self._send_to_connection(connection_id, echo_event)
        
        except Exception as e:
            logger.error(f"Error handling client message from {connection_id}: {e}")
    
    async def _cleanup_loop(self):
        """Background task to clean up dead connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_dead_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _heartbeat_loop(self):
        """Background task to send heartbeats"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    async def _cleanup_dead_connections(self):
        """Clean up connections that are no longer responsive"""
        now = datetime.now(timezone.utc)
        dead_connections = []
        
        for connection_id, connection in self.connections.items():
            try:
                # Check if WebSocket is still connected
                if hasattr(connection.websocket, 'client_state') and connection.websocket.client_state.name == "DISCONNECTED":
                    dead_connections.append(connection_id)
                    continue
                
                # Check for timeout (no ping in connection_timeout seconds)
                if connection.last_ping:
                    last_ping_dt = datetime.fromisoformat(connection.last_ping.replace('Z', '+00:00'))
                    if (now - last_ping_dt).total_seconds() > self.connection_timeout:
                        dead_connections.append(connection_id)
                        continue
                else:
                    # No ping recorded, check connection age
                    connected_dt = datetime.fromisoformat(connection.connected_at.replace('Z', '+00:00'))
                    if (now - connected_dt).total_seconds() > self.connection_timeout:
                        dead_connections.append(connection_id)
                        continue
                
            except Exception as e:
                logger.warning(f"Error checking connection {connection_id}: {e}")
                dead_connections.append(connection_id)
        
        # Clean up dead connections
        for connection_id in dead_connections:
            await self._disconnect_connection(connection_id, code=1001, reason="Connection timeout")
        
        if dead_connections:
            logger.info(f"Cleaned up {len(dead_connections)} dead WebSocket connections")
    
    async def _send_heartbeats(self):
        """Send heartbeat to all connections"""
        heartbeat_event_template = {
            "type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        failed_connections = []
        sent_count = 0
        
        for connection_id, connection in self.connections.items():
            try:
                heartbeat_event = WebSocketEvent(
                    **heartbeat_event_template,
                    tenant_id=connection.tenant_id,
                    session_id=connection.session_id,
                    connection_id=connection_id
                )
                
                await self._send_to_connection(connection_id, heartbeat_event)
                sent_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to send heartbeat to connection {connection_id}: {e}")
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self._disconnect_connection(connection_id, code=1011, reason="Heartbeat failed")
        
        if sent_count > 0:
            logger.debug(f"Sent heartbeat to {sent_count} WebSocket connections")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        stats = {
            "total_connections": len(self.connections),
            "total_topics": len(self.topic_manager.topic_subscriptions),
            "connections_by_tenant": {},
            "connections_by_topic": {},
            "authenticated_connections": 0
        }
        
        for connection in self.connections.values():
            # Count by tenant
            tenant = connection.tenant_id
            if tenant not in stats["connections_by_tenant"]:
                stats["connections_by_tenant"][tenant] = 0
            stats["connections_by_tenant"][tenant] += 1
            
            # Count by topic
            topic = connection.topic
            if topic not in stats["connections_by_topic"]:
                stats["connections_by_topic"][topic] = 0
            stats["connections_by_topic"][topic] += 1
            
            # Count authenticated
            if connection.authenticated:
                stats["authenticated_connections"] += 1
        
        return stats


# Global WebSocket manager instance
websocket_manager = WebSocketManager()