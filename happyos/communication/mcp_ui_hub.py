"""
MCP UI Hub Client - Platform Integration for HappyOS SDK

This module provides integration with the central MCP UI Hub platform,
enabling rapid startup deployment and ecosystem control for MCP agents.

Based on backend/services/platform/mcp_agent_sdk.py but adapted for
the HappyOS SDK architecture with enterprise patterns.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from uuid import uuid4
import urllib.parse
from dataclasses import dataclass

from ..config import SDKConfig
from ..exceptions import HappyOSSDKError, MCPError


@dataclass
class UIResource:
    """UI Resource model for the MCP UI Hub."""
    tenant_id: str
    session_id: str
    agent_id: str
    id: str
    type: str
    version: str = "2025-10-21"
    payload: Dict[str, Any] = None
    tags: List[str] = None
    ttl_seconds: Optional[int] = None
    idempotency_key: Optional[str] = None
    
    def __post_init__(self):
        if self.payload is None:
            self.payload = {}
        if self.tags is None:
            self.tags = []


class MCPUIHubClient:
    """
    MCP UI Hub Client for connecting to the central platform.
    
    This client enables rapid startup deployment by providing a standardized
    interface for MCP servers to integrate with the central platform.
    
    Features:
    - Agent registration and discovery
    - UI resource publishing and management
    - Real-time updates via WebSocket
    - Platform-as-a-service integration
    
    Example:
        >>> client = MCPUIHubClient(
        ...     hub_base_url="https://api.happyos.com",
        ...     agent_id="my-agent",
        ...     tenant_id="tenant-123",
        ...     jwt_token="eyJ..."
        ... )
        >>> 
        >>> async with client:
        ...     await client.create_card(
        ...         session_id="session-456",
        ...         name="status",
        ...         title="Agent Status",
        ...         content="Running successfully"
        ...     )
    """
    
    def __init__(
        self,
        hub_base_url: str,
        agent_id: str,
        tenant_id: str,
        jwt_token: str,
        agent_info: Optional[Dict[str, Any]] = None,
        sdk_config: Optional[SDKConfig] = None
    ):
        """Initialize MCP UI Hub client.
        
        Args:
            hub_base_url: Base URL of the MCP UI Hub
            agent_id: Unique agent identifier
            tenant_id: Tenant identifier for multi-tenancy
            jwt_token: JWT token for authentication
            agent_info: Optional agent metadata
            sdk_config: SDK configuration
        """
        self.hub_base_url = hub_base_url.rstrip('/')
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.jwt_token = jwt_token
        self.agent_info = agent_info or {}
        self.sdk_config = sdk_config or SDKConfig.from_environment()
        
        # Initialize logging
        try:
            from ..observability import get_logger
            self.logger = get_logger(f"mcp_ui_hub.{agent_id}")
        except ImportError:
            self.logger = logging.getLogger(f"mcp_ui_hub.{agent_id}")
        
        # Initialize metrics
        try:
            from ..observability import MetricsCollector
            self.metrics = MetricsCollector(f"mcp_ui_hub_{agent_id}")
        except ImportError:
            self.metrics = None
        
        # Client state
        self.session = None
        self.websocket = None
        self.websocket_task = None
        self.heartbeat_task = None
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Default headers for API requests
        self.headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "User-Agent": f"HappyOS-SDK/1.0.0 Agent/{agent_id}"
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
    
    async def initialize(self) -> None:
        """Initialize the MCP UI Hub client."""
        try:
            # Import aiohttp dynamically to avoid hard dependency
            try:
                import aiohttp
            except ImportError:
                raise HappyOSSDKError(
                    "aiohttp is required for MCP UI Hub client. "
                    "Install with: pip install aiohttp"
                )
            
            self.session = aiohttp.ClientSession(headers=self.headers)
            
            # Register agent with the platform
            success = await self.register_agent()
            if not success:
                raise MCPError("Failed to register agent with MCP UI Hub")
            
            # Start heartbeat task
            await self.start_heartbeat_task()
            
            self.logger.info(f"MCP UI Hub client initialized for {self.agent_id}")
            
            if self.metrics:
                self.metrics.increment('mcp_ui_hub_initializations')
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP UI Hub client: {e}")
            raise MCPError(f"Initialization failed: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            # Stop heartbeat task
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
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
            
            self.logger.info(f"MCP UI Hub client cleaned up for {self.agent_id}")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    # === Agent Registration and Discovery ===
    
    async def register_agent(self) -> bool:
        """Register agent with the central platform."""
        try:
            registration_data = {
                "agentId": self.agent_id,
                "tenantId": self.tenant_id,
                "name": self.agent_info.get("name", self.agent_id),
                "description": self.agent_info.get("description", f"HappyOS Agent {self.agent_id}"),
                "version": self.agent_info.get("version", "1.0.0"),
                "capabilities": self.agent_info.get("capabilities", []),
                "endpoints": self.agent_info.get("endpoints", {}),
                "healthCheckUrl": self.agent_info.get("healthCheckUrl"),
                "sdk_version": "1.0.0"
            }
            
            async with self.session.post(
                f"{self.hub_base_url}/mcp-ui/agents/register",
                json=registration_data
            ) as response:
                if response.status == 200:
                    self.logger.info(f"Successfully registered agent {self.agent_id}")
                    
                    if self.metrics:
                        self.metrics.increment('agent_registrations_success')
                    
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to register agent: {response.status} - {error_text}")
                    
                    if self.metrics:
                        self.metrics.increment('agent_registrations_failed')
                    
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error registering agent: {e}")
            
            if self.metrics:
                self.metrics.increment('agent_registrations_error')
            
            return False
    
    async def send_heartbeat(self) -> bool:
        """Send heartbeat to maintain agent registration."""
        try:
            async with self.session.post(
                f"{self.hub_base_url}/mcp-ui/agents/{self.tenant_id}/{self.agent_id}/heartbeat"
            ) as response:
                success = response.status == 200
                
                if self.metrics:
                    if success:
                        self.metrics.increment('heartbeats_success')
                    else:
                        self.metrics.increment('heartbeats_failed')
                
                return success
                
        except Exception as e:
            self.logger.error(f"Error sending heartbeat: {e}")
            
            if self.metrics:
                self.metrics.increment('heartbeats_error')
            
            return False
    
    async def start_heartbeat_task(self, interval_seconds: int = 30) -> None:
        """Start automatic heartbeat task."""
        async def heartbeat_loop():
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    await self.send_heartbeat()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Heartbeat error: {e}")
        
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
        """Create UI resource on the central platform."""
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
                    self.logger.debug(f"Created UI resource {resource_id}")
                    
                    if self.metrics:
                        self.metrics.increment(f'ui_resources_created.{resource_type}')
                    
                    return UIResource(
                        tenant_id=result["tenantId"],
                        session_id=result["sessionId"],
                        agent_id=result["agentId"],
                        id=result["id"],
                        type=result["type"],
                        version=result.get("version", "2025-10-21"),
                        payload=result.get("payload", {}),
                        tags=result.get("tags", []),
                        ttl_seconds=result.get("ttlSeconds"),
                        idempotency_key=result.get("idempotencyKey")
                    )
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create UI resource: {response.status} - {error_text}")
                    
                    if self.metrics:
                        self.metrics.increment(f'ui_resources_create_failed.{resource_type}')
                    
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error creating UI resource: {e}")
            
            if self.metrics:
                self.metrics.increment(f'ui_resources_create_error.{resource_type}')
            
            return None
    
    async def update_ui_resource(
        self,
        resource_id: str,
        patch_operations: List[Dict[str, Any]]
    ) -> Optional[UIResource]:
        """Update UI resource using JSON Patch operations."""
        try:
            encoded_resource_id = urllib.parse.quote(resource_id, safe='')
            
            patch_data = {"ops": patch_operations}
            
            async with self.session.patch(
                f"{self.hub_base_url}/mcp-ui/resources/{encoded_resource_id}",
                json=patch_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.debug(f"Updated UI resource {resource_id}")
                    
                    if self.metrics:
                        self.metrics.increment('ui_resources_updated')
                    
                    return UIResource(
                        tenant_id=result["tenantId"],
                        session_id=result["sessionId"],
                        agent_id=result["agentId"],
                        id=result["id"],
                        type=result["type"],
                        version=result.get("version", "2025-10-21"),
                        payload=result.get("payload", {}),
                        tags=result.get("tags", []),
                        ttl_seconds=result.get("ttlSeconds"),
                        idempotency_key=result.get("idempotencyKey")
                    )
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to update UI resource: {response.status} - {error_text}")
                    
                    if self.metrics:
                        self.metrics.increment('ui_resources_update_failed')
                    
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error updating UI resource: {e}")
            
            if self.metrics:
                self.metrics.increment('ui_resources_update_error')
            
            return None
    
    async def delete_ui_resource(self, resource_id: str) -> bool:
        """Delete UI resource from the central platform."""
        try:
            encoded_resource_id = urllib.parse.quote(resource_id, safe='')
            
            async with self.session.delete(
                f"{self.hub_base_url}/mcp-ui/resources/{encoded_resource_id}"
            ) as response:
                if response.status == 200:
                    self.logger.debug(f"Deleted UI resource {resource_id}")
                    
                    if self.metrics:
                        self.metrics.increment('ui_resources_deleted')
                    
                    return True
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to delete UI resource: {response.status} - {error_text}")
                    
                    if self.metrics:
                        self.metrics.increment('ui_resources_delete_failed')
                    
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error deleting UI resource: {e}")
            
            if self.metrics:
                self.metrics.increment('ui_resources_delete_error')
            
            return False
    
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
        """Create a card UI resource."""
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
        """Create a list UI resource."""
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
        """Create a chart UI resource."""
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
        """Update card content using JSON Patch."""
        patch_ops = [
            {"op": "replace", "path": "/payload/content", "value": new_content},
            {"op": "replace", "path": "/updatedAt", "value": datetime.now(timezone.utc).isoformat()}
        ]
        
        return await self.update_ui_resource(resource_id, patch_ops)
    
    async def update_list_items(self, resource_id: str, new_items: List[str]) -> Optional[UIResource]:
        """Update list items using JSON Patch."""
        patch_ops = [
            {"op": "replace", "path": "/payload/items", "value": new_items},
            {"op": "replace", "path": "/updatedAt", "value": datetime.now(timezone.utc).isoformat()}
        ]
        
        return await self.update_ui_resource(resource_id, patch_ops)
    
    # === Real-time WebSocket Connection ===
    
    async def connect_websocket(self, session_id: str) -> None:
        """Connect to WebSocket for real-time updates."""
        try:
            # Import websockets dynamically to avoid hard dependency
            try:
                import websockets
            except ImportError:
                raise HappyOSSDKError(
                    "websockets is required for real-time updates. "
                    "Install with: pip install websockets"
                )
            
            topic = f"ui.{self.tenant_id}.{session_id}"
            ws_url = f"{self.hub_base_url.replace('http', 'ws')}/mcp-ui/ws?topic={topic}"
            
            self.websocket = await websockets.connect(
                ws_url,
                extra_headers={"Authorization": f"Bearer {self.jwt_token}"}
            )
            
            # Start WebSocket message handling task
            self.websocket_task = asyncio.create_task(self._handle_websocket_messages())
            
            self.logger.info(f"Connected to WebSocket for topic {topic}")
            
            if self.metrics:
                self.metrics.increment('websocket_connections')
            
        except Exception as e:
            self.logger.error(f"Failed to connect WebSocket: {e}")
            raise MCPError(f"WebSocket connection failed: {e}")
    
    async def _handle_websocket_messages(self) -> None:
        """Handle incoming WebSocket messages."""
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
                                self.logger.error(f"Error in event handler: {e}")
                    
                    self.logger.debug(f"Received WebSocket event: {event_type}")
                    
                    if self.metrics:
                        self.metrics.increment(f'websocket_events.{event_type}')
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse WebSocket message: {e}")
                    
        except Exception as e:
            if "websockets" in str(type(e)):
                self.logger.info("WebSocket connection closed")
            else:
                self.logger.error(f"WebSocket error: {e}")
    
    def on_event(self, event_type: str, handler: Callable) -> None:
        """Register event handler for WebSocket events."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    # === Platform Health and Status ===
    
    async def get_platform_health(self) -> Optional[Dict[str, Any]]:
        """Get platform health status."""
        try:
            async with self.session.get(f"{self.hub_base_url}/mcp-ui/health") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
                    
        except Exception as e:
            self.logger.error(f"Error getting platform health: {e}")
            return None


# === Utility Functions ===

async def create_startup_agent_client(
    hub_base_url: str,
    tenant_id: str,
    agent_id: str,
    jwt_token: str,
    agent_info: Dict[str, Any],
    sdk_config: Optional[SDKConfig] = None
) -> MCPUIHubClient:
    """
    Create and initialize MCP UI Hub client for rapid startup deployment.
    
    This is a convenience function that handles the complete setup process
    for new startup MCP servers connecting to the central platform.
    
    Args:
        hub_base_url: Base URL of the MCP UI Hub
        tenant_id: Tenant identifier
        agent_id: Agent identifier
        jwt_token: JWT authentication token
        agent_info: Agent metadata
        sdk_config: Optional SDK configuration
        
    Returns:
        Initialized MCP UI Hub client
        
    Example:
        >>> client = await create_startup_agent_client(
        ...     hub_base_url="https://api.happyos.com",
        ...     tenant_id="startup-123",
        ...     agent_id="my-agent",
        ...     jwt_token="eyJ...",
        ...     agent_info={
        ...         "name": "My Startup Agent",
        ...         "description": "AI agent for startup operations",
        ...         "version": "1.0.0",
        ...         "capabilities": ["data_analysis", "reporting"]
        ...     }
        ... )
    """
    client = MCPUIHubClient(
        hub_base_url=hub_base_url,
        agent_id=agent_id,
        tenant_id=tenant_id,
        jwt_token=jwt_token,
        agent_info=agent_info,
        sdk_config=sdk_config
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
    Generate JWT token for MCP agent with appropriate scopes.
    
    This enables platform-as-a-service infrastructure by providing
    standardized authentication for MCP servers.
    
    Args:
        agent_id: Agent identifier
        tenant_id: Tenant identifier
        scopes: List of permission scopes
        secret_key: JWT signing secret
        algorithm: JWT algorithm (default: HS256)
        expires_hours: Token expiration in hours
        
    Returns:
        JWT token string
        
    Raises:
        HappyOSSDKError: If PyJWT is not available
    """
    try:
        import jwt
    except ImportError:
        raise HappyOSSDKError(
            "PyJWT is required for JWT token generation. "
            "Install with: pip install PyJWT"
        )
    
    from datetime import timedelta
    
    payload = {
        "sub": f"agent-{agent_id}",
        "iss": "happyos-sdk",
        "aud": "mcp-ui-hub",
        "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        "iat": datetime.now(timezone.utc),
        "scopes": scopes,
        "tenantId": tenant_id,
        "agentId": agent_id,
        "type": "access"
    }
    
    return jwt.encode(payload, secret_key, algorithm=algorithm)