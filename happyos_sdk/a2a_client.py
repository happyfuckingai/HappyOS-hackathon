"""
A2A Client - Agent-to-Agent Communication Client

Provides the main interface for agents to communicate with each other
and with the HappyOS core platform via the A2A protocol.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from enum import Enum

from .exceptions import A2AError, ServiceUnavailableError

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """A2A Message types."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    DISCOVERY = "discovery"


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class A2ATransport(ABC):
    """Abstract base class for A2A transport implementations."""
    
    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message and return response."""
        pass
    
    @abstractmethod
    async def register_handler(self, message_type: str, handler: Callable):
        """Register a message handler."""
        pass
    
    @abstractmethod
    async def start(self):
        """Start the transport."""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the transport."""
        pass


class NetworkTransport(A2ATransport):
    """Network-based A2A transport for distributed deployment."""
    
    def __init__(self, endpoint: str, auth_token: Optional[str] = None):
        """
        Initialize network transport.
        
        Args:
            endpoint: A2A router endpoint URL
            auth_token: Authentication token for secure communication
        """
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.handlers: Dict[str, Callable] = {}
        self.session = None
        
    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via HTTP/WebSocket to A2A router."""
        try:
            # In real implementation, this would use aiohttp or similar
            # to send HTTP requests to the A2A router
            
            # Mock implementation for now
            await asyncio.sleep(0.01)  # Simulate network delay
            
            return {
                "success": True,
                "response_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "transport": "network"
            }
            
        except Exception as e:
            logger.error(f"Network transport send failed: {e}")
            raise A2AError(f"Failed to send message via network transport: {e}")
    
    async def register_handler(self, message_type: str, handler: Callable):
        """Register message handler for network transport."""
        self.handlers[message_type] = handler
        logger.debug(f"Registered network handler for: {message_type}")
    
    async def start(self):
        """Start network transport (establish connections, etc.)."""
        logger.info(f"Starting network transport to {self.endpoint}")
        # In real implementation, establish WebSocket connection or HTTP session
        
    async def stop(self):
        """Stop network transport."""
        logger.info("Stopping network transport")
        # In real implementation, close connections


class InProcessTransport(A2ATransport):
    """In-process A2A transport for same-process deployment."""
    
    def __init__(self):
        """Initialize in-process transport."""
        self.handlers: Dict[str, Callable] = {}
        self.message_queue = asyncio.Queue()
        self.running = False
        
    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via in-process queue."""
        try:
            # Route message to appropriate handler
            message_type = message.get("header", {}).get("message_type")
            handler = self.handlers.get(message_type)
            
            if handler:
                response = await handler(message)
                return response
            else:
                # Forward to default handler or A2A router
                return {
                    "success": True,
                    "response_id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat(),
                    "transport": "in_process"
                }
                
        except Exception as e:
            logger.error(f"In-process transport send failed: {e}")
            raise A2AError(f"Failed to send message via in-process transport: {e}")
    
    async def register_handler(self, message_type: str, handler: Callable):
        """Register message handler for in-process transport."""
        self.handlers[message_type] = handler
        logger.debug(f"Registered in-process handler for: {message_type}")
    
    async def start(self):
        """Start in-process transport."""
        self.running = True
        logger.info("Started in-process transport")
    
    async def stop(self):
        """Stop in-process transport."""
        self.running = False
        logger.info("Stopped in-process transport")


