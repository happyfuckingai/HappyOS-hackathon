"""
MCP UI Hub Routes - Multi-Tenant UI Resource Server

Implements the UI Hub for AWS AI Agents hackathon projects:
- meetmind.com (MeetMind Summarizer)
- happyos.com (Full ecosystem)  
- feliciasfi.com (Felicia's Finance)

Architecture:
- 3 MCP Agents (Felicia's Finance, Agent Svea, MeetMind Summarizer) → UI Hub
- UI Hub → 3 Frontends (same renderer, different themes/brands)
- Multi-tenant with tenantId/sessionId/agentId isolation
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..modules.auth import get_current_user, verify_ui_scope
from ..services.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/ui-hub", tags=["UI Hub"])


class UIResource(BaseModel):
    """UI Resource following MCP-UI standard with MeetMind namespacing"""
    id: str = Field(..., description="Resource ID")
    namespace: str = Field(..., description="Namespace: mm://{sessionId}/{agentId}/{resourceName}")
    type: str = Field(..., description="Resource type (chart, table, card, etc.)")
    title: str = Field(..., description="Resource title")
    data: Dict[str, Any] = Field(..., description="Resource data")
    config: Optional[Dict[str, Any]] = Field(None, description="Resource configuration")
    version: str = Field(default="2025-10-01", description="Schema version")
    revision: int = Field(default=1, description="Monotonic revision number")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for retries")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class UIResourcePatch(BaseModel):
    """Partial update for UI Resource"""
    title: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


class UIEvent(BaseModel):
    """UI Event for real-time updates"""
    type: str = Field(..., description="Event type (create, update, delete)")
    resource_id: str = Field(..., description="Resource ID")
    namespace: str = Field(..., description="Resource namespace")
    data: Optional[Dict[str, Any]] = Field(None, description="Event data")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# In-memory storage (in production, use Redis or database)
ui_resources: Dict[str, UIResource] = {}
resource_revisions: Dict[str, int] = {}
active_connections: Dict[str, List[WebSocket]] = {}  # session_id -> websockets


@router.post("/resources", response_model=UIResource)
async def create_ui_resource(
    resource: UIResource,
    current_user: dict = Depends(get_current_user)
) -> UIResource:
    """
    Create new UI resource
    
    Agents use this to create new UI components (charts, tables, cards, etc.)
    """
    try:
        # Validate namespace format: mm://{sessionId}/{agentId}/{resourceName}
        if not resource.namespace.startswith("mm://"):
            raise HTTPException(status_code=400, detail="Invalid namespace format")
        
        namespace_parts = resource.namespace.replace("mm://", "").split("/")
        if len(namespace_parts) != 3:
            raise HTTPException(status_code=400, detail="Namespace must be mm://{sessionId}/{agentId}/{resourceName}")
        
        session_id, agent_id, resource_name = namespace_parts
        
        # Verify JWT scope for this session
        required_scope = f"ui:write:session-{session_id}"
        if not verify_ui_scope(current_user, required_scope):
            raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")
        
        # Check idempotency
        if resource.idempotency_key:
            existing = _find_resource_by_idempotency_key(resource.idempotency_key, resource.namespace)
            if existing:
                logger.info(f"Idempotent create for resource {resource.id}")
                return existing
        
        # Generate ID if not provided
        if not resource.id:
            resource.id = f"{resource_name}_{uuid4().hex[:8]}"
        
        # Set revision
        resource.revision = _get_next_revision(resource.id)
        
        # Store resource
        ui_resources[resource.id] = resource
        
        # Broadcast create event
        await _broadcast_ui_event(UIEvent(
            type="create",
            resource_id=resource.id,
            namespace=resource.namespace,
            data=resource.dict()
        ), session_id)
        
        logger.info(f"Created UI resource {resource.id} in namespace {resource.namespace}")
        return resource
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create UI resource: {e}")
        raise HTTPException(status_code=500, detail="Failed to create resource")


@router.patch("/resources/{resource_id}", response_model=UIResource)
async def update_ui_resource(
    resource_id: str,
    patch: UIResourcePatch,
    current_user: dict = Depends(get_current_user)
) -> UIResource:
    """
    Update existing UI resource
    
    Agents use this to update UI components with new data
    """
    try:
        # Find existing resource
        if resource_id not in ui_resources:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        existing_resource = ui_resources[resource_id]
        
        # Extract session from namespace for scope verification
        namespace_parts = existing_resource.namespace.replace("mm://", "").split("/")
        session_id = namespace_parts[0]
        
        # Verify JWT scope
        required_scope = f"ui:write:session-{session_id}"
        if not verify_ui_scope(current_user, required_scope):
            raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")
        
        # Check idempotency
        if patch.idempotency_key:
            if existing_resource.idempotency_key == patch.idempotency_key:
                logger.info(f"Idempotent update for resource {resource_id}")
                return existing_resource
        
        # Apply patch
        update_data = patch.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field != "idempotency_key":
                setattr(existing_resource, field, value)
        
        # Update metadata
        existing_resource.revision = _get_next_revision(resource_id)
        existing_resource.updated_at = datetime.now(timezone.utc).isoformat()
        if patch.idempotency_key:
            existing_resource.idempotency_key = patch.idempotency_key
        
        # Broadcast update event
        await _broadcast_ui_event(UIEvent(
            type="update",
            resource_id=resource_id,
            namespace=existing_resource.namespace,
            data=existing_resource.dict()
        ), session_id)
        
        logger.info(f"Updated UI resource {resource_id}")
        return existing_resource
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update UI resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update resource")


@router.delete("/resources/{resource_id}")
async def delete_ui_resource(
    resource_id: str,
    current_user: dict = Depends(get_current_user)
) -> JSONResponse:
    """
    Delete UI resource
    
    Agents use this to remove UI components
    """
    try:
        # Find existing resource
        if resource_id not in ui_resources:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        existing_resource = ui_resources[resource_id]
        
        # Extract session from namespace for scope verification
        namespace_parts = existing_resource.namespace.replace("mm://", "").split("/")
        session_id = namespace_parts[0]
        
        # Verify JWT scope
        required_scope = f"ui:write:session-{session_id}"
        if not verify_ui_scope(current_user, required_scope):
            raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")
        
        # Remove resource
        del ui_resources[resource_id]
        if resource_id in resource_revisions:
            del resource_revisions[resource_id]
        
        # Broadcast delete event
        await _broadcast_ui_event(UIEvent(
            type="delete",
            resource_id=resource_id,
            namespace=existing_resource.namespace
        ), session_id)
        
        logger.info(f"Deleted UI resource {resource_id}")
        return JSONResponse(content={"success": True, "message": "Resource deleted"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete UI resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete resource")


@router.get("/resources", response_model=List[UIResource])
async def list_ui_resources(
    session_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> List[UIResource]:
    """
    List UI resources with optional filtering
    
    Frontend uses this to get current UI state
    """
    try:
        # Verify read scope for session
        if session_id:
            required_scope = f"ui:read:session-{session_id}"
            if not verify_ui_scope(current_user, required_scope):
                raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")
        
        # Filter resources
        filtered_resources = []
        for resource in ui_resources.values():
            namespace_parts = resource.namespace.replace("mm://", "").split("/")
            resource_session_id, resource_agent_id, _ = namespace_parts
            
            # Apply filters
            if session_id and resource_session_id != session_id:
                continue
            if agent_id and resource_agent_id != agent_id:
                continue
            
            # Check read permission for this session
            if not session_id:  # If no session filter, check each resource
                required_scope = f"ui:read:session-{resource_session_id}"
                if not verify_ui_scope(current_user, required_scope):
                    continue
            
            filtered_resources.append(resource)
        
        return filtered_resources
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list UI resources: {e}")
        raise HTTPException(status_code=500, detail="Failed to list resources")


@router.get("/resources/{resource_id}", response_model=UIResource)
async def get_ui_resource(
    resource_id: str,
    current_user: dict = Depends(get_current_user)
) -> UIResource:
    """
    Get specific UI resource
    """
    try:
        if resource_id not in ui_resources:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        resource = ui_resources[resource_id]
        
        # Extract session from namespace for scope verification
        namespace_parts = resource.namespace.replace("mm://", "").split("/")
        session_id = namespace_parts[0]
        
        # Verify JWT scope
        required_scope = f"ui:read:session-{session_id}"
        if not verify_ui_scope(current_user, required_scope):
            raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")
        
        return resource
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get UI resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource")


@router.get("/sessions/{session_id}/stream")
async def stream_ui_events(
    session_id: str,
    current_user: dict = Depends(get_current_user)
) -> EventSourceResponse:
    """
    Server-Sent Events stream for real-time UI updates
    
    Frontend subscribes to this for real-time UI resource updates
    """
    # Verify read scope
    required_scope = f"ui:read:session-{session_id}"
    if not verify_ui_scope(current_user, required_scope):
        raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")
    
    async def event_generator():
        try:
            # Send initial state
            session_resources = [
                r for r in ui_resources.values()
                if r.namespace.startswith(f"mm://{session_id}/")
            ]
            
            initial_event = {
                "type": "initial_state",
                "data": {
                    "resources": [r.dict() for r in session_resources],
                    "session_id": session_id
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            yield f"data: {json.dumps(initial_event)}\n\n"
            
            # Keep connection alive and send heartbeats
            while True:
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"
                await asyncio.sleep(30)
                
        except Exception as e:
            logger.error(f"SSE stream error for session {session_id}: {e}")
            error_event = {
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.websocket("/sessions/{session_id}/ws")
async def websocket_ui_events(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time UI updates
    
    Alternative to SSE for bidirectional communication
    """
    await websocket.accept()
    
    # Add to active connections
    if session_id not in active_connections:
        active_connections[session_id] = []
    active_connections[session_id].append(websocket)
    
    try:
        # Send initial state
        session_resources = [
            r for r in ui_resources.values()
            if r.namespace.startswith(f"mm://{session_id}/")
        ]
        
        initial_message = {
            "type": "initial_state",
            "data": {
                "resources": [r.dict() for r in session_resources],
                "session_id": session_id
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await websocket.send_json(initial_message)
        
        # Keep connection alive
        while True:
            # Wait for messages (ping/pong, etc.)
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                # Handle client messages if needed
            except asyncio.TimeoutError:
                # Send heartbeat
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_json(heartbeat)
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        # Remove from active connections
        if session_id in active_connections:
            try:
                active_connections[session_id].remove(websocket)
                if not active_connections[session_id]:
                    del active_connections[session_id]
            except ValueError:
                pass


@router.get("/health")
async def ui_hub_health() -> JSONResponse:
    """
    UI Hub health check
    """
    return JSONResponse(content={
        "status": "healthy",
        "resources_count": len(ui_resources),
        "active_sessions": len(active_connections),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# Helper functions
def _get_next_revision(resource_id: str) -> int:
    """Get next monotonic revision number for resource"""
    if resource_id not in resource_revisions:
        resource_revisions[resource_id] = 0
    resource_revisions[resource_id] += 1
    return resource_revisions[resource_id]


def _find_resource_by_idempotency_key(idempotency_key: str, namespace: str) -> Optional[UIResource]:
    """Find resource by idempotency key within namespace"""
    for resource in ui_resources.values():
        if (resource.idempotency_key == idempotency_key and 
            resource.namespace == namespace):
            return resource
    return None


async def _broadcast_ui_event(event: UIEvent, session_id: str):
    """Broadcast UI event to all connected clients for session"""
    if session_id not in active_connections:
        return
    
    event_data = event.dict()
    dead_connections = []
    
    for websocket in active_connections[session_id]:
        try:
            await websocket.send_json(event_data)
        except Exception as e:
            logger.warning(f"Failed to send event to WebSocket: {e}")
            dead_connections.append(websocket)
    
    # Clean up dead connections
    for websocket in dead_connections:
        try:
            active_connections[session_id].remove(websocket)
        except ValueError:
            pass
    
    if not active_connections[session_id]:
        del active_connections[session_id]