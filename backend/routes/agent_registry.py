"""
Agent Registry API Routes

Provides REST API endpoints for agent registration, discovery, and health monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from backend.services.agents.agent_registry_service import agent_registry
from backend.core.a2a.constants import AgentType, AgentCapability
from backend.modules.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/agents", tags=["Agent Registry"])


# Request/Response Models

class AgentRegistrationRequest(BaseModel):
    agent_id: str
    agent_type: str
    capabilities: List[str]
    endpoint: str
    metadata: Optional[Dict[str, Any]] = None


class AgentHeartbeatRequest(BaseModel):
    health_metrics: Optional[Dict[str, Any]] = None


class AgentDiscoveryRequest(BaseModel):
    required_capabilities: Optional[List[str]] = None
    agent_type: Optional[str] = None
    health_status: Optional[str] = None


class AgentRegistrationResponse(BaseModel):
    success: bool
    agent_id: str
    message: Optional[str] = None
    error: Optional[str] = None
    registration_time: Optional[str] = None


class AgentStatusResponse(BaseModel):
    agent_id: str
    agent_type: str
    capabilities: List[str]
    endpoint: str
    status: str
    health_status: str
    last_heartbeat: Optional[str] = None
    failure_count: int
    registered_at: Optional[str] = None
    metadata: Dict[str, Any]
    health_metrics: Dict[str, Any]


class RegistryStatusResponse(BaseModel):
    total_agents: int
    status_distribution: Dict[str, int]
    health_distribution: Dict[str, int]
    type_distribution: Dict[str, int]
    capability_distribution: Dict[str, int]
    registry_uptime: str
    monitoring_active: bool


# API Endpoints

@router.post("/register", response_model=AgentRegistrationResponse)
async def register_agent(
    request: AgentRegistrationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Register a new agent with the registry.
    
    Args:
        request: Agent registration details
        current_user: Authenticated user (for authorization)
        
    Returns:
        Registration result
    """
    try:
        # Validate agent type
        try:
            agent_type = AgentType(request.agent_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent type: {request.agent_type}"
            )
        
        # Validate capabilities
        capabilities = []
        for cap_str in request.capabilities:
            try:
                capabilities.append(AgentCapability(cap_str))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid capability: {cap_str}"
                )
        
        # Register agent
        result = await agent_registry.register_agent(
            agent_id=request.agent_id,
            agent_type=agent_type,
            capabilities=capabilities,
            endpoint=request.endpoint,
            metadata=request.metadata
        )
        
        return AgentRegistrationResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/deregister/{agent_id}")
async def deregister_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Deregister an agent from the registry.
    
    Args:
        agent_id: Agent identifier to deregister
        current_user: Authenticated user (for authorization)
        
    Returns:
        Deregistration result
    """
    try:
        result = await agent_registry.deregister_agent(agent_id)
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heartbeat/{agent_id}")
async def agent_heartbeat(
    agent_id: str,
    request: AgentHeartbeatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Process agent heartbeat.
    
    Args:
        agent_id: Agent identifier
        request: Heartbeat data including health metrics
        current_user: Authenticated user (for authorization)
        
    Returns:
        Heartbeat acknowledgment
    """
    try:
        result = await agent_registry.heartbeat(
            agent_id=agent_id,
            health_metrics=request.health_metrics
        )
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discover")
async def discover_agents(
    request: AgentDiscoveryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Discover agents based on criteria.
    
    Args:
        request: Discovery criteria
        current_user: Authenticated user (for authorization)
        
    Returns:
        List of matching agents
    """
    try:
        # Parse capabilities
        required_capabilities = None
        if request.required_capabilities:
            required_capabilities = []
            for cap_str in request.required_capabilities:
                try:
                    required_capabilities.append(AgentCapability(cap_str))
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid capability: {cap_str}"
                    )
        
        # Parse agent type
        agent_type = None
        if request.agent_type:
            try:
                agent_type = AgentType(request.agent_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid agent type: {request.agent_type}"
                )
        
        # Discover agents
        agents = await agent_registry.discover_agents(
            required_capabilities=required_capabilities,
            agent_type=agent_type,
            health_status=request.health_status
        )
        
        return {
            "agents": agents,
            "total_count": len(agents),
            "discovery_time": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{agent_id}", response_model=AgentStatusResponse)
async def get_agent_status(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed status for a specific agent.
    
    Args:
        agent_id: Agent identifier
        current_user: Authenticated user (for authorization)
        
    Returns:
        Agent status information
    """
    try:
        status = await agent_registry.get_agent_status(agent_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return AgentStatusResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/registry/status", response_model=RegistryStatusResponse)
async def get_registry_status(
    current_user: dict = Depends(get_current_user)
):
    """
    Get overall registry status and statistics.
    
    Args:
        current_user: Authenticated user (for authorization)
        
    Returns:
        Registry status information
    """
    try:
        status = await agent_registry.get_registry_status()
        
        if "error" in status:
            raise HTTPException(status_code=500, detail=status["error"])
        
        return RegistryStatusResponse(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_agents(
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    health_status: Optional[str] = Query(None, description="Filter by health status"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
    current_user: dict = Depends(get_current_user)
):
    """
    List all registered agents with optional filters.
    
    Args:
        agent_type: Optional agent type filter
        health_status: Optional health status filter
        capability: Optional capability filter
        current_user: Authenticated user (for authorization)
        
    Returns:
        List of agents matching filters
    """
    try:
        # Build discovery request
        required_capabilities = [AgentCapability(capability)] if capability else None
        agent_type_enum = AgentType(agent_type) if agent_type else None
        
        # Discover agents
        agents = await agent_registry.discover_agents(
            required_capabilities=required_capabilities,
            agent_type=agent_type_enum,
            health_status=health_status
        )
        
        return {
            "agents": agents,
            "total_count": len(agents),
            "filters": {
                "agent_type": agent_type,
                "health_status": health_status,
                "capability": capability
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities")
async def list_capabilities(
    current_user: dict = Depends(get_current_user)
):
    """
    List all available agent capabilities.
    
    Args:
        current_user: Authenticated user (for authorization)
        
    Returns:
        List of available capabilities
    """
    try:
        capabilities = [
            {
                "name": cap.value,
                "description": f"Agent capability: {cap.value}"
            }
            for cap in AgentCapability
        ]
        
        return {
            "capabilities": capabilities,
            "total_count": len(capabilities)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types")
async def list_agent_types(
    current_user: dict = Depends(get_current_user)
):
    """
    List all available agent types.
    
    Args:
        current_user: Authenticated user (for authorization)
        
    Returns:
        List of available agent types
    """
    try:
        agent_types = [
            {
                "name": agent_type.value,
                "description": f"Agent type: {agent_type.value}"
            }
            for agent_type in AgentType
        ]
        
        return {
            "agent_types": agent_types,
            "total_count": len(agent_types)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint for the registry service itself
@router.get("/registry/health")
async def registry_health_check():
    """
    Health check endpoint for the agent registry service.
    
    Returns:
        Registry service health status
    """
    try:
        # Check if registry is initialized and running
        if agent_registry._health_monitor_task and not agent_registry._health_monitor_task.done():
            return {
                "status": "healthy",
                "service": "agent_registry",
                "timestamp": datetime.utcnow().isoformat(),
                "monitoring_active": True
            }
        else:
            return {
                "status": "degraded",
                "service": "agent_registry",
                "timestamp": datetime.utcnow().isoformat(),
                "monitoring_active": False,
                "message": "Health monitoring not active"
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "agent_registry",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }