"""
MCP Agent SDK - Client Library for Rapid Startup Deployment

This SDK enables MCP servers to easily connect to the central MCP UI Hub platform.
It provides standardized methods for:
- Agent registration and discovery
- UI resource publishing and management
- Real-time updates and WebSocket connections
- Platform-as-a-service integration

This is a key component for rapid startup deployment and ecosystem control.

Requirements: 1.4, 6.1, 6.5
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4
import urllib.parse

import aiohttp
import websockets
from pydantic import BaseModel, Field

from ..observability import get_logger

logger = get_logger(__name__)


class UIResource(BaseModel):
    """UI Resource model for the MCP Agent SDK"""
    tenantId: str = Field(..., description="Tenant ID for multi-tenant isolation")
    sessionId: str = Field(..., description="Session ID for context")
    agentId: str = Field(..., description="Agent ID")
    id: str = Field(..., description="Resource ID in mm:// format")
    type: str = Field(..., description="Resource type (card, list, form, chart)")
    version: str = Field(default="2025-10-21", description="Schema version")
    payload: Dict[str, Any] = Field(..., description="Resource payload")
    tags: List[str] = Field(default_factory=list, description="Resource tags")
    ttlSeconds: Optional[int] = Field(None, description="Time to live in seconds")
    idempotencyKey: Optional[str] = Field(None, description="Idempotency key")


class MCPAgentClient:
    """
    MCP Agent Client SDK for connecting to the central MCP UI Hub platform
    
    This client enables rapid startup deployment by providing a standardized
    interface for MCP servers to integrate with the central platform.
    """
    
    def __init__(
        self,
        hub_base_url: str,
        agent_id: str,
        tenant_id: str,
        jwt_token: str,
        agent_info: Optional[Dict[str, Any]] = None
    ):
        self.hub_base_url = hub_base_url.rstrip('/')
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.jwt_token = jwt_token
        self.agent_info = agent_info or {}
        
        self.session = None
        self.websocket = None
        self.websocket_task = None
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Default headers for API requests
        self.headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()
    
    async def initialize(self):
        """Initialize the MCP Agent Client"""
        try:
            self.session = aiohttp.ClientSession(headers=self.headers)
            
            # Register agent with the platform
            await self.register_agent()
            
            logger.info(f"MCP Agent Client initialized for {self.agent_id} in tenant {self.tenant_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP Agent Client: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            # Stop WebSocket connection
            if self.websocket_task:
                self.websocket_task.cancel()
                try:
                    await self.websocket_task
                except asyncio.CancelledError:
                    pass
            
            if self.websocket:
                await self.websocket.close()
            
            # Close HTTP session
            if self.session:
                await self.session.close()
            
            logger.info(f"MCP Agent Client cleaned up for {self.agent_id}")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    # === Agent Registration and Discovery ===
    
    async def register_agent(self) -> bool:
        """Register agent with the central platform for standardized server discovery"""
        try:
            registration_data = {
                "agentId": self.agent_id,
                "tenantId": self.tenant_id,
                "name": self.agent_info.get("name", self.agent_id),
                "description": self.agent_info.get("description", f"MCP Agent {self.agent_id}"),
                "version": self.agent_info.get("version", "1.0.0"),
                "capabilities": self.agent_info.get("capabilities", []),
                "endpoints": self.agent_info.get("endpoints", {}),
                "healthCheckUrl": self.agent_info.get("healthCheckUrl")
            }
            
            async with self.session.post(
                f"{self.hub_base_url}/mcp-ui/agents/register",
                json=registration_data
            ) as response:
                if response.status == 200:
                    logger.info(f"Successfully registered agent {self.agent_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to register agent: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error registering agent: {e}")
            return False
    
    async def send_heartbeat(self) -> bool:
        """Send heartbeat to maintain agent registration"""
        try:
            async with self.session.post(
                f"{self.hub_base_url}/mcp-ui/agents/{self.tenant_id}/{self.agent_id}/heartbeat"
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return False
    
    async def start_heartbeat_task(self, interval_seconds: int = 30):
        """Start automatic heartbeat task"""
        async def heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    await self.send_heartbeat()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
        
        self.heartbeat_task = asyncio.create_task(heartbeat_loop())
    
    # === UI Resource Management ===
    
    async def create_ui_resource(
        self,
        session_id: str,
        resource_name: str,
        resource_type: str,
        payload: Dict[str, Any],
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        idempotency_key: Optional[str] = None
    ) -> Optional[UIResource]:
        """
        Create UI resource on the central platform
        
        This enables automatic UI resource publishing for rapid startup deployment.
        """
        try:
            resource_id = f"mm://{self.tenant_id}/{session_id}/{self.agent_id}/{resource_name}"
            
            resource_data = {
                "tenantId": self.tenant_id,
                "sessionId": session_id,
                "agentId": self.agent_id,
                "id": resource_id,
                "type": resource_type,
                "version": "2025-10-21",
                "payload": payload,
                "tags": tags or [],
                "ttlSeconds": ttl_seconds,
                "idempotencyKey": idempotency_key
            }
            
            async with self.session.post(
                f"{self.hub_base_url}/mcp-ui/resources",
                json=resource_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.debug(f"Created UI resource {resource_id}")
                    return UIResource(**result)
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create UI resource: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error creating UI resource: {e}")
            return None
    
    async def update_ui_resource(
        self,
        resource_id: str,
        patch_operations: List[Dict[str, Any]]
    ) -> Optional[UIResource]:
        """
        Update UI resource using JSON Patch operations
        
        Enables real-time UI updates through standardized patch operations.
        """
        try:
            encoded_resource_id = urllib.parse.quote(resource_id, safe='')
            
            patch_data = {"ops": patch_operations}
            
            async with self.session.patch(
                f"{self.hub_base_url}/mcp-ui/resources/{encoded_resource_id}",
                json=patch_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.debug(f"Updated UI resource {resource_id}")
                    return UIResource(**result)
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to update UI resource: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error updating UI resource: {e}")
            return None
    
    async def delete_ui_resource(self, resource_id: str) -> bool:
        """Delete UI resource from the central platform"""
        try:
            encoded_resource_id = urllib.parse.quote(resource_id, safe='')
            
            async with self.session.delete(
                f"{self.hub_base_url}/mcp-ui/resources/{encoded_resource_id}"
            ) as response:
                if response.status == 200:
                    logger.debug(f"Deleted UI resource {resource_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to delete UI resource: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error deleting UI resource: {e}")
            return False
    
    async def get_ui_resources(
        self,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> List[UIResource]:
        """Get UI resources with optional filtering"""
        try:
            params = {"tenantId": self.tenant_id}
            if session_id:
                params["sessionId"] = session_id
            if agent_id:
                params["agentId"] = agent_id
            
            async with self.session.get(
                f"{self.hub_base_url}/mcp-ui/resources",
                params=params
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    return [UIResource(**resource) for resource in results]
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get UI resources: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting UI resources: {e}")
            return []
    
    # === Convenience Methods for Common UI Resource Types ===
    
    async def create_card(
        self,
        session_id: str,
        name: str,
        title: str,
        content: str,
        status: str = "info",
        actions: Optional[List[Dict[str, Any]]] = None,
        ttl_seconds: Optional[int] = None
    ) -> Optional[UIResource]:
        """Create a card UI resource"""
        payload = {
            "title": title,
            "content": content,
            "status": status,
            "actions": actions or []
        }
        
        return await self.create_ui_resource(
            session_id=session_id,
            resource_name=name,
            resource_type="card",
            payload=payload,
            tags=["card"],
            ttl_seconds=ttl_seconds
        )
    
    async def create_list(
        self,
        session_id: str,
        name: str,
        title: str,
        items: List[str],
        item_type: str = "text",
        ttl_seconds: Optional[int] = None
    ) -> Optional[UIResource]:
        """Create a list UI resource"""
        payload = {
            "title": title,
            "items": items,
            "itemType": item_type
        }
        
        return await self.create_ui_resource(
            session_id=session_id,
            resource_name=name,
            resource_type="list",
            payload=payload,
            tags=["list"],
            ttl_seconds=ttl_seconds
        )
    
    async def create_chart(
        self,
        session_id: str,
        name: str,
        title: str,
        chart_type: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None
    ) -> Optional[UIResource]:
        """Create a chart UI resource"""
        payload = {
            "title": title,
            "chartType": chart_type,
            "data": data,
            "options": options or {}
        }
        
        return await self.create_ui_resource(
            session_id=session_id,
            resource_name=name,
            resource_type="chart",
            payload=payload,
            tags=["chart"],
            ttl_seconds=ttl_seconds
        )
    
    async def update_card_content(self, resource_id: str, new_content: str) -> Optional[UIResource]:
        """Update card content using JSON Patch"""
        patch_ops = [
            {"op": "replace", "path": "/payload/content", "value": new_content},
            {"op": "replace", "path": "/updatedAt", "value": datetime.now(timezone.utc).isoformat()}
        ]
        
        return await self.update_ui_resource(resource_id, patch_ops)
    
    async def update_list_items(self, resource_id: str, new_items: List[str]) -> Optional[UIResource]:
        """Update list items using JSON Patch"""
        patch_ops = [
            {"op": "replace", "path": "/payload/items", "value": new_items},
            {"op": "replace", "path": "/updatedAt", "value": datetime.now(timezone.utc).isoformat()}
        ]
        
        return await self.update_ui_resource(resource_id, patch_ops)
    
    # === Real-time WebSocket Connection ===
    
    async def connect_websocket(self, session_id: str):
        """Connect to WebSocket for real-time updates"""
        try:
            topic = f"ui.{self.tenant_id}.{session_id}"
            ws_url = f"{self.hub_base_url.replace('http', 'ws')}/mcp-ui/ws?topic={topic}"
            
            self.websocket = await websockets.connect(
                ws_url,
                extra_headers={"Authorization": f"Bearer {self.jwt_token}"}
            )
            
            # Start WebSocket message handling task
            self.websocket_task = asyncio.create_task(self._handle_websocket_messages())
            
            logger.info(f"Connected to WebSocket for topic {topic}")
            
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
    
    async def _handle_websocket_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    event_data = json.loads(message)
                    event_type = event_data.get("type")
                    
                    # Call registered event handlers
                    if event_type in self.event_handlers:
                        for handler in self.event_handlers[event_type]:
                            try:
                                await handler(event_data)
                            except Exception as e:
                                logger.error(f"Error in event handler: {e}")
                    
                    logger.debug(f"Received WebSocket event: {event_type}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    def on_event(self, event_type: str, handler: Callable):
        """Register event handler for WebSocket events"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    # === Platform Health and Status ===
    
    async def get_platform_health(self) -> Optional[Dict[str, Any]]:
        """Get platform health status"""
        try:
            async with self.session.get(f"{self.hub_base_url}/mcp-ui/health") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting platform health: {e}")
            return None
    
    async def get_tenant_info(self) -> Optional[Dict[str, Any]]:
        """Get tenant configuration information"""
        try:
            async with self.session.get(f"{self.hub_base_url}/mcp-ui/tenants") as response:
                if response.status == 200:
                    tenants_data = await response.json()
                    return tenants_data.get("tenants", {}).get(self.tenant_id)
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting tenant info: {e}")
            return None


# === Utility Functions for Rapid Startup Deployment ===

async def create_startup_agent(
    hub_base_url: str,
    tenant_id: str,
    agent_id: str,
    jwt_token: str,
    agent_info: Dict[str, Any]
) -> MCPAgentClient:
    """
    Create and initialize MCP Agent Client for rapid startup deployment
    
    This is a convenience function that handles the complete setup process
    for new startup MCP servers connecting to the central platform.
    """
    client = MCPAgentClient(
        hub_base_url=hub_base_url,
        agent_id=agent_id,
        tenant_id=tenant_id,
        jwt_token=jwt_token,
        agent_info=agent_info
    )
    
    await client.initialize()
    return client


def generate_jwt_token_for_agent(
    agent_id: str,
    tenant_id: str,
    scopes: List[str],
    secret_key: str,
    algorithm: str = "HS256",
    expires_hours: int = 24
) -> str:
    """
    Generate JWT token for MCP agent with appropriate scopes
    
    This enables platform-as-a-service infrastructure by providing
    standardized authentication for MCP servers.
    """
    import jwt
    from datetime import timedelta
    
    payload = {
        "sub": f"agent-{agent_id}",
        "iss": "mcp-ui-hub",
        "aud": "mcp-ui-hub",
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        "iat": datetime.now(timezone.utc),
        "scopes": scopes,
        "tenantId": tenant_id,
        "agentId": agent_id,
        "type": "access"
    }
    
    return jwt.encode(payload, secret_key, algorithm=algorithm)