"""
A2A Client - High-level Client for Agent-to-Agent Communication

Provides a simple, high-level interface for agents to communicate using
the A2A Protocol in HappyOS.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from .constants import (
    AgentCapability,
    MessageType,
    MessagePriority,
    DEFAULT_CONFIG,
    MessagePayload,
    TransportProtocol
)
from .identity import IdentityManager
from .messaging import MessageManager, message_manager
from .transport import TransportLayer, TransportConfig
from .discovery import DiscoveryService, discovery_service
from .auth import AuthenticationManager

logger = logging.getLogger(__name__)


class A2AClient:
    """
    High-level client for A2A Protocol communication.

    Provides a simple interface for agents to:
    - Register capabilities and services
    - Discover other agents
    - Send and receive secure messages
    - Manage agent identity and authentication
    """

    def __init__(self,
                 agent_id: str,
                 capabilities: List[AgentCapability],
                 transport_config: Optional[TransportConfig] = None,
                 storage_path: Optional[str] = None):
        """
        Initialize A2A Client.

        Args:
            agent_id: Unique identifier for this agent
            capabilities: List of capabilities this agent provides
            transport_config: Transport layer configuration
            storage_path: Path for storing identity and configuration data
        """
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.storage_path = storage_path or f"./data/a2a/{agent_id}"

        # Core components
        self.identity_manager = IdentityManager(self.storage_path)
        self.authentication_manager = AuthenticationManager()
        self.transport_config = transport_config or TransportConfig()
        self.transport_layer = TransportLayer(self.transport_config)
        self.message_manager = message_manager

        # Message handlers
        self._message_handlers: Dict[str, Callable] = {}
        self._response_handlers: Dict[str, Callable] = {}

        # Client state
        self._initialized = False
        self._running = False

        logger.info(f"A2A Client initialized for agent: {agent_id}")

    async def initialize(self) -> bool:
        """
        Initialize the A2A client and all its components.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info(f"Initializing A2A Client for agent: {self.agent_id}")

            # Generate or load agent identity
            identity = self.identity_manager.load_agent_identity(self.agent_id)
            if not identity:
                logger.info(f"Generating new identity for agent: {self.agent_id}")
                identity = self.identity_manager.generate_agent_identity(
                    self.agent_id,
                    common_name=f"HappyOS Agent {self.agent_id}"
                )

            if not identity:
                raise Exception("Failed to generate or load agent identity")

            # Initialize transport layer
            transport_success = await self.transport_layer.initialize()
            if not transport_success:
                logger.warning("Transport layer initialization failed")

            # Register with discovery service
            services = [cap.value for cap in self.capabilities]
            discovery_success = await discovery_service.register_agent(
                self.agent_id,
                self.capabilities,
                metadata={
                    "transport_protocol": self.transport_config.protocol.value,
                    "transport_host": self.transport_config.host,
                    "transport_port": self.transport_config.port,
                    "initialized_at": datetime.utcnow().isoformat()
                }
            )

            # Start message handler if transport is available
            if transport_success:
                await self.transport_layer.start_server(self._handle_incoming_message)

            self._initialized = True

            logger.info(f"A2A Client initialized successfully for agent: {self.agent_id}")
            return True

        except Exception as e:
            logger.error(f"A2A Client initialization failed: {e}")
            return False

    async def shutdown(self):
        """Shutdown the A2A client gracefully."""
        try:
            logger.info(f"Shutting down A2A Client for agent: {self.agent_id}")

            self._running = False

            # Unregister from discovery service
            await discovery_service.unregister_agent(self.agent_id)

            # Shutdown transport layer
            await self.transport_layer.shutdown()

            logger.info(f"A2A Client shutdown completed for agent: {self.agent_id}")

        except Exception as e:
            logger.error(f"Error during A2A Client shutdown: {e}")

    async def send_message(self,
                         recipient_id: str,
                         action: str,
                         parameters: Optional[Dict[str, Any]] = None,
                         priority: MessagePriority = MessagePriority.NORMAL,
                         timeout: int = 30) -> Dict[str, Any]:
        """
        Send a message to another agent.

        Args:
            recipient_id: ID of the recipient agent
            action: Action to perform
            parameters: Action parameters
            priority: Message priority
            timeout: Response timeout in seconds

        Returns:
            Response from recipient agent
        """
        try:
            if not self._initialized:
                raise Exception("Client not initialized")

            # Create message payload
            payload = {
                "action": action,
                "parameters": parameters or {},
                "sender_id": self.agent_id,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Create message
            message = self.message_manager.create_message(
                sender_id=self.agent_id,
                recipient_id=recipient_id,
                message_type=MessageType.REQUEST,
                payload=payload,
                priority=priority
            )

            # Get recipient's public key for encryption
            recipient_identity = self.identity_manager.load_agent_identity(recipient_id)
            if not recipient_identity:
                raise Exception(f"No identity found for recipient: {recipient_id}")

            sender_identity = self.identity_manager.load_agent_identity(self.agent_id)
            if not sender_identity:
                raise Exception("No identity found for sender")

            # Encrypt message
            encrypted_message = self.message_manager.encrypt_message(
                message,
                recipient_identity["public_key"],
                sender_identity["private_key"]
            )

            # Send message
            send_result = await self.transport_layer.send_message(
                recipient_id,
                encrypted_message
            )

            if not send_result["success"]:
                return {
                    "success": False,
                    "error": send_result["error"]
                }

            # Wait for response (simplified implementation)
            # In production, this would use proper async response handling
            response_data = send_result.get("response", {})

            return {
                "success": True,
                "response": response_data,
                "message_id": message["header"]["message_id"]
            }

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def broadcast_message(self,
                              action: str,
                              parameters: Optional[Dict[str, Any]] = None,
                              priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """
        Broadcast a message to all agents with specific capability.

        Args:
            action: Action to perform
            parameters: Action parameters
            priority: Message priority

        Returns:
            Broadcast results
        """
        try:
            if not self._initialized:
                raise Exception("Client not initialized")

            # Find agents that can handle this action
            # For now, we'll broadcast to all agents (in production, use capability matching)
            agents = await discovery_service.discover_agents(min_agents=1)

            if not agents:
                return {
                    "success": False,
                    "error": "No agents available for broadcast"
                }

            # Create broadcast message
            payload = {
                "action": action,
                "parameters": parameters or {},
                "sender_id": self.agent_id,
                "broadcast": True,
                "timestamp": datetime.utcnow().isoformat()
            }

            message = self.message_manager.create_notification_message(
                sender_id=self.agent_id,
                notification_type=action,
                notification_data=payload,
                priority=priority
            )

            # Send to all agents (simplified - in production, use proper broadcasting)
            results = []
            for agent in agents[:5]:  # Limit to first 5 agents for demo
                agent_id = agent["agent_id"]
                try:
                    result = await self.send_message(
                        agent_id,
                        action,
                        parameters,
                        priority
                    )
                    results.append({
                        "agent_id": agent_id,
                        "success": result["success"],
                        "response": result.get("response")
                    })
                except Exception as e:
                    results.append({
                        "agent_id": agent_id,
                        "success": False,
                        "error": str(e)
                    })

            successful_sends = sum(1 for r in results if r["success"])

            return {
                "success": successful_sends > 0,
                "total_agents": len(results),
                "successful_sends": successful_sends,
                "results": results
            }

        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def discover_agents(self,
                            capability: Optional[AgentCapability] = None,
                            min_agents: int = 1) -> List[Dict[str, Any]]:
        """
        Discover other agents.

        Args:
            capability: Required capability (optional)
            min_agents: Minimum number of agents to find

        Returns:
            List of discovered agent records
        """
        try:
            if not self._initialized:
                raise Exception("Client not initialized")

            agents = await discovery_service.discover_agents(
                capability=capability,
                min_agents=min_agents
            )

            return agents

        except Exception as e:
            logger.error(f"Agent discovery failed: {e}")
            return []

    async def register_message_handler(self, action: str, handler: Callable):
        """
        Register a handler for incoming messages.

        Args:
            action: Action to handle
            handler: Async function to handle the action
        """
        self._message_handlers[action] = handler
        logger.debug(f"Registered handler for action: {action}")

    async def register_response_handler(self, message_id: str, handler: Callable):
        """
        Register a handler for message responses.

        Args:
            message_id: Message ID to handle response for
            handler: Async function to handle the response
        """
        self._response_handlers[message_id] = handler
        logger.debug(f"Registered response handler for message: {message_id}")

    async def _handle_incoming_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming messages from other agents.

        Args:
            message: Incoming message

        Returns:
            Response to send back
        """
        try:
            # Validate message
            if not self.message_manager.validate_message(message):
                return {
                    "success": False,
                    "error": "Invalid message format"
                }

            # Decrypt message if encrypted
            if message.get("metadata", {}).get("encrypted", False):
                # In production, load appropriate keys for decryption
                # For now, assume message is not encrypted for this demo
                pass

            # Extract action and parameters
            payload = message.get("payload", {})
            action = payload.get("action")
            parameters = payload.get("parameters", {})

            # Find handler for action
            handler = self._message_handlers.get(action)
            if not handler:
                return {
                    "success": False,
                    "error": f"No handler registered for action: {action}"
                }

            # Execute handler
            try:
                response_payload = await handler(parameters)

                # Create response message
                response = self.message_manager.create_response_message(
                    message,
                    response_payload,
                    success=True
                )

                return response

            except Exception as handler_error:
                logger.error(f"Message handler error for action {action}: {handler_error}")

                error_response = self.message_manager.create_response_message(
                    message,
                    {},
                    success=False,
                    error_message=str(handler_error)
                )

                return error_response

        except Exception as e:
            logger.error(f"Error handling incoming message: {e}")
            return {
                "success": False,
                "error": f"Message processing error: {str(e)}"
            }

    def get_client_status(self) -> Dict[str, Any]:
        """Get client status and statistics."""
        return {
            "agent_id": self.agent_id,
            "capabilities": [cap.value for cap in self.capabilities],
            "initialized": self._initialized,
            "running": self._running,
            "transport_config": {
                "protocol": self.transport_config.protocol.value,
                "host": self.transport_config.host,
                "port": self.transport_config.port,
                "enable_tls": self.transport_config.enable_tls
            },
            "registered_handlers": len(self._message_handlers),
            "pending_responses": len(self._response_handlers),
            "transport_stats": self.transport_layer.get_transport_statistics(),
            "identity_info": self.identity_manager.get_identity_statistics() if self._initialized else None
        }


class SimpleA2AAgent(A2AClient):
    """
    Simple A2A agent implementation for basic use cases.

    Extends A2AClient with common message handlers and utilities.
    """

    def __init__(self, agent_id: str, capabilities: List[AgentCapability]):
        super().__init__(agent_id, capabilities)

        # Common handlers
        self._setup_default_handlers()

    def _setup_default_handlers(self):
        """Setup default message handlers."""
        # These would be implemented based on specific agent needs
        pass

    async def handle_status_request(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle status request from other agents."""
        return {
            "status": "active",
            "agent_id": self.agent_id,
            "capabilities": [cap.value for cap in self.capabilities],
            "timestamp": datetime.utcnow().isoformat()
        }

    async def handle_capability_query(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle capability query from other agents."""
        requested_capability = parameters.get("capability")

        if requested_capability:
            has_capability = requested_capability in [cap.value for cap in self.capabilities]
            return {
                "capability": requested_capability,
                "available": has_capability,
                "agent_id": self.agent_id
            }
        else:
            return {
                "capabilities": [cap.value for cap in self.capabilities],
                "agent_id": self.agent_id
            }


# Example usage and test functions
async def create_test_agent(agent_id: str = "test_agent") -> A2AClient:
    """Create a test agent for development and testing."""
    client = SimpleA2AAgent(
        agent_id,
        [AgentCapability.GENERAL, AgentCapability.ANALYSIS]
    )

    # Register common handlers
    await client.register_message_handler("status", client.handle_status_request)
    await client.register_message_handler("capabilities", client.handle_capability_query)

    return client