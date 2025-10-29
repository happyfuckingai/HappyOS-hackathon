"""
Event Broadcasting System for MCP UI Hub

Handles real-time event broadcasting for resource create/update/delete operations
with WebSocket topic filtering by tenant and session, event serialization,
and connection health monitoring.

Requirements: 3.1, 3.2, 3.5
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

from pydantic import BaseModel

from ..modules.models.ui_resource import UIResource
from ..services.observability import get_logger
from .websocket_manager import WebSocketManager, WebSocketEvent

logger = get_logger(__name__)


class EventType(str, Enum):
    """Event types for UI resource operations"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    HYDRATION = "hydration"
    HEARTBEAT = "heartbeat"
    PING = "ping"
    PONG = "pong"
    ECHO = "echo"
    ERROR = "error"


class ResourceEvent(BaseModel):
    """Resource event data structure"""
    event_type: EventType
    resource_id: str
    tenant_id: str
    session_id: str
    agent_id: str
    resource: Optional[UIResource] = None
    old_resource: Optional[UIResource] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str = None
    
    def __init__(self, **data):
        if 'timestamp' not in data or data['timestamp'] is None:
            data['timestamp'] = datetime.now(timezone.utc).isoformat()
        super().__init__(**data)


class EventFilter(BaseModel):
    """Event filtering criteria"""
    tenant_ids: Optional[List[str]] = None
    session_ids: Optional[List[str]] = None
    agent_ids: Optional[List[str]] = None
    event_types: Optional[List[EventType]] = None
    resource_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class EventBroadcaster:
    """
    Event broadcasting system for real-time UI updates
    
    Features:
    - Resource lifecycle event broadcasting (create/update/delete)
    - WebSocket topic filtering by tenant and session
    - Event serialization and message formatting
    - Connection health monitoring integration
    - Event filtering and routing
    - Batch event processing
    """
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.event_filters: List[EventFilter] = []
        
        # Statistics
        self.events_sent = 0
        self.events_failed = 0
        self.events_filtered = 0
        
        # Background processing
        self._processing_task: Optional[asyncio.Task] = None
        self._batch_size = 10
        self._batch_timeout = 0.1  # 100ms
    
    async def start(self):
        """Start event processing"""
        if not self._processing_task:
            self._processing_task = asyncio.create_task(self._process_events())
        logger.info("Event broadcaster started")
    
    async def stop(self):
        """Stop event processing"""
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None
        logger.info("Event broadcaster stopped")
    
    def add_event_handler(self, event_type: EventType, handler: Callable[[ResourceEvent], None]):
        """Add custom event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.debug(f"Added event handler for {event_type}")
    
    def add_event_filter(self, event_filter: EventFilter):
        """Add event filter"""
        self.event_filters.append(event_filter)
        logger.debug(f"Added event filter: {event_filter}")
    
    def _should_filter_event(self, event: ResourceEvent) -> bool:
        """Check if event should be filtered out"""
        if not self.event_filters:
            return False
        
        for filter_criteria in self.event_filters:
            # Check tenant filter
            if filter_criteria.tenant_ids and event.tenant_id not in filter_criteria.tenant_ids:
                continue
            
            # Check session filter
            if filter_criteria.session_ids and event.session_id not in filter_criteria.session_ids:
                continue
            
            # Check agent filter
            if filter_criteria.agent_ids and event.agent_id not in filter_criteria.agent_ids:
                continue
            
            # Check event type filter
            if filter_criteria.event_types and event.event_type not in filter_criteria.event_types:
                continue
            
            # Check resource type filter
            if filter_criteria.resource_types and event.resource:
                if event.resource.type not in filter_criteria.resource_types:
                    continue
            
            # Check tags filter
            if filter_criteria.tags and event.resource:
                if not any(tag in event.resource.tags for tag in filter_criteria.tags):
                    continue
            
            # If we get here, the event matches this filter - don't filter it out
            return False
        
        # If no filters matched, filter out the event
        return len(self.event_filters) > 0
    
    async def broadcast_resource_created(self, resource: UIResource, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Broadcast resource creation event
        
        Returns:
            Number of connections the event was sent to
        """
        event = ResourceEvent(
            event_type=EventType.CREATE,
            resource_id=resource.id,
            tenant_id=resource.tenantId,
            session_id=resource.sessionId,
            agent_id=resource.agentId,
            resource=resource,
            metadata=metadata
        )
        
        return await self._queue_event(event)
    
    async def broadcast_resource_updated(self, resource: UIResource, old_resource: Optional[UIResource] = None, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Broadcast resource update event
        
        Returns:
            Number of connections the event was sent to
        """
        event = ResourceEvent(
            event_type=EventType.UPDATE,
            resource_id=resource.id,
            tenant_id=resource.tenantId,
            session_id=resource.sessionId,
            agent_id=resource.agentId,
            resource=resource,
            old_resource=old_resource,
            metadata=metadata
        )
        
        return await self._queue_event(event)
    
    async def broadcast_resource_deleted(self, resource: UIResource, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Broadcast resource deletion event
        
        Returns:
            Number of connections the event was sent to
        """
        event = ResourceEvent(
            event_type=EventType.DELETE,
            resource_id=resource.id,
            tenant_id=resource.tenantId,
            session_id=resource.sessionId,
            agent_id=resource.agentId,
            resource=resource,
            metadata=metadata
        )
        
        return await self._queue_event(event)
    
    async def broadcast_custom_event(self, event: ResourceEvent) -> int:
        """
        Broadcast custom event
        
        Returns:
            Number of connections the event was sent to
        """
        return await self._queue_event(event)
    
    async def _queue_event(self, event: ResourceEvent) -> int:
        """Queue event for processing"""
        try:
            await self.event_queue.put(event)
            return 1  # Queued successfully
        except Exception as e:
            logger.error(f"Failed to queue event {event.event_type} for resource {event.resource_id}: {e}")
            self.events_failed += 1
            return 0
    
    async def _process_events(self):
        """Background task to process queued events"""
        while True:
            try:
                # Collect batch of events
                events = []
                
                # Wait for first event
                try:
                    event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                    events.append(event)
                except asyncio.TimeoutError:
                    continue
                
                # Collect additional events up to batch size or timeout
                batch_start = asyncio.get_event_loop().time()
                while len(events) < self._batch_size:
                    try:
                        remaining_time = self._batch_timeout - (asyncio.get_event_loop().time() - batch_start)
                        if remaining_time <= 0:
                            break
                        
                        event = await asyncio.wait_for(self.event_queue.get(), timeout=remaining_time)
                        events.append(event)
                    except asyncio.TimeoutError:
                        break
                
                # Process batch
                await self._process_event_batch(events)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
    
    async def _process_event_batch(self, events: List[ResourceEvent]):
        """Process a batch of events"""
        for event in events:
            try:
                await self._process_single_event(event)
            except Exception as e:
                logger.error(f"Failed to process event {event.event_type} for resource {event.resource_id}: {e}")
                self.events_failed += 1
    
    async def _process_single_event(self, event: ResourceEvent):
        """Process a single event"""
        # Check if event should be filtered
        if self._should_filter_event(event):
            self.events_filtered += 1
            logger.debug(f"Filtered out event {event.event_type} for resource {event.resource_id}")
            return
        
        # Run custom event handlers
        if event.event_type in self.event_handlers:
            for handler in self.event_handlers[event.event_type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Event handler failed for {event.event_type}: {e}")
        
        # Convert to WebSocket event and broadcast
        websocket_event = self._convert_to_websocket_event(event)
        sent_count = await self.websocket_manager.broadcast_event(websocket_event)
        
        if sent_count > 0:
            self.events_sent += 1
            logger.debug(f"Broadcasted {event.event_type} event for resource {event.resource_id} to {sent_count} connections")
        else:
            logger.debug(f"No connections to broadcast {event.event_type} event for resource {event.resource_id}")
    
    def _convert_to_websocket_event(self, event: ResourceEvent) -> WebSocketEvent:
        """Convert ResourceEvent to WebSocketEvent with enhanced serialization"""
        websocket_event = WebSocketEvent(
            type=event.event_type.value,
            tenant_id=event.tenant_id,
            session_id=event.session_id,
            resource_id=event.resource_id,
            agent_id=event.agent_id,
            timestamp=event.timestamp
        )
        
        # Add resource data with enhanced serialization
        if event.resource:
            try:
                # Use model_dump if available (Pydantic v2)
                if hasattr(event.resource, 'model_dump'):
                    websocket_event.resource = event.resource.model_dump()
                # Fallback to dict() for Pydantic v1
                elif hasattr(event.resource, 'dict'):
                    websocket_event.resource = event.resource.dict()
                # Fallback to manual conversion
                else:
                    websocket_event.resource = self._serialize_resource(event.resource)
            except Exception as e:
                logger.warning(f"Failed to serialize resource {event.resource_id}: {e}")
                websocket_event.resource = {"error": "serialization_failed", "resource_id": event.resource_id}
        
        if event.old_resource:
            try:
                if hasattr(event.old_resource, 'model_dump'):
                    websocket_event.old_resource = event.old_resource.model_dump()
                elif hasattr(event.old_resource, 'dict'):
                    websocket_event.old_resource = event.old_resource.dict()
                else:
                    websocket_event.old_resource = self._serialize_resource(event.old_resource)
            except Exception as e:
                logger.warning(f"Failed to serialize old resource {event.resource_id}: {e}")
                websocket_event.old_resource = {"error": "serialization_failed", "resource_id": event.resource_id}
        
        # Add metadata with proper formatting
        if event.metadata:
            try:
                # Ensure metadata is JSON serializable
                websocket_event.message = json.dumps(event.metadata, default=str)
            except Exception as e:
                logger.warning(f"Failed to serialize metadata for {event.resource_id}: {e}")
                websocket_event.message = json.dumps({"error": "metadata_serialization_failed"})
        
        return websocket_event
    
    def _serialize_resource(self, resource) -> Dict[str, Any]:
        """Manually serialize a resource object"""
        try:
            # Try to convert common attributes
            serialized = {}
            
            # Common UIResource attributes
            for attr in ['id', 'tenantId', 'sessionId', 'agentId', 'type', 'version', 'revision', 
                        'payload', 'tags', 'ttlSeconds', 'idempotencyKey', 'createdAt', 'updatedAt', 'expiresAt']:
                if hasattr(resource, attr):
                    value = getattr(resource, attr)
                    # Handle nested objects
                    if hasattr(value, 'model_dump'):
                        serialized[attr] = value.model_dump()
                    elif hasattr(value, 'dict'):
                        serialized[attr] = value.dict()
                    else:
                        serialized[attr] = value
            
            return serialized
            
        except Exception as e:
            logger.error(f"Manual resource serialization failed: {e}")
            return {"error": "manual_serialization_failed"}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get broadcasting statistics"""
        return {
            "events_sent": self.events_sent,
            "events_failed": self.events_failed,
            "events_filtered": self.events_filtered,
            "queue_size": self.event_queue.qsize(),
            "active_handlers": sum(len(handlers) for handlers in self.event_handlers.values()),
            "active_filters": len(self.event_filters),
            "websocket_stats": self.websocket_manager.get_connection_stats()
        }
    
    def reset_statistics(self):
        """Reset broadcasting statistics"""
        self.events_sent = 0
        self.events_failed = 0
        self.events_filtered = 0
        logger.info("Event broadcaster statistics reset")


# Utility functions for common event patterns

async def broadcast_batch_updates(broadcaster: EventBroadcaster, updates: List[tuple[UIResource, Optional[UIResource]]]) -> int:
    """
    Broadcast multiple resource updates efficiently
    
    Args:
        broadcaster: EventBroadcaster instance
        updates: List of (new_resource, old_resource) tuples
    
    Returns:
        Total number of events queued
    """
    total_queued = 0
    
    for new_resource, old_resource in updates:
        queued = await broadcaster.broadcast_resource_updated(new_resource, old_resource)
        total_queued += queued
    
    return total_queued


async def broadcast_session_cleanup(broadcaster: EventBroadcaster, tenant_id: str, session_id: str, deleted_resources: List[UIResource]) -> int:
    """
    Broadcast cleanup events for a session
    
    Args:
        broadcaster: EventBroadcaster instance
        tenant_id: Tenant ID
        session_id: Session ID
        deleted_resources: List of deleted resources
    
    Returns:
        Total number of events queued
    """
    total_queued = 0
    
    for resource in deleted_resources:
        queued = await broadcaster.broadcast_resource_deleted(
            resource, 
            metadata={"reason": "session_cleanup", "session_id": session_id}
        )
        total_queued += queued
    
    return total_queued


# Global event broadcaster instance (will be initialized with websocket_manager)
event_broadcaster: Optional[EventBroadcaster] = None


def get_event_broadcaster() -> EventBroadcaster:
    """Get the global event broadcaster instance"""
    global event_broadcaster
    if event_broadcaster is None:
        raise RuntimeError("Event broadcaster not initialized. Call initialize_event_broadcaster() first.")
    return event_broadcaster


def initialize_event_broadcaster(websocket_manager: WebSocketManager) -> EventBroadcaster:
    """Initialize the global event broadcaster"""
    global event_broadcaster
    event_broadcaster = EventBroadcaster(websocket_manager)
    return event_broadcaster