"""
MCP UI Hub Routes - Central Platform for Multi-Tenant UI Resource Management

This is the core platform that all startup MCP servers connect to for UI resource management.
Implements the central MCP UI Hub platform with:
- Multi-tenant isolation (meetmind, happyos, feliciasfi)
- Standardized MCP server registration and discovery
- Real-time UI resource broadcasting
- Platform-as-a-service infrastructure for rapid startup deployment
- Ecosystem control through centralized UI resource management

Requirements: 1.4, 6.1, 6.5, 4.1, 4.2, 4.3, 4.4
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import jsonschema
import jsonpatch

from ..modules.auth import get_current_user, verify_jwt_token, get_jwt_claims, validate_ui_write_access, validate_ui_read_access
from ..modules.auth.tenant_isolation import tenant_isolation_service, audit_logger, TenantIsolationError, CrossTenantAccessError
from ..modules.models.ui_resource import (
    UIResource, UIResourceCreate, UIResourcePatch, UIResourceQuery,
    ui_resource_validator, RevisionConflictError, IdempotencyConflictError
)
from ..services.validation import (
    json_schema_validation_service, ValidationError,
    validate_resource_creation, validate_patch_operations
)
from ..modules.models.revision_manager import (
    revision_manager, ttl_manager, RevisionConflictError, IdempotencyConflictError
)
from ..services.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/mcp-ui", tags=["MCP UI Hub"])

# MCP Agent model for registration
class MCPAgentRegistration(BaseModel):
    """MCP Agent registration request"""
    agentId: str = Field(..., pattern="^[a-z0-9-]+$")
    tenantId: str = Field(..., pattern="^[a-z0-9-]+$")
    name: str = Field(...)
    description: str = Field(...)
    version: str = Field(...)
    capabilities: List[str] = Field(default_factory=list)
    endpoints: Dict[str, str] = Field(default_factory=dict)
    healthCheckUrl: Optional[str] = None


class MCPAgent(BaseModel):
    """MCP Agent registration for standardized server discovery"""
    agentId: str = Field(..., pattern="^[a-z0-9-]+$")
    tenantId: str = Field(..., pattern="^[a-z0-9-]+$")
    name: str = Field(...)
    description: str = Field(...)
    version: str = Field(...)
    capabilities: List[str] = Field(default_factory=list)
    endpoints: Dict[str, str] = Field(default_factory=dict)
    healthCheckUrl: Optional[str] = None
    registeredAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    lastHeartbeat: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# In-memory storage (in production, use DynamoDB)
ui_resources: Dict[str, UIResource] = {}
resource_revisions: Dict[str, int] = {}
registered_agents: Dict[str, MCPAgent] = {}
active_websockets: Dict[str, Set[WebSocket]] = {}  # topic -> websockets
tenant_configs = {
    "meetmind": {
        "name": "MeetMind",
        "domain": "meetmind.com",
        "allowedAgents": ["meetmind-summarizer"]
    },
    "happyos": {
        "name": "HappyOS",
        "domain": "happyos.com", 
        "allowedAgents": ["felicia-core", "agent-svea", "meetmind-summarizer"]
    },
    "feliciasfi": {
        "name": "Felicia's Finance",
        "domain": "feliciasfi.com",
        "allowedAgents": ["felicia-core"]
    }
}


def validate_tenant_access(jwt_claims: Dict, tenant_id: str, session_id: str, operation: str) -> bool:
    """Validate JWT scopes for tenant access - DEPRECATED: Use tenant_isolation_service instead"""
    # Convert dict to JWTClaims for new system
    from ..modules.auth.jwt_service import JWTClaims
    
    try:
        claims = JWTClaims(**jwt_claims)
        return tenant_isolation_service.validate_tenant_access(
            claims, tenant_id, session_id, operation
        )
    except (TenantIsolationError, CrossTenantAccessError):
        return False
    except Exception:
        # Fallback to legacy validation
        required_scope = f"ui:{operation}:{tenant_id}:{session_id}"
        scopes = jwt_claims.get("scopes", [])
        
        # Check exact scope match
        if required_scope in scopes:
            return True
        
        # Check wildcard scopes
        wildcard_scope = f"ui:{operation}:{tenant_id}:*"
        if wildcard_scope in scopes:
            return True
        
        return False


def validate_json_schema(resource_data: Dict[str, Any], version: str) -> None:
    """
    Validate UI resource against JSON schema
    
    This function enforces JSON schema validation for all resource operations
    to ensure data integrity and consistency across the platform.
    
    Args:
        resource_data: Resource data to validate
        version: Schema version to use for validation
        
    Raises:
        ValueError: If validation fails with detailed error message
    """
    try:
        ui_resource_validator.validate(resource_data, version)
        logger.debug(f"JSON schema validation passed for version {version}")
    except ValueError as e:
        logger.error(f"JSON schema validation failed: {e}")
        raise ValueError(f"JSON schema validation failed: {str(e)}")


def validate_payload_by_type(payload: Dict[str, Any], resource_type: str, version: str = "2025-10-21") -> None:
    """
    Validate payload against type-specific JSON schema
    
    This function provides granular validation for resource payloads based on their type.
    
    Args:
        payload: Payload data to validate
        resource_type: Type of resource (card, list, form, chart)
        version: Schema version to use for validation
        
    Raises:
        ValueError: If validation fails with detailed error message
    """
    try:
        ui_resource_validator.validate_payload_by_type(payload, resource_type, version)
        logger.debug(f"Payload validation passed for type {resource_type}")
    except ValueError as e:
        logger.error(f"Payload validation failed for type {resource_type}: {e}")
        raise ValueError(f"Payload validation failed for {resource_type}: {str(e)}")


def validate_patch_operations(patch_ops: List[Dict[str, Any]], current_resource: UIResource) -> None:
    """
    Validate JSON Patch operations before applying them
    
    This function ensures that patch operations are valid and won't result in
    an invalid resource state after application.
    
    Args:
        patch_ops: List of JSON Patch operations
        current_resource: Current resource state
        
    Raises:
        ValueError: If patch operations are invalid
    """
    try:
        # Validate patch operation structure
        for op in patch_ops:
            if not isinstance(op, dict):
                raise ValueError("Each patch operation must be a dictionary")
            
            if 'op' not in op:
                raise ValueError("Each patch operation must have an 'op' field")
            
            if 'path' not in op:
                raise ValueError("Each patch operation must have a 'path' field")
            
            # Validate operation type
            valid_ops = ['add', 'remove', 'replace', 'move', 'copy', 'test']
            if op['op'] not in valid_ops:
                raise ValueError(f"Invalid patch operation: {op['op']}. Valid operations: {valid_ops}")
            
            # Validate path format
            path = op['path']
            if not isinstance(path, str) or not path.startswith('/'):
                raise ValueError("Patch path must be a string starting with '/'")
            
            # Prevent modification of protected fields
            protected_paths = ['/id', '/tenantId', '/sessionId', '/agentId', '/createdAt', '/version']
            if any(path.startswith(protected) for protected in protected_paths):
                raise ValueError(f"Cannot modify protected field: {path}")
        
        # Test apply patch to validate it won't break the resource
        import jsonpatch
        resource_dict = current_resource.model_dump()
        try:
            patch_obj = jsonpatch.JsonPatch(patch_ops)
            patched_dict = patch_obj.apply(resource_dict)
            
            # Validate the patched resource would be valid
            validate_json_schema(patched_dict, current_resource.version)
            
        except jsonpatch.JsonPatchException as e:
            raise ValueError(f"Invalid patch operation: {e}")
        except Exception as e:
            raise ValueError(f"Patch would result in invalid resource: {e}")
            
        logger.debug(f"Patch operations validation passed for resource {current_resource.id}")
        
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Patch validation error: {e}")
        raise ValueError(f"Patch validation failed: {str(e)}")


async def cleanup_expired_resources():
    """Clean up expired resources using TTL manager"""
    try:
        cleaned_count = await ttl_manager.cleanup_expired()
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired resources")
    except Exception as e:
        logger.error(f"Error cleaning up expired resources: {e}")


async def resource_cleanup_callback(resource_id: str):
    """Callback for when a resource expires"""
    if resource_id in ui_resources:
        resource = ui_resources[resource_id]
        del ui_resources[resource_id]
        
        # Broadcast delete event
        await broadcast_event("delete", resource)
        
        # Clean up revision info
        await revision_manager.delete_resource_revision(resource_id)
        
        logger.info(f"Auto-deleted expired resource: {resource_id}")


async def broadcast_event(event_type: str, resource: UIResource, old_resource: Optional[UIResource] = None):
    """
    Broadcast UI event using the enhanced event broadcasting system
    
    Uses the new event broadcaster for improved reliability and features.
    """
    try:
        from ..services.event_broadcaster import get_event_broadcaster
        
        broadcaster = get_event_broadcaster()
        
        if event_type == "create":
            await broadcaster.broadcast_resource_created(resource)
        elif event_type == "update":
            await broadcaster.broadcast_resource_updated(resource, old_resource)
        elif event_type == "delete":
            await broadcaster.broadcast_resource_deleted(resource)
        else:
            logger.warning(f"Unknown event type for broadcasting: {event_type}")
            
    except Exception as e:
        logger.error(f"Failed to broadcast event {event_type} for resource {resource.id}: {e}")
        # Fallback to legacy broadcasting if new system fails
        await _legacy_broadcast_event(event_type, resource, old_resource)


async def _legacy_broadcast_event(event_type: str, resource: UIResource, old_resource: Optional[UIResource] = None):
    """Legacy broadcast function as fallback"""
    topic = f"ui.{resource.tenantId}.{resource.sessionId}"
    
    if topic not in active_websockets:
        return
    
    event_data = {
        "type": event_type,
        "resourceId": resource.id,
        "tenantId": resource.tenantId,
        "sessionId": resource.sessionId,
        "agentId": resource.agentId,
        "resource": resource.model_dump() if event_type != "delete" else None,
        "oldResource": old_resource.model_dump() if old_resource else None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    message = json.dumps(event_data)
    dead_connections = set()
    
    for websocket in active_websockets[topic]:
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
            dead_connections.add(websocket)
    
    # Clean up dead connections
    for websocket in dead_connections:
        active_websockets[topic].discard(websocket)
    
    if not active_websockets[topic]:
        del active_websockets[topic]


# === MCP Agent Registration Endpoints ===

@router.post("/agents/register", response_model=MCPAgent)
async def register_mcp_agent(
    agent_request: MCPAgentRegistration,
    request: Request
) -> MCPAgent:
    """
    Register MCP agent for standardized server discovery
    
    This enables rapid startup deployment by allowing MCP servers to register
    themselves with the central platform for ecosystem control.
    """
    try:
        # Validate tenant exists
        if agent_request.tenantId not in tenant_configs:
            raise HTTPException(status_code=400, detail=f"Unknown tenant: {agent_request.tenantId}")
        
        # Validate agent is allowed for tenant
        allowed_agents = tenant_configs[agent_request.tenantId]["allowedAgents"]
        if agent_request.agentId not in allowed_agents:
            raise HTTPException(
                status_code=403, 
                detail=f"Agent {agent_request.agentId} not allowed for tenant {agent_request.tenantId}"
            )
        
        # Create full agent record
        agent = MCPAgent(
            **agent_request.model_dump(),
            registeredAt=datetime.now(timezone.utc).isoformat(),
            lastHeartbeat=datetime.now(timezone.utc).isoformat()
        )
        
        # Store agent registration
        agent_key = f"{agent.tenantId}:{agent.agentId}"
        registered_agents[agent_key] = agent
        
        logger.info(f"Registered MCP agent {agent.agentId} for tenant {agent.tenantId}")
        
        return agent
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to register MCP agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to register agent")


@router.get("/agents", response_model=List[MCPAgent])
async def list_mcp_agents(
    tenant_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
) -> List[MCPAgent]:
    """
    List registered MCP agents with optional tenant filtering
    
    Supports platform-as-a-service infrastructure by providing agent discovery.
    """
    try:
        agents = list(registered_agents.values())
        
        # Filter by tenant if specified
        if tenant_id:
            agents = [agent for agent in agents if agent.tenantId == tenant_id]
        
        return agents
        
    except Exception as e:
        logger.error(f"Failed to list MCP agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.post("/agents/{tenant_id}/{agent_id}/heartbeat")
async def agent_heartbeat(
    tenant_id: str,
    agent_id: str,
    request: Request
) -> JSONResponse:
    """
    Agent heartbeat for health monitoring
    
    Maintains ecosystem control by tracking agent health and availability.
    """
    try:
        agent_key = f"{tenant_id}:{agent_id}"
        
        if agent_key not in registered_agents:
            raise HTTPException(status_code=404, detail="Agent not registered")
        
        # Update heartbeat timestamp
        registered_agents[agent_key].lastHeartbeat = datetime.now(timezone.utc).isoformat()
        
        return JSONResponse(content={"status": "ok", "timestamp": registered_agents[agent_key].lastHeartbeat})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process agent heartbeat: {e}")
        raise HTTPException(status_code=500, detail="Failed to process heartbeat")


# === UI Resource Management Endpoints ===

@router.post("/resources", response_model=UIResource)
async def create_ui_resource(
    resource_request: UIResourceCreate,
    request: Request
) -> UIResource:
    """
    Create new UI resource with multi-tenant isolation
    
    Core platform functionality for centralized UI resource management.
    Requirements: 4.1
    """
    try:
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Validate tenant access
        if not validate_tenant_access(jwt_claims, resource_request.tenantId, resource_request.sessionId, "write"):
            raise HTTPException(
                status_code=403, 
                detail=f"Missing scope: ui:write:{resource_request.tenantId}:{resource_request.sessionId}"
            )
        
        # Validate resource creation using centralized validation service
        try:
            validated_resource_create = validate_resource_creation(resource_request.model_dump())
            resource = validated_resource_create.to_ui_resource()
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Check idempotency
        if resource.idempotencyKey:
            existing_resource_id = await revision_manager.check_idempotency(
                resource.idempotencyKey,
                resource.tenantId,
                resource.sessionId
            )
            if existing_resource_id and existing_resource_id in ui_resources:
                logger.info(f"Idempotent create for resource {resource.id}")
                return ui_resources[existing_resource_id]
        
        # Get next revision
        agent_id = jwt_claims.get("agentId") or jwt_claims.get("sub")
        resource.revision = await revision_manager.get_next_revision(resource.id, agent_id)
        
        # Set timestamps
        now = datetime.now(timezone.utc).isoformat()
        resource.createdAt = now
        resource.updatedAt = now
        
        # Handle TTL
        if resource.ttlSeconds:
            ttl_manager.set_ttl(resource.id, resource.ttlSeconds, resource_cleanup_callback)
        
        # Record idempotency if provided
        if resource.idempotencyKey:
            await revision_manager.record_idempotency(
                resource.idempotencyKey,
                resource.id,
                resource.tenantId,
                resource.sessionId
            )
        
        # Store resource
        ui_resources[resource.id] = resource
        
        # Broadcast create event
        await broadcast_event("create", resource)
        
        logger.info(f"Created UI resource {resource.id} for tenant {resource.tenantId}")
        
        return resource
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create UI resource: {e}")
        raise HTTPException(status_code=500, detail="Failed to create resource")


@router.patch("/resources/{resource_id}", response_model=UIResource)
async def patch_ui_resource(
    resource_id: str,
    patch: UIResourcePatch,
    request: Request,
    expected_revision: Optional[int] = Query(None, description="Expected current revision for conflict detection")
) -> UIResource:
    """
    Apply JSON Patch operations to UI resource
    
    Enables real-time UI updates through standardized patch operations.
    Requirements: 4.2
    """
    try:
        # Decode URL-encoded resource ID
        decoded_resource_id = urllib.parse.unquote(resource_id)
        
        # Find existing resource
        if decoded_resource_id not in ui_resources:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        existing_resource = ui_resources[decoded_resource_id]
        old_resource = existing_resource.copy()
        
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Validate tenant access
        if not validate_tenant_access(jwt_claims, existing_resource.tenantId, existing_resource.sessionId, "write"):
            raise HTTPException(
                status_code=403, 
                detail=f"Missing scope: ui:write:{existing_resource.tenantId}:{existing_resource.sessionId}"
            )
        
        # Validate revision if provided
        try:
            await revision_manager.validate_revision(decoded_resource_id, expected_revision)
        except RevisionConflictError as e:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "revision_conflict",
                    "message": str(e),
                    "current_revision": e.current_revision,
                    "expected_revision": e.expected_revision
                }
            )
        
        # Validate patch operations using centralized validation service
        try:
            validated_patch = validate_patch_operations(patch.model_dump(), existing_resource)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Apply JSON Patch operations (already validated)
        resource_dict = existing_resource.model_dump()
        try:
            patch_obj = jsonpatch.JsonPatch(validated_patch.ops)
            patched_dict = patch_obj.apply(resource_dict)
        except jsonpatch.JsonPatchException as e:
            raise HTTPException(status_code=400, detail=f"Invalid patch operation: {e}")
        
        # Create new resource instance with patched data
        try:
            # Preserve protected fields
            patched_dict['id'] = existing_resource.id
            patched_dict['tenantId'] = existing_resource.tenantId
            patched_dict['sessionId'] = existing_resource.sessionId
            patched_dict['agentId'] = existing_resource.agentId
            patched_dict['createdAt'] = existing_resource.createdAt
            
            updated_resource = UIResource(**patched_dict)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid resource after patch: {e}")
        
        # Get next revision
        agent_id = jwt_claims.get("agentId") or jwt_claims.get("sub")
        updated_resource.revision = await revision_manager.get_next_revision(decoded_resource_id, agent_id)
        updated_resource.updatedAt = datetime.now(timezone.utc).isoformat()
        
        # Validate updated resource using centralized validation service
        try:
            json_schema_validation_service.validate_resource_update(updated_resource.model_dump())
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Update TTL if changed
        if updated_resource.ttlSeconds != existing_resource.ttlSeconds:
            ttl_manager.remove_ttl(decoded_resource_id)
            if updated_resource.ttlSeconds:
                ttl_manager.set_ttl(decoded_resource_id, updated_resource.ttlSeconds, resource_cleanup_callback)
        
        # Store updated resource
        ui_resources[decoded_resource_id] = updated_resource
        
        # Broadcast update event
        await broadcast_event("update", updated_resource, old_resource)
        
        logger.info(f"Patched UI resource {decoded_resource_id} to revision {updated_resource.revision}")
        
        return updated_resource
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to patch UI resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to patch resource")


@router.delete("/resources/{resource_id}")
async def delete_ui_resource(
    resource_id: str,
    request: Request
) -> JSONResponse:
    """
    Delete UI resource with tenant isolation
    
    Maintains ecosystem control through secure resource deletion.
    Requirements: 4.3
    """
    try:
        # Decode URL-encoded resource ID
        decoded_resource_id = urllib.parse.unquote(resource_id)
        
        # Find existing resource
        if decoded_resource_id not in ui_resources:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        existing_resource = ui_resources[decoded_resource_id]
        
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Validate tenant access
        if not validate_tenant_access(jwt_claims, existing_resource.tenantId, existing_resource.sessionId, "write"):
            raise HTTPException(
                status_code=403, 
                detail=f"Missing scope: ui:write:{existing_resource.tenantId}:{existing_resource.sessionId}"
            )
        
        # Remove resource
        del ui_resources[decoded_resource_id]
        
        # Clean up TTL
        ttl_manager.remove_ttl(decoded_resource_id)
        
        # Clean up revision info
        await revision_manager.delete_resource_revision(decoded_resource_id)
        
        # Broadcast delete event
        await broadcast_event("delete", existing_resource)
        
        logger.info(f"Deleted UI resource {decoded_resource_id}")
        
        return JSONResponse(content={
            "success": True, 
            "message": "Resource deleted",
            "resourceId": decoded_resource_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete UI resource {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete resource")


@router.get("/resources/{resource_id}/revision")
async def get_resource_revision_info(
    resource_id: str,
    request: Request
) -> JSONResponse:
    """
    Get revision information for a resource
    
    Supports conflict resolution by providing current revision details.
    Requirements: 2.3, 4.5
    """
    try:
        # Decode URL-encoded resource ID
        decoded_resource_id = urllib.parse.unquote(resource_id)
        
        # Check if resource exists
        if decoded_resource_id not in ui_resources:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        resource = ui_resources[decoded_resource_id]
        
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Validate read access
        if not validate_tenant_access(jwt_claims, resource.tenantId, resource.sessionId, "read"):
            raise HTTPException(
                status_code=403, 
                detail=f"Missing scope: ui:read:{resource.tenantId}:{resource.sessionId}"
            )
        
        # Get revision info
        revision_info = await revision_manager.get_revision_info(decoded_resource_id)
        
        response_data = {
            "resourceId": decoded_resource_id,
            "currentRevision": resource.revision,
            "createdAt": resource.createdAt,
            "updatedAt": resource.updatedAt,
            "ttlSeconds": resource.ttlSeconds,
            "timeToExpiry": resource.time_to_expiry(),
            "isExpired": resource.is_expired()
        }
        
        if revision_info:
            response_data.update({
                "lastUpdatedBy": revision_info.lastUpdatedBy,
                "conflictCount": revision_info.conflictCount
            })
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get revision info for {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get revision info")


@router.post("/resources/{resource_id}/resolve-conflict")
async def resolve_resource_conflict(
    resource_id: str,
    request: Request,
    force_update: bool = Query(False, description="Force update ignoring revision conflicts")
) -> JSONResponse:
    """
    Resolve revision conflicts for a resource
    
    Provides conflict resolution strategies for concurrent updates.
    Requirements: 2.3, 4.5
    """
    try:
        # Decode URL-encoded resource ID
        decoded_resource_id = urllib.parse.unquote(resource_id)
        
        # Check if resource exists
        if decoded_resource_id not in ui_resources:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        resource = ui_resources[decoded_resource_id]
        
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Validate write access
        if not validate_tenant_access(jwt_claims, resource.tenantId, resource.sessionId, "write"):
            raise HTTPException(
                status_code=403, 
                detail=f"Missing scope: ui:write:{resource.tenantId}:{resource.sessionId}"
            )
        
        # Get current revision info
        revision_info = await revision_manager.get_revision_info(decoded_resource_id)
        
        if not revision_info:
            raise HTTPException(status_code=404, detail="No revision info found")
        
        response_data = {
            "resourceId": decoded_resource_id,
            "currentRevision": resource.revision,
            "conflictCount": revision_info.conflictCount,
            "resolved": False
        }
        
        if force_update:
            # Reset conflict count
            revision_info.conflictCount = 0
            response_data["resolved"] = True
            response_data["message"] = "Conflicts resolved by force update"
            
            logger.info(f"Force resolved conflicts for resource {decoded_resource_id}")
        else:
            # Provide conflict resolution options
            response_data["resolutionOptions"] = [
                {
                    "strategy": "force_update",
                    "description": "Ignore conflicts and proceed with update",
                    "url": f"/mcp-ui/resources/{urllib.parse.quote(decoded_resource_id, safe='')}/resolve-conflict?force_update=true"
                },
                {
                    "strategy": "get_latest",
                    "description": "Get the latest version of the resource",
                    "url": f"/mcp-ui/resources?tenantId={resource.tenantId}&sessionId={resource.sessionId}&agentId={resource.agentId}"
                }
            ]
            response_data["message"] = f"Resource has {revision_info.conflictCount} conflicts. Use resolution options."
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve conflicts for {resource_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve conflicts")


@router.get("/resources/stats/revisions")
async def get_revision_stats(
    request: Request,
    tenantId: Optional[str] = Query(None)
) -> JSONResponse:
    """
    Get revision and conflict statistics
    
    Provides insights into system health and conflict patterns.
    Requirements: 2.3, 4.5
    """
    try:
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Get global stats
        conflict_stats = await revision_manager.get_conflict_stats()
        ttl_stats = ttl_manager.get_stats()
        
        # Filter by tenant if specified and user has access
        tenant_resources = []
        if tenantId:
            if not validate_tenant_access(jwt_claims, tenantId, "*", "read"):
                raise HTTPException(
                    status_code=403, 
                    detail=f"Missing scope: ui:read:{tenantId}:*"
                )
            tenant_resources = [r for r in ui_resources.values() if r.tenantId == tenantId]
        
        response_data = {
            "global_stats": {
                **conflict_stats,
                **ttl_stats
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if tenantId:
            response_data["tenant_stats"] = {
                "tenantId": tenantId,
                "total_resources": len(tenant_resources),
                "expired_resources": sum(1 for r in tenant_resources if r.is_expired()),
                "resources_with_ttl": sum(1 for r in tenant_resources if r.ttlSeconds is not None)
            }
        
        return JSONResponse(content=response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get revision stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get revision stats")


# Background task for cleanup
_cleanup_task = None
_websocket_system_initialized = False

async def start_cleanup_task():
    """Start background cleanup task"""
    global _cleanup_task
    if _cleanup_task is None:
        _cleanup_task = asyncio.create_task(cleanup_background_task())

async def stop_cleanup_task():
    """Stop background cleanup task"""
    global _cleanup_task
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        _cleanup_task = None

async def cleanup_background_task():
    """Background task to clean up expired resources"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            await cleanup_expired_resources()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cleanup background task: {e}")

