"""
MCP Adapter Routes - Integration Layer for MCP Servers

This module provides the integration layer between MCP servers and the central UI Hub platform.
It handles MCP server communication, tool execution, and resource publishing to the UI Hub.

This is part of the central MCP UI Hub platform infrastructure that enables:
- Standardized MCP server integration
- Tool execution and result processing
- Automatic UI resource publishing
- Platform-as-a-service capabilities for rapid startup deployment

Requirements: 1.4, 6.1, 6.5
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..modules.auth import get_current_user
from ..services.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/mcp-adapter", tags=["MCP Adapter"])


class MCPToolCall(BaseModel):
    """MCP tool call request"""
    agentId: str = Field(..., description="Agent ID making the call")
    tenantId: str = Field(..., description="Tenant ID for isolation")
    sessionId: str = Field(..., description="Session ID for context")
    toolName: str = Field(..., description="Name of the MCP tool to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    publishToUI: bool = Field(default=True, description="Whether to publish results to UI Hub")
    resourceType: Optional[str] = Field(None, description="UI resource type for results")
    resourceName: Optional[str] = Field(None, description="UI resource name")


class MCPToolResult(BaseModel):
    """MCP tool execution result"""
    success: bool = Field(...)
    toolName: str = Field(...)
    agentId: str = Field(...)
    tenantId: str = Field(...)
    sessionId: str = Field(...)
    result: Any = Field(...)
    error: Optional[str] = None
    executionTime: float = Field(...)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    publishedResourceId: Optional[str] = None


class MCPServerStatus(BaseModel):
    """MCP server status information"""
    serverId: str = Field(...)
    agentId: str = Field(...)
    tenantId: str = Field(...)
    status: str = Field(...)  # "connected", "disconnected", "error"
    lastSeen: str = Field(...)
    availableTools: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    version: Optional[str] = None


# In-memory storage for MCP server connections (in production, use Redis)
mcp_servers: Dict[str, MCPServerStatus] = {}
tool_execution_history: List[MCPToolResult] = []


async def publish_result_to_ui_hub(
    tool_result: MCPToolResult,
    resource_type: str = "card",
    resource_name: str = None
) -> Optional[str]:
    """
    Publish MCP tool result to UI Hub as a UI resource
    
    This enables automatic UI resource creation from MCP tool execution results,
    providing seamless integration between MCP servers and the UI platform.
    """
    try:
        if not resource_name:
            resource_name = f"{tool_result.toolName}-result"
        
        # Create UI resource ID
        resource_id = f"mm://{tool_result.tenantId}/{tool_result.sessionId}/{tool_result.agentId}/{resource_name}"
        
        # Format result data based on resource type
        if resource_type == "card":
            payload = {
                "title": f"{tool_result.toolName} Result",
                "content": str(tool_result.result),
                "status": "success" if tool_result.success else "error",
                "timestamp": tool_result.timestamp
            }
        elif resource_type == "list":
            if isinstance(tool_result.result, list):
                payload = {
                    "title": f"{tool_result.toolName} Results",
                    "items": [str(item) for item in tool_result.result],
                    "itemType": "text"
                }
            else:
                payload = {
                    "title": f"{tool_result.toolName} Result",
                    "items": [str(tool_result.result)],
                    "itemType": "text"
                }
        elif resource_type == "chart":
            # Assume result contains chart data
            payload = {
                "title": f"{tool_result.toolName} Chart",
                "chartType": "line",
                "data": tool_result.result if isinstance(tool_result.result, dict) else {"value": tool_result.result}
            }
        else:
            # Default to card format
            payload = {
                "title": f"{tool_result.toolName} Result",
                "content": str(tool_result.result),
                "status": "success" if tool_result.success else "error"
            }
        
        # Create UI resource
        ui_resource_data = {
            "tenantId": tool_result.tenantId,
            "sessionId": tool_result.sessionId,
            "agentId": tool_result.agentId,
            "id": resource_id,
            "type": resource_type,
            "version": "2025-10-21",
            "payload": payload,
            "tags": ["mcp-result", tool_result.toolName],
            "ttlSeconds": 3600,  # 1 hour TTL
            "idempotencyKey": f"{tool_result.toolName}-{tool_result.timestamp}"
        }
        
        # TODO: In production, make HTTP request to UI Hub
        # For now, log the resource creation
        logger.info(f"Would publish UI resource: {resource_id}")
        
        return resource_id
        
    except Exception as e:
        logger.error(f"Failed to publish result to UI Hub: {e}")
        return None


@router.post("/tools/execute", response_model=MCPToolResult)
async def execute_mcp_tool(
    tool_call: MCPToolCall,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
) -> MCPToolResult:
    """
    Execute MCP tool and optionally publish results to UI Hub
    
    This is the core integration point between MCP servers and the UI platform,
    enabling standardized tool execution with automatic UI resource publishing.
    """
    start_time = datetime.now(timezone.utc)
    
    try:
        # Validate server connection
        server_key = f"{tool_call.tenantId}:{tool_call.agentId}"
        if server_key not in mcp_servers:
            raise HTTPException(
                status_code=404, 
                detail=f"MCP server not found for agent {tool_call.agentId} in tenant {tool_call.tenantId}"
            )
        
        server_status = mcp_servers[server_key]
        if server_status.status != "connected":
            raise HTTPException(
                status_code=503,
                detail=f"MCP server is not connected (status: {server_status.status})"
            )
        
        # Validate tool availability
        if tool_call.toolName not in server_status.availableTools:
            raise HTTPException(
                status_code=400,
                detail=f"Tool {tool_call.toolName} not available on server {tool_call.agentId}"
            )
        
        # TODO: Execute actual MCP tool call
        # For now, simulate tool execution
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # Simulate different tool results based on tool name
        if tool_call.toolName == "summarize_meeting":
            result = {
                "summary": "Meeting summary generated successfully",
                "topics": ["Project planning", "Budget review", "Next steps"],
                "action_items": ["Review budget proposal", "Schedule follow-up meeting"]
            }
        elif tool_call.toolName == "analyze_costs":
            result = {
                "total_cost": 15420.50,
                "categories": [
                    {"name": "Office supplies", "amount": 2340.25},
                    {"name": "Software licenses", "amount": 8950.00},
                    {"name": "Travel expenses", "amount": 4130.25}
                ]
            }
        elif tool_call.toolName == "get_market_data":
            result = {
                "symbols": [
                    {"symbol": "BTC", "price": 67234.50, "change": "+1.2%"},
                    {"symbol": "OMXS30", "price": 2456.78, "change": "-0.4%"},
                    {"symbol": "USD/SEK", "price": 10.85, "change": "+0.1%"}
                ]
            }
        else:
            result = f"Tool {tool_call.toolName} executed successfully with arguments: {tool_call.arguments}"
        
        # Create tool result
        tool_result = MCPToolResult(
            success=True,
            toolName=tool_call.toolName,
            agentId=tool_call.agentId,
            tenantId=tool_call.tenantId,
            sessionId=tool_call.sessionId,
            result=result,
            executionTime=execution_time
        )
        
        # Store execution history
        tool_execution_history.append(tool_result)
        
        # Publish to UI Hub if requested
        if tool_call.publishToUI:
            resource_type = tool_call.resourceType or "card"
            resource_name = tool_call.resourceName
            
            background_tasks.add_task(
                publish_result_to_ui_hub,
                tool_result,
                resource_type,
                resource_name
            )
        
        logger.info(f"Executed MCP tool {tool_call.toolName} for agent {tool_call.agentId}")
        
        return tool_result
        
    except HTTPException:
        raise
    except Exception as e:
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        error_result = MCPToolResult(
            success=False,
            toolName=tool_call.toolName,
            agentId=tool_call.agentId,
            tenantId=tool_call.tenantId,
            sessionId=tool_call.sessionId,
            result=None,
            error=str(e),
            executionTime=execution_time
        )
        
        tool_execution_history.append(error_result)
        
        logger.error(f"Failed to execute MCP tool {tool_call.toolName}: {e}")
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@router.post("/servers/register")
async def register_mcp_server(
    server_status: MCPServerStatus,
    request: Request
) -> JSONResponse:
    """
    Register MCP server with the adapter
    
    This enables standardized MCP server registration for platform-as-a-service
    infrastructure and rapid startup deployment.
    """
    try:
        server_key = f"{server_status.tenantId}:{server_status.agentId}"
        
        # Update server status
        server_status.lastSeen = datetime.now(timezone.utc).isoformat()
        mcp_servers[server_key] = server_status
        
        logger.info(f"Registered MCP server {server_status.serverId} for agent {server_status.agentId}")
        
        return JSONResponse(content={
            "success": True,
            "message": "MCP server registered successfully",
            "serverId": server_status.serverId,
            "timestamp": server_status.lastSeen
        })
        
    except Exception as e:
        logger.error(f"Failed to register MCP server: {e}")
        raise HTTPException(status_code=500, detail="Failed to register MCP server")


@router.get("/servers", response_model=List[MCPServerStatus])
async def list_mcp_servers(
    tenant_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> List[MCPServerStatus]:
    """
    List registered MCP servers with optional tenant filtering
    
    Supports ecosystem control by providing visibility into all connected MCP servers.
    """
    try:
        servers = list(mcp_servers.values())
        
        if tenant_id:
            servers = [server for server in servers if server.tenantId == tenant_id]
        
        return servers
        
    except Exception as e:
        logger.error(f"Failed to list MCP servers: {e}")
        raise HTTPException(status_code=500, detail="Failed to list MCP servers")


@router.get("/servers/{tenant_id}/{agent_id}/status", response_model=MCPServerStatus)
async def get_mcp_server_status(
    tenant_id: str,
    agent_id: str,
    current_user: dict = Depends(get_current_user)
) -> MCPServerStatus:
    """
    Get specific MCP server status
    
    Provides detailed status information for ecosystem monitoring and health checks.
    """
    try:
        server_key = f"{tenant_id}:{agent_id}"
        
        if server_key not in mcp_servers:
            raise HTTPException(
                status_code=404,
                detail=f"MCP server not found for agent {agent_id} in tenant {tenant_id}"
            )
        
        return mcp_servers[server_key]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP server status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get server status")


@router.post("/servers/{tenant_id}/{agent_id}/heartbeat")
async def mcp_server_heartbeat(
    tenant_id: str,
    agent_id: str,
    request: Request
) -> JSONResponse:
    """
    MCP server heartbeat for health monitoring
    
    Maintains ecosystem control by tracking server health and availability.
    """
    try:
        server_key = f"{tenant_id}:{agent_id}"
        
        if server_key not in mcp_servers:
            raise HTTPException(
                status_code=404,
                detail=f"MCP server not found for agent {agent_id} in tenant {tenant_id}"
            )
        
        # Update heartbeat
        mcp_servers[server_key].lastSeen = datetime.now(timezone.utc).isoformat()
        mcp_servers[server_key].status = "connected"
        
        return JSONResponse(content={
            "status": "ok",
            "timestamp": mcp_servers[server_key].lastSeen
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process MCP server heartbeat: {e}")
        raise HTTPException(status_code=500, detail="Failed to process heartbeat")


@router.get("/tools/history")
async def get_tool_execution_history(
    tenant_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
) -> List[MCPToolResult]:
    """
    Get tool execution history with optional filtering
    
    Provides audit trail and monitoring capabilities for the platform.
    """
    try:
        history = tool_execution_history.copy()
        
        # Apply filters
        if tenant_id:
            history = [result for result in history if result.tenantId == tenant_id]
        
        if agent_id:
            history = [result for result in history if result.agentId == agent_id]
        
        # Sort by timestamp (most recent first) and limit
        history.sort(key=lambda x: x.timestamp, reverse=True)
        
        return history[:limit]
        
    except Exception as e:
        logger.error(f"Failed to get tool execution history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get execution history")


@router.get("/health")
async def adapter_health() -> JSONResponse:
    """
    MCP adapter health check
    
    Provides health status for the MCP integration layer.
    """
    try:
        # Count servers by status
        status_counts = {}
        for server in mcp_servers.values():
            status_counts[server.status] = status_counts.get(server.status, 0) + 1
        
        return JSONResponse(content={
            "status": "healthy",
            "component": "MCP Adapter",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "registered_servers": len(mcp_servers),
                "server_status_counts": status_counts,
                "tool_executions": len(tool_execution_history),
                "supported_tenants": len(set(server.tenantId for server in mcp_servers.values()))
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get adapter health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get adapter health")