"""
Hydration Service for MCP UI Hub

Handles hydration and initial state loading for WebSocket connections:
- Hydration endpoint for existing resources
- Initial state broadcasting on WebSocket connect
- Incremental update handling for new connections
- Connection recovery and state synchronization

Requirements: 3.3
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set
from uuid import uuid4

from pydantic import BaseModel

from ..modules.models.ui_resource import UIResource
from ..services.observability import get_logger
from .websocket_manager import WebSocketManager, WebSocketEvent

logger = get_logger(__name__)


class HydrationRequest(BaseModel):
    """Hydration request parameters"""
    tenant_id: str
    session_id: str
    agent_id: Optional[str] = None
    resource_types: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    include_expired: bool = False
    since_timestamp: Optional[str] = None  # For incremental updates
    connection_id: Optional[str] = None


class HydrationResponse(BaseModel):
    """Hydration response data"""
    tenant_id: str
    session_id: str
    resources: List[Dict[str, Any]]
    total_count: int
    filtered_count: int
    timestamp: str
    is_incremental: bool = False
    since_timestamp: Optional[str] = None


class ConnectionState(BaseModel):
    """Connection state for recovery"""
    connection_id: str
    tenant_id: str
    session_id: str
    last_hydration: str
    last_update: str
    resource_versions: Dict[str, int]  # resource_id -> revision
    subscribed_agents: Set[str] = set()
    
    class Config:
        arbitrary_types_allowed = True


class HydrationService:
    """
    Service for handling WebSocket hydration and state synchronization
    
    Features:
    - Initial state loading for new connections
    - Incremental updates for reconnecting clients
    - Connection state tracking for recovery
    - Resource filtering and optimization
    - Batch hydration for performance
    """
    
    def __init__(self, resource_provider: Callable[[str, str], List[UIResource]]):
        self.resource_provider = resource_provider
        self.connection_states: Dict[str, ConnectionState] = {}
        
        # Configuration
        self.max_resources_per_hydration = 1000
        self.hydration_timeout = 30  # seconds
        self.state_retention_hours = 24
        
        # Statistics
        self.hydrations_performed = 0
        self.incremental_updates = 0
        self.resources_hydrated = 0
        
        # Background cleanup
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start background tasks"""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Hydration service started")
    
    async def stop(self):
        """Stop background tasks"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("Hydration service stopped")
    
    async def hydrate_connection(self, request: HydrationRequest) -> HydrationResponse:
        """
        Perform hydration for a WebSocket connection
        
        Args:
            request: Hydration request parameters
            
        Returns:
            HydrationResponse with resources and metadata
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Get resources from provider
            all_resources = await self._get_resources(request.tenant_id, request.session_id)
            
            # Apply filters
            filtered_resources = self._apply_filters(all_resources, request)
            
            # Handle incremental updates
            if request.since_timestamp:
                filtered_resources = self._filter_by_timestamp(filtered_resources, request.since_timestamp)
            
            # Limit resources
            if len(filtered_resources) > self.max_resources_per_hydration:
                logger.warning(f"Hydration for {request.tenant_id}/{request.session_id} has {len(filtered_resources)} resources, limiting to {self.max_resources_per_hydration}")
                filtered_resources = filtered_resources[:self.max_resources_per_hydration]
            
            # Convert to dict format
            resource_dicts = [
                resource.model_dump() if hasattr(resource, 'model_dump') else resource 
                for resource in filtered_resources
            ]
            
            # Update connection state
            if request.connection_id:
                await self._update_connection_state(request.connection_id, request, filtered_resources)
            
            # Create response
            response = HydrationResponse(
                tenant_id=request.tenant_id,
                session_id=request.session_id,
                resources=resource_dicts,
                total_count=len(all_resources),
                filtered_count=len(filtered_resources),
                timestamp=datetime.now(timezone.utc).isoformat(),
                is_incremental=bool(request.since_timestamp),
                since_timestamp=request.since_timestamp
            )
            
            # Update statistics
            self.hydrations_performed += 1
            self.resources_hydrated += len(filtered_resources)
            if request.since_timestamp:
                self.incremental_updates += 1
            
            duration = asyncio.get_event_loop().time() - start_time
            logger.info(f"Hydrated {len(filtered_resources)} resources for {request.tenant_id}/{request.session_id} in {duration:.3f}s")
            
            return response
            
        except Exception as e:
            logger.error(f"Hydration failed for {request.tenant_id}/{request.session_id}: {e}")
            raise
    
    async def _get_resources(self, tenant_id: str, session_id: str) -> List[UIResource]:
        """Get resources from the provider"""
        try:
            if asyncio.iscoroutinefunction(self.resource_provider):
                return await self.resource_provider(tenant_id, session_id)
            else:
                return self.resource_provider(tenant_id, session_id)
        except Exception as e:
            logger.error(f"Resource provider failed for {tenant_id}/{session_id}: {e}")
            return []
    
    def _apply_filters(self, resources: List[UIResource], request: HydrationRequest) -> List[UIResource]:
        """Apply filters to resources"""
        filtered = resources
        
        # Filter by agent
        if request.agent_id:
            filtered = [r for r in filtered if r.agentId == request.agent_id]
        
        # Filter by resource types
        if request.resource_types:
            filtered = [r for r in filtered if r.type in request.resource_types]
        
        # Filter by tags
        if request.tags:
            filtered = [r for r in filtered if any(tag in r.tags for tag in request.tags)]
        
        # Filter expired resources
        if not request.include_expired:
            filtered = [r for r in filtered if not r.is_expired()]
        
        return filtered
    
    def _filter_by_timestamp(self, resources: List[UIResource], since_timestamp: str) -> List[UIResource]:
        """Filter resources updated since timestamp"""
        try:
            since_dt = datetime.fromisoformat(since_timestamp.replace('Z', '+00:00'))
            
            filtered = []
            for resource in resources:
                try:
                    updated_dt = datetime.fromisoformat(resource.updatedAt.replace('Z', '+00:00'))
                    if updated_dt > since_dt:
                        filtered.append(resource)
                except Exception:
                    # If we can't parse the timestamp, include the resource
                    filtered.append(resource)
            
            return filtered
            
        except Exception as e:
            logger.warning(f"Failed to filter by timestamp {since_timestamp}: {e}")
            return resources
    
    async def _update_connection_state(self, connection_id: str, request: HydrationRequest, resources: List[UIResource]):
        """Update connection state for recovery"""
        now = datetime.now(timezone.utc).isoformat()
        
        # Build resource versions map
        resource_versions = {}
        subscribed_agents = set()
        
        for resource in resources:
            resource_versions[resource.id] = resource.revision
            subscribed_agents.add(resource.agentId)
        
        # Create or update connection state
        self.connection_states[connection_id] = ConnectionState(
            connection_id=connection_id,
            tenant_id=request.tenant_id,
            session_id=request.session_id,
            last_hydration=now,
            last_update=now,
            resource_versions=resource_versions,
            subscribed_agents=subscribed_agents
        )
        
        logger.debug(f"Updated connection state for {connection_id}: {len(resources)} resources, {len(subscribed_agents)} agents")
    
    async def get_incremental_updates(self, connection_id: str, since_timestamp: Optional[str] = None) -> Optional[HydrationResponse]:
        """
        Get incremental updates for a connection
        
        Args:
            connection_id: Connection ID
            since_timestamp: Optional timestamp to filter from (uses connection state if not provided)
            
        Returns:
            HydrationResponse with incremental updates or None if connection not found
        """
        if connection_id not in self.connection_states:
            logger.warning(f"No connection state found for {connection_id}")
            return None
        
        state = self.connection_states[connection_id]
        
        # Use provided timestamp or connection's last update
        filter_timestamp = since_timestamp or state.last_update
        
        request = HydrationRequest(
            tenant_id=state.tenant_id,
            session_id=state.session_id,
            since_timestamp=filter_timestamp,
            connection_id=connection_id
        )
        
        try:
            response = await self.hydrate_connection(request)
            
            # Update connection state
            state.last_update = response.timestamp
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get incremental updates for {connection_id}: {e}")
            return None
    
    async def handle_connection_recovery(self, connection_id: str, websocket_manager: WebSocketManager) -> bool:
        """
        Handle connection recovery by sending missed updates
        
        Args:
            connection_id: Connection ID to recover
            websocket_manager: WebSocket manager for sending updates
            
        Returns:
            True if recovery was successful, False otherwise
        """
        if connection_id not in self.connection_states:
            logger.info(f"No previous state found for connection {connection_id}, performing full hydration")
            return False
        
        try:
            # Get incremental updates
            response = await self.get_incremental_updates(connection_id)
            
            if not response:
                logger.error(f"Failed to get incremental updates for connection recovery {connection_id}")
                return False
            
            # Send recovery event
            recovery_event = WebSocketEvent(
                type="recovery",
                tenant_id=response.tenant_id,
                session_id=response.session_id,
                resources=response.resources,
                timestamp=response.timestamp,
                connection_id=connection_id,
                message=f"Recovered {response.filtered_count} updates since {response.since_timestamp}"
            )
            
            await websocket_manager._send_to_connection(connection_id, recovery_event)
            
            logger.info(f"Successfully recovered connection {connection_id} with {response.filtered_count} updates")
            return True
            
        except Exception as e:
            logger.error(f"Connection recovery failed for {connection_id}: {e}")
            return False
    
    def remove_connection_state(self, connection_id: str):
        """Remove connection state (called on disconnect)"""
        if connection_id in self.connection_states:
            del self.connection_states[connection_id]
            logger.debug(f"Removed connection state for {connection_id}")
    
    async def _cleanup_loop(self):
        """Background task to clean up old connection states"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_old_states()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in hydration cleanup loop: {e}")
    
    async def _cleanup_old_states(self):
        """Clean up old connection states"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.state_retention_hours)
        cutoff_iso = cutoff_time.isoformat()
        
        old_connections = []
        
        for connection_id, state in self.connection_states.items():
            try:
                last_update_dt = datetime.fromisoformat(state.last_update.replace('Z', '+00:00'))
                if last_update_dt < cutoff_time:
                    old_connections.append(connection_id)
            except Exception:
                # If we can't parse the timestamp, consider it old
                old_connections.append(connection_id)
        
        # Remove old states
        for connection_id in old_connections:
            del self.connection_states[connection_id]
        
        if old_connections:
            logger.info(f"Cleaned up {len(old_connections)} old connection states")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hydration service statistics"""
        return {
            "hydrations_performed": self.hydrations_performed,
            "incremental_updates": self.incremental_updates,
            "resources_hydrated": self.resources_hydrated,
            "active_connection_states": len(self.connection_states),
            "max_resources_per_hydration": self.max_resources_per_hydration,
            "hydration_timeout": self.hydration_timeout,
            "state_retention_hours": self.state_retention_hours
        }
    
    def reset_statistics(self):
        """Reset hydration service statistics"""
        self.hydrations_performed = 0
        self.incremental_updates = 0
        self.resources_hydrated = 0
        logger.info("Hydration service statistics reset")


# Utility functions

async def create_hydration_request_from_connection(
    connection_id: str,
    tenant_id: str,
    session_id: str,
    agent_id: Optional[str] = None,
    resource_types: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    include_expired: bool = False,
    since_timestamp: Optional[str] = None
) -> HydrationRequest:
    """Create a hydration request from connection parameters"""
    return HydrationRequest(
        tenant_id=tenant_id,
        session_id=session_id,
        agent_id=agent_id,
        resource_types=resource_types,
        tags=tags,
        include_expired=include_expired,
        since_timestamp=since_timestamp,
        connection_id=connection_id
    )


async def batch_hydrate_connections(
    hydration_service: HydrationService,
    requests: List[HydrationRequest]
) -> List[HydrationResponse]:
    """
    Perform batch hydration for multiple connections
    
    Args:
        hydration_service: HydrationService instance
        requests: List of hydration requests
        
    Returns:
        List of hydration responses
    """
    tasks = [hydration_service.hydrate_connection(request) for request in requests]
    
    try:
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        valid_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Batch hydration failed for request {i}: {response}")
            else:
                valid_responses.append(response)
        
        return valid_responses
        
    except Exception as e:
        logger.error(f"Batch hydration failed: {e}")
        return []


# Global hydration service instance
hydration_service: Optional[HydrationService] = None


def get_hydration_service() -> HydrationService:
    """Get the global hydration service instance"""
    global hydration_service
    if hydration_service is None:
        raise RuntimeError("Hydration service not initialized. Call initialize_hydration_service() first.")
    return hydration_service


def initialize_hydration_service(resource_provider: Callable[[str, str], List[UIResource]]) -> HydrationService:
    """Initialize the global hydration service"""
    global hydration_service
    hydration_service = HydrationService(resource_provider)
    return hydration_service