async def initialize_websocket_system():
    """Initialize the WebSocket system for real-time updates"""
    global _websocket_system_initialized
    
    if _websocket_system_initialized:
        return
    
    try:
        from ..services.websocket_init import setup_websocket_system_for_mcp_ui
        
        # Set up WebSocket system with UI resources
        await setup_websocket_system_for_mcp_ui(ui_resources)
        
        _websocket_system_initialized = True
        logger.info("WebSocket system initialized for MCP UI Hub")
        
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket system: {e}")
        # Continue without WebSocket system - fallback to legacy mode

# Initialize WebSocket system and start cleanup task when module is imported
async def _startup_tasks():
    """Run startup tasks"""
    await initialize_websocket_system()
    await start_cleanup_task()

# Schedule startup tasks
asyncio.create_task(_startup_tasks())


@router.get("/resources", response_model=List[UIResource])
async def query_ui_resources(
    request: Request,
    tenantId: Optional[str] = Query(None),
    sessionId: Optional[str] = Query(None),
    agentId: Optional[str] = Query(None),
    type: Optional[str] = Query(None, pattern="^(card|list|form|chart)$"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tags"),
    includeExpired: bool = Query(False, description="Include expired resources"),
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[int] = Query(None, ge=0)
) -> List[UIResource]:
    """
    Query UI resources with multi-tenant filtering
    
    Supports frontend integration with proper tenant isolation.
    Requirements: 4.4
    """
    try:
        # Clean up expired resources first
        await cleanup_expired_resources()
        
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Parse tags filter
        tag_filter = []
        if tags:
            tag_filter = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        filtered_resources = []
        
        for resource in ui_resources.values():
            # Skip expired resources unless explicitly requested
            if not includeExpired and resource.is_expired():
                continue
            
            # Apply filters
            if tenantId and resource.tenantId != tenantId:
                continue
            if sessionId and resource.sessionId != sessionId:
                continue
            if agentId and resource.agentId != agentId:
                continue
            if type and resource.type != type:
                continue
            
            # Tag filtering (resource must have all specified tags)
            if tag_filter:
                if not all(tag in resource.tags for tag in tag_filter):
                    continue
            
            # Validate read access for this resource
            if validate_tenant_access(jwt_claims, resource.tenantId, resource.sessionId, "read"):
                filtered_resources.append(resource)
        
        # Sort by creation time (newest first)
        filtered_resources.sort(key=lambda r: r.createdAt, reverse=True)
        
        # Apply pagination
        if offset:
            filtered_resources = filtered_resources[offset:]
        if limit:
            filtered_resources = filtered_resources[:limit]
        
        logger.info(f"Queried {len(filtered_resources)} UI resources with filters: "
                   f"tenant={tenantId}, session={sessionId}, agent={agentId}, type={type}")
        
        return filtered_resources
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query UI resources: {e}")
        raise HTTPException(status_code=500, detail="Failed to query resources")


# === Real-time WebSocket Endpoints ===

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    topic: str = Query(...),
    token: Optional[str] = Query(None, description="JWT authentication token")
):
    """
    Enhanced WebSocket endpoint for real-time UI updates
    
    Features:
    - Connection authentication and authorization
    - Topic-based message routing with tenant isolation
    - Connection lifecycle management
    - Hydration and initial state loading
    - Health monitoring and dead connection cleanup
    
    Topic format: ui.{tenantId}.{sessionId}
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
    """
    from ..services.websocket_manager import websocket_manager
    from ..services.event_broadcaster import get_event_broadcaster
    from ..services.hydration_service import get_hydration_service
    
    # Accept WebSocket connection
    await websocket.accept()
    
    try:
        # Connect through WebSocket manager with authentication
        success, connection_id, error_msg = await websocket_manager.connect(websocket, topic, token)
        
        if not success:
            await websocket.close(code=1008, reason=error_msg or "Connection failed")
            return
        
        logger.info(f"WebSocket connection established: {connection_id} for topic {topic}")
        
        # Keep connection alive and handle messages
        try:
            while True:
                # Wait for client messages
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle message through WebSocket manager
                await websocket_manager.handle_client_message(connection_id, message)
                
        except asyncio.TimeoutError:
            # Connection timeout - will be handled by cleanup
            logger.debug(f"WebSocket timeout for connection {connection_id}")
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {connection_id}")
            
    except Exception as e:
        logger.error(f"WebSocket error for topic {topic}: {e}")
        
    finally:
        # Disconnect through WebSocket manager
        if 'connection_id' in locals():
            await websocket_manager.disconnect(connection_id, code=1000, reason="Normal closure")