class A2AClient:
    """
    Main A2A client for agent communication.
    
    Provides a unified interface for agents to communicate with other agents
    and HappyOS core services via the A2A protocol, regardless of transport.
    """
    
    def __init__(self, 
                 agent_id: str,
                 transport: A2ATransport,
                 tenant_id: Optional[str] = None):
        """
        Initialize A2A client.
        
        Args:
            agent_id: Unique identifier for this agent
            transport: Transport implementation (Network or InProcess)
            tenant_id: Tenant ID for multi-tenant deployments
        """
        self.agent_id = agent_id
        self.transport = transport
        self.tenant_id = tenant_id or "default"
        
        self.message_handlers: Dict[str, Callable] = {}
        self.is_connected = False
        
        logger.info(f"A2A Client initialized for agent: {agent_id}")
    
    async def connect(self):
        """Connect to the A2A network."""
        try:
            await self.transport.start()
            self.is_connected = True
            
            # Register for discovery and health checks
            await self._register_core_handlers()
            
            logger.info(f"A2A Client connected for agent: {self.agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to connect A2A client: {e}")
            raise A2AError(f"Connection failed: {e}")
    
    async def disconnect(self):
        """Disconnect from the A2A network."""
        try:
            await self.transport.stop()
            self.is_connected = False
            logger.info(f"A2A Client disconnected for agent: {self.agent_id}")
            
        except Exception as e:
            logger.error(f"Failed to disconnect A2A client: {e}")
    
    async def send_request(self, 
                          recipient_id: str,
                          action: str,
                          data: Dict[str, Any],
                          priority: MessagePriority = MessagePriority.NORMAL,
                          timeout: float = 30.0) -> Dict[str, Any]:
        """
        Send a request message to another agent or service.
        
        Args:
            recipient_id: ID of the recipient agent/service
            action: Action to perform
            data: Request data
            priority: Message priority
            timeout: Request timeout in seconds
            
        Returns:
            Response from the recipient
        """
        if not self.is_connected:
            raise A2AError("A2A client not connected")
        
        message = self._create_message(
            recipient_id=recipient_id,
            message_type=MessageType.REQUEST,
            payload={
                "action": action,
                "data": data,
                "tenant_id": self.tenant_id
            },
            priority=priority
        )
        
        try:
            response = await asyncio.wait_for(
                self.transport.send_message(message),
                timeout=timeout
            )
            return response
            
        except asyncio.TimeoutError:
            raise A2AError(f"Request timeout after {timeout}s")
        except Exception as e:
            raise A2AError(f"Request failed: {e}")
    
    async def send_notification(self,
                               recipient_id: str,
                               event_type: str,
                               data: Dict[str, Any],
                               priority: MessagePriority = MessagePriority.NORMAL):
        """
        Send a notification message (fire-and-forget).
        
        Args:
            recipient_id: ID of the recipient agent/service
            event_type: Type of event/notification
            data: Notification data
            priority: Message priority
        """
        if not self.is_connected:
            raise A2AError("A2A client not connected")
        
        message = self._create_message(
            recipient_id=recipient_id,
            message_type=MessageType.NOTIFICATION,
            payload={
                "event_type": event_type,
                "data": data,
                "tenant_id": self.tenant_id
            },
            priority=priority
        )
        
        try:
            await self.transport.send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            # Don't raise for notifications - they're fire-and-forget
    
    async def register_handler(self, action: str, handler: Callable):
        """
        Register a handler for incoming messages.
        
        Args:
            action: Action type to handle
            handler: Async function to handle the message
        """
        self.message_handlers[action] = handler
        await self.transport.register_handler(action, handler)
        logger.debug(f"Registered handler for action: {action}")
    
    async def discover_agents(self, 
                             capabilities: Optional[List[str]] = None,
                             agent_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Discover other agents in the network.
        
        Args:
            capabilities: Required capabilities to filter by
            agent_type: Agent type to filter by
            
        Returns:
            List of discovered agents
        """
        discovery_data = {
            "capabilities": capabilities,
            "agent_type": agent_type,
            "requesting_agent": self.agent_id
        }
        
        try:
            response = await self.send_request(
                recipient_id="discovery_service",
                action="discover_agents",
                data=discovery_data
            )
            
            return response.get("agents", [])
            
        except Exception as e:
            logger.error(f"Agent discovery failed: {e}")
            return []
    
    async def get_agent_health(self, agent_id: str) -> Dict[str, Any]:
        """
        Get health status of another agent.
        
        Args:
            agent_id: ID of the agent to check
            
        Returns:
            Health status information
        """
        try:
            response = await self.send_request(
                recipient_id=agent_id,
                action="health_check",
                data={}
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Health check failed for agent {agent_id}: {e}")
            return {"status": "unknown", "error": str(e)}
    
    def _create_message(self,
                       recipient_id: str,
                       message_type: MessageType,
                       payload: Dict[str, Any],
                       priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """Create a properly formatted A2A message."""
        message_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        return {
            "header": {
                "message_id": message_id,
                "sender_id": self.agent_id,
                "recipient_id": recipient_id,
                "message_type": message_type.value,
                "priority": priority.value,
                "timestamp": timestamp,
                "tenant_id": self.tenant_id
            },
            "payload": payload
        }
    
    async def _register_core_handlers(self):
        """Register core message handlers."""
        await self.register_handler("health_check", self._handle_health_check)
        await self.register_handler("ping", self._handle_ping)
    
    async def _handle_health_check(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health check requests."""
        return {
            "status": "healthy",
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
            "connected": self.is_connected
        }
    
    async def _handle_ping(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping requests."""
        return {
            "pong": True,
            "agent_id": self.agent_id,
            "timestamp": datetime.utcnow().isoformat()
        }


# Factory functions for creating transports
def create_network_transport(endpoint: str, auth_token: Optional[str] = None) -> NetworkTransport:
    """Create a network transport for distributed deployment."""
    return NetworkTransport(endpoint, auth_token)


def create_inprocess_transport() -> InProcessTransport:
    """Create an in-process transport for same-process deployment."""
    return InProcessTransport()


def create_a2a_client(agent_id: str, 
                     transport_type: str = "inprocess",
                     endpoint: Optional[str] = None,
                     auth_token: Optional[str] = None,
                     tenant_id: Optional[str] = None) -> A2AClient:
    """
    Factory function to create A2A client with appropriate transport.
    
    Args:
        agent_id: Unique agent identifier
        transport_type: "network" or "inprocess"
        endpoint: Network endpoint (required for network transport)
        auth_token: Authentication token (for network transport)
        tenant_id: Tenant ID for multi-tenant deployments
        
    Returns:
        Configured A2AClient instance
    """
    if transport_type == "network":
        if not endpoint:
            raise ValueError("Endpoint required for network transport")
        transport = create_network_transport(endpoint, auth_token)
    elif transport_type == "inprocess":
        transport = create_inprocess_transport()
    else:
        raise ValueError(f"Unknown transport type: {transport_type}")
    
    return A2AClient(agent_id, transport, tenant_id)