# === Platform Health and Status Endpoints ===

@router.get("/health")
async def platform_health() -> JSONResponse:
    """
    Platform health check for ecosystem monitoring
    
    Provides comprehensive health status for the central MCP UI Hub platform.
    """
    try:
        # Count active resources by tenant
        tenant_stats = {}
        for tenant_id in tenant_configs.keys():
            tenant_resources = [r for r in ui_resources.values() if r.tenantId == tenant_id]
            tenant_stats[tenant_id] = {
                "resources": len(tenant_resources),
                "agents": len([a for a in registered_agents.values() if a.tenantId == tenant_id]),
                "websockets": sum(len(ws_set) for topic, ws_set in active_websockets.items() if topic.startswith(f"ui.{tenant_id}."))
            }
        
        return JSONResponse(content={
            "status": "healthy",
            "platform": "MCP UI Hub",
            "version": "2025-10-21",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "total_resources": len(ui_resources),
                "registered_agents": len(registered_agents),
                "active_websockets": sum(len(ws_set) for ws_set in active_websockets.values()),
                "supported_tenants": list(tenant_configs.keys()),
                "tenant_stats": tenant_stats
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get platform health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get platform health")


@router.get("/tenants")
async def list_tenants() -> JSONResponse:
    """
    List supported tenants for platform-as-a-service infrastructure
    
    Enables rapid startup deployment by providing tenant configuration discovery.
    """
    return JSONResponse(content={
        "tenants": tenant_configs,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@router.get("/websocket/health")
async def websocket_health() -> JSONResponse:
    """
    WebSocket system health check
    
    Provides comprehensive health status for the real-time WebSocket system.
    Requirements: 3.1, 3.2, 3.3
    """
    try:
        from ..services.websocket_init import websocket_system_health_check
        
        health_data = websocket_system_health_check()
        
        # Add legacy WebSocket info
        health_data["legacy_websockets"] = {
            "active_topics": len(active_websockets),
            "total_connections": sum(len(ws_set) for ws_set in active_websockets.values())
        }
        
        return JSONResponse(content=health_data)
        
    except Exception as e:
        logger.error(f"Failed to get WebSocket health: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.get("/validation/health")
async def validation_health() -> JSONResponse:
    """
    JSON Schema validation health check
    
    Provides comprehensive status and statistics about the JSON schema validation system.
    This endpoint verifies that JSON schema validation is properly enforced for all
    resource operations as required.
    """
    try:
        validation_stats = json_schema_validation_service.get_validation_stats()
        
        # Test validation with sample resources for each type
        test_results = {}
        
        test_cases = {
            "card": {
                "tenantId": "test",
                "sessionId": "test-session",
                "agentId": "test-agent",
                "name": "test-card",
                "type": "card",
                "payload": {"title": "Test Card"}
            },
            "list": {
                "tenantId": "test",
                "sessionId": "test-session",
                "agentId": "test-agent",
                "name": "test-list",
                "type": "list",
                "payload": {"title": "Test List", "items": ["Item 1", "Item 2"]}
            },
            "form": {
                "tenantId": "test",
                "sessionId": "test-session",
                "agentId": "test-agent",
                "name": "test-form",
                "type": "form",
                "payload": {
                    "title": "Test Form",
                    "fields": [{"name": "test", "label": "Test Field", "type": "text"}]
                }
            },
            "chart": {
                "tenantId": "test",
                "sessionId": "test-session",
                "agentId": "test-agent",
                "name": "test-chart",
                "type": "chart",
                "payload": {
                    "title": "Test Chart",
                    "chartType": "line",
                    "data": {"datasets": [{"data": [1, 2, 3]}]}
                }
            }
        }
        
        overall_validation_working = True
        
        for resource_type, test_data in test_cases.items():
            try:
                validate_resource_creation(test_data)
                test_results[resource_type] = {
                    "status": "pass",
                    "error": None
                }
            except Exception as e:
                test_results[resource_type] = {
                    "status": "fail",
                    "error": str(e)
                }
                overall_validation_working = False
        
        # Test patch validation
        try:
            patch_test_data = {
                "ops": [
                    {"op": "replace", "path": "/payload/title", "value": "Updated Title"}
                ]
            }
            validate_patch_operations(patch_test_data)
            test_results["patch_operations"] = {
                "status": "pass",
                "error": None
            }
        except Exception as e:
            test_results["patch_operations"] = {
                "status": "fail",
                "error": str(e)
            }
            overall_validation_working = False
        
        # Test invalid data rejection
        try:
            invalid_data = {
                "tenantId": "test",
                "sessionId": "test-session",
                "agentId": "test-agent",
                "name": "test-invalid",
                "type": "card",
                "payload": {}  # Missing required title
            }
            validate_resource_creation(invalid_data)
            # If this doesn't raise an exception, validation is not working
            test_results["invalid_data_rejection"] = {
                "status": "fail",
                "error": "Validation should have failed but didn't"
            }
            overall_validation_working = False
        except ValidationError:
            # This is expected - validation should reject invalid data
            test_results["invalid_data_rejection"] = {
                "status": "pass",
                "error": None
            }
        except Exception as e:
            test_results["invalid_data_rejection"] = {
                "status": "fail",
                "error": f"Unexpected error: {str(e)}"
            }
            overall_validation_working = False
        
        return JSONResponse(content={
            "status": "healthy" if overall_validation_working else "unhealthy",
            "validation_enforced": overall_validation_working,
            "test_results": test_results,
            "stats": validation_stats,
            "middleware_active": True,  # Middleware is configured in main.py
            "validation_points": [
                "Resource creation (POST /mcp-ui/resources)",
                "Resource updates (PATCH /mcp-ui/resources/{id})",
                "Patch operations validation",
                "Repository layer validation",
                "Middleware request validation"
            ],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Validation health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.post("/validation/test")
async def test_validation(
    request: Request,
    test_data: Dict[str, Any]
) -> JSONResponse:
    """
    Test JSON schema validation with provided data
    
    Allows testing of validation rules without creating actual resources.
    """
    try:
        # Extract and validate JWT token for admin access
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Determine test type
        test_type = test_data.get("type", "create")
        test_payload = test_data.get("data", {})
        
        validation_result = {
            "test_type": test_type,
            "validation_passed": False,
            "validation_error": None,
            "validated_data": None
        }
        
        try:
            if test_type == "create":
                validated = validate_resource_creation(test_payload)
                validation_result["validated_data"] = validated.model_dump()
            elif test_type == "patch":
                current_resource_data = test_data.get("current_resource")
                if current_resource_data:
                    current_resource = UIResource(**current_resource_data)
                    validated = validate_patch_operations(test_payload, current_resource)
                else:
                    validated = validate_patch_operations(test_payload)
                validation_result["validated_data"] = validated.model_dump()
            else:
                raise ValueError(f"Unsupported test type: {test_type}")
            
            validation_result["validation_passed"] = True
            
        except (ValidationError, ValueError) as e:
            validation_result["validation_error"] = str(e)
        
        return JSONResponse(content={
            "result": validation_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation test failed: {e}")
        raise HTTPException(status_code=500, detail="Validation test failed")


@router.get("/websocket/stats")
async def websocket_stats(
    request: Request,
    detailed: bool = Query(False, description="Include detailed statistics")
) -> JSONResponse:
    """
    WebSocket system statistics
    
    Provides detailed statistics about WebSocket connections and performance.
    Requirements: 3.1, 3.2, 3.3
    """
    try:
        # Extract and validate JWT token for admin access
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Check for admin scope (optional - could be restricted)
        # For now, allow any authenticated user to view stats
        
        from ..services.websocket_init import get_websocket_system
        
        websocket_system = get_websocket_system()
        stats = websocket_system.get_statistics()
        
        if not detailed:
            # Return summary stats only
            summary = {
                "websocket_connections": stats.get("websocket_manager", {}).get("total_connections", 0),
                "active_topics": stats.get("websocket_manager", {}).get("total_topics", 0),
                "events_sent": stats.get("event_broadcaster", {}).get("events_sent", 0),
                "hydrations_performed": stats.get("hydration_service", {}).get("hydrations_performed", 0),
                "system_healthy": stats.get("system_status", {}).get("started", False)
            }
            return JSONResponse(content=summary)
        
        # Return detailed stats
        stats["timestamp"] = datetime.now(timezone.utc).isoformat()
        return JSONResponse(content=stats)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get WebSocket stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get WebSocket statistics")


@router.get("/hydrate/{tenant_id}/{session_id}")
async def hydrate_session(
    tenant_id: str,
    session_id: str,
    request: Request,
    agent_id: Optional[str] = Query(None, description="Filter by specific agent"),
    resource_types: Optional[str] = Query(None, description="Comma-separated list of resource types"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tags"),
    include_expired: bool = Query(False, description="Include expired resources"),
    since_timestamp: Optional[str] = Query(None, description="Get incremental updates since timestamp"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Maximum number of resources to return")
) -> JSONResponse:
    """
    Hydration endpoint for existing resources
    
    Provides initial state loading and incremental updates for WebSocket connections.
    Supports connection recovery and state synchronization.
    
    Requirements: 3.3
    """
    try:
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Validate tenant access
        if not validate_tenant_access(jwt_claims, tenant_id, session_id, "read"):
            raise HTTPException(
                status_code=403, 
                detail=f"Missing scope: ui:read:{tenant_id}:{session_id}"
            )
        
        # Parse query parameters
        resource_type_list = None
        if resource_types:
            resource_type_list = [rt.strip() for rt in resource_types.split(",") if rt.strip()]
        
        tag_list = None
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        
        # Use hydration service if available
        try:
            from ..services.hydration_service import get_hydration_service
            from ..services.hydration_service import HydrationRequest
            
            hydration_service = get_hydration_service()
            
            # Create hydration request
            hydration_request = HydrationRequest(
                tenant_id=tenant_id,
                session_id=session_id,
                agent_id=agent_id,
                resource_types=resource_type_list,
                tags=tag_list,
                include_expired=include_expired,
                since_timestamp=since_timestamp
            )
            
            # Perform hydration
            response = await hydration_service.hydrate_connection(hydration_request)
            
            # Apply limit if specified
            if limit and len(response.resources) > limit:
                response.resources = response.resources[:limit]
                response.filtered_count = len(response.resources)
            
            return JSONResponse(content=response.model_dump())
            
        except Exception as e:
            logger.warning(f"Hydration service failed, falling back to direct query: {e}")
            
            # Fallback to direct resource query
            return await _fallback_hydration(
                tenant_id, session_id, agent_id, resource_type_list, 
                tag_list, include_expired, since_timestamp, limit
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hydration failed for {tenant_id}/{session_id}: {e}")
        raise HTTPException(status_code=500, detail="Hydration failed")


async def _fallback_hydration(
    tenant_id: str,
    session_id: str,
    agent_id: Optional[str],
    resource_types: Optional[List[str]],
    tags: Optional[List[str]],
    include_expired: bool,
    since_timestamp: Optional[str],
    limit: Optional[int]
) -> JSONResponse:
    """Fallback hydration using direct resource query"""
    
    # Clean up expired resources first
    await cleanup_expired_resources()
    
    # Filter resources
    filtered_resources = []
    
    for resource in ui_resources.values():
        # Basic filters
        if resource.tenantId != tenant_id or resource.sessionId != session_id:
            continue
        
        if agent_id and resource.agentId != agent_id:
            continue
        
        if resource_types and resource.type not in resource_types:
            continue
        
        if tags and not any(tag in resource.tags for tag in tags):
            continue
        
        if not include_expired and resource.is_expired():
            continue
        
        # Timestamp filter for incremental updates
        if since_timestamp:
            try:
                since_dt = datetime.fromisoformat(since_timestamp.replace('Z', '+00:00'))
                updated_dt = datetime.fromisoformat(resource.updatedAt.replace('Z', '+00:00'))
                if updated_dt <= since_dt:
                    continue
            except Exception:
                # If timestamp parsing fails, include the resource
                pass
        
        filtered_resources.append(resource)
    
    # Sort by creation time (newest first)
    filtered_resources.sort(key=lambda r: r.createdAt, reverse=True)
    
    # Apply limit
    if limit and len(filtered_resources) > limit:
        filtered_resources = filtered_resources[:limit]
    
    # Convert to dict format
    resource_dicts = [resource.model_dump() for resource in filtered_resources]
    
    response_data = {
        "tenant_id": tenant_id,
        "session_id": session_id,
        "resources": resource_dicts,
        "total_count": len([r for r in ui_resources.values() if r.tenantId == tenant_id and r.sessionId == session_id]),
        "filtered_count": len(filtered_resources),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_incremental": bool(since_timestamp),
        "since_timestamp": since_timestamp
    }
    
    return JSONResponse(content=response_data)


@router.post("/websocket/recovery/{connection_id}")
async def recover_websocket_connection(
    connection_id: str,
    request: Request,
    since_timestamp: Optional[str] = Query(None, description="Recover updates since timestamp")
) -> JSONResponse:
    """
    WebSocket connection recovery endpoint
    
    Handles connection recovery by providing missed updates for reconnecting clients.
    Implements connection recovery and state synchronization.
    
    Requirements: 3.3
    """
    try:
        # Extract and validate JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = auth_header.split(" ")[1]
        jwt_claims = verify_jwt_token(token)
        
        # Use hydration service for recovery
        try:
            from ..services.hydration_service import get_hydration_service
            from ..services.websocket_manager import websocket_manager
            
            hydration_service = get_hydration_service()
            
            # Attempt connection recovery
            success = await hydration_service.handle_connection_recovery(connection_id, websocket_manager)
            
            if success:
                return JSONResponse(content={
                    "success": True,
                    "message": "Connection recovery successful",
                    "connection_id": connection_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            else:
                # Try incremental updates if recovery failed
                response = await hydration_service.get_incremental_updates(connection_id, since_timestamp)
                
                if response:
                    return JSONResponse(content={
                        "success": True,
                        "message": "Incremental updates provided",
                        "connection_id": connection_id,
                        "updates": response.model_dump(),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                else:
                    raise HTTPException(status_code=404, detail="Connection state not found")
            
        except Exception as e:
            logger.error(f"Connection recovery failed for {connection_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Connection recovery failed: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recovery endpoint failed for {connection_id}: {e}")
        raise HTTPException(status_code=500, detail="Recovery failed")