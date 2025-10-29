"""
MCP Protocol Implementation

Core MCP protocol with message types, headers, and transport abstraction.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Callable, Union

from ...config import Config
from ...exceptions import CommunicationError, ValidationError
from ...security.signing import MCPMessageSigner


class MCPMessageType(Enum):
    """MCP message types."""
    TOOL_CALL = "tool_call"
    CALLBACK = "callback"
    DISCOVER_TOOLS = "discover_tools"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class MCPHeaders:
    """Standardized MCP headers for all messages."""
    
    tenant_id: str
    trace_id: str
    conversation_id: str
    reply_to: str
    caller: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    auth_signature: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        reply_to: str,
        caller: str,
        trace_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> "MCPHeaders":
        """Create headers with auto-generated IDs."""
        return cls(
            tenant_id=tenant_id,
            trace_id=trace_id or str(uuid.uuid4()),
            conversation_id=conversation_id or str(uuid.uuid4()),
            reply_to=reply_to,
            caller=caller
        )
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for serialization."""
        return {
            "tenant-id": self.tenant_id,
            "trace-id": self.trace_id,
            "conversation-id": self.conversation_id,
            "reply-to": self.reply_to,
            "caller": self.caller,
            "timestamp": self.timestamp,
            "auth-signature": self.auth_signature or ""
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "MCPHeaders":
        """Create from dictionary."""
        return cls(
            tenant_id=data["tenant-id"],
            trace_id=data["trace-id"],
            conversation_id=data["conversation-id"],
            reply_to=data["reply-to"],
            caller=data["caller"],
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            auth_signature=data.get("auth-signature")
        )
    
    def validate(self) -> None:
        """Validate required headers."""
        required = ["tenant_id", "trace_id", "reply_to", "caller"]
        for field_name in required:
            if not getattr(self, field_name):
                raise ValidationError(f"Missing required header: {field_name}")


@dataclass
class MCPMessage:
    """MCP message with headers and payload."""
    
    message_type: Union[str, MCPMessageType]
    headers: MCPHeaders
    payload: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Convert string message type to enum."""
        if isinstance(self.message_type, str):
            try:
                self.message_type = MCPMessageType(self.message_type)
            except ValueError:
                raise ValidationError(f"Invalid message type: {self.message_type}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.message_type.value,
            "headers": self.headers.to_dict(),
            "payload": self.payload
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPMessage":
        """Create from dictionary."""
        return cls(
            message_type=data["type"],
            headers=MCPHeaders.from_dict(data["headers"]),
            payload=data.get("payload", {})
        )
    
    def validate(self) -> None:
        """Validate message structure."""
        self.headers.validate()
        
        if not isinstance(self.payload, dict):
            raise ValidationError("Payload must be a dictionary")


@dataclass
class MCPResponse:
    """Standardized MCP response."""
    
    status: str  # "ack", "success", "error"
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    trace_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "status": self.status,
            "message": self.message,
            "timestamp": self.timestamp
        }
        
        if self.data is not None:
            result["data"] = self.data
        if self.error_code:
            result["error_code"] = self.error_code
        if self.trace_id:
            result["trace_id"] = self.trace_id
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPResponse":
        """Create from dictionary."""
        return cls(
            status=data["status"],
            message=data["message"],
            data=data.get("data"),
            error_code=data.get("error_code"),
            trace_id=data.get("trace_id"),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat())
        )


class MCPProtocol:
    """MCP protocol implementation with transport abstraction.
    
    Handles message serialization, validation, signing, and routing.
    """
    
    def __init__(self, config: Config):
        """Initialize protocol.
        
        Args:
            config: SDK configuration
        """
        self.config = config
        self.message_signer = MCPMessageSigner(
            config.security.mcp_signing_key
        ) if config.security.mcp_signing_key else None
        
        # Message handlers
        self._handlers: Dict[str, Callable] = {}
        
        # Transport (would be injected in production)
        self._transport = None
    
    async def initialize(self) -> None:
        """Initialize protocol."""
        # Initialize transport layer
        # In production, this would set up network connections
        pass
    
    async def send_message(
        self,
        target_agent: str,
        message: MCPMessage,
        timeout: float = 30.0
    ) -> MCPResponse:
        """Send MCP message to target agent.
        
        Args:
            target_agent: Target agent identifier
            message: MCP message to send
            timeout: Request timeout
            
        Returns:
            MCP response
            
        Raises:
            CommunicationError: If send fails
        """
        try:
            # Validate message
            message.validate()
            
            # Sign message if signing enabled
            if self.message_signer and self.config.security.mcp_verify_signatures:
                signature = await self.message_signer.sign_message(message)
                message.headers.auth_signature = signature
            
            # Serialize message
            message_data = json.dumps(message.to_dict())
            
            # Send via transport (mock implementation)
            response_data = await self._send_via_transport(
                target_agent, 
                message_data, 
                timeout
            )
            
            # Parse response
            response_dict = json.loads(response_data)
            return MCPResponse.from_dict(response_dict)
            
        except json.JSONDecodeError as e:
            raise CommunicationError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise CommunicationError(f"Message send failed: {e}")
    
    async def register_handler(
        self, 
        message_type: Union[str, MCPMessageType], 
        handler: Callable
    ) -> None:
        """Register message handler.
        
        Args:
            message_type: Message type to handle
            handler: Async handler function
        """
        if isinstance(message_type, MCPMessageType):
            message_type = message_type.value
        
        self._handlers[message_type] = handler
    
    async def handle_message(self, message_data: str) -> str:
        """Handle incoming message.
        
        Args:
            message_data: Serialized message data
            
        Returns:
            Serialized response data
        """
        try:
            # Parse message
            message_dict = json.loads(message_data)
            message = MCPMessage.from_dict(message_dict)
            
            # Verify signature if required
            if (self.message_signer and 
                self.config.security.mcp_verify_signatures and
                message.headers.auth_signature):
                
                is_valid = await self.message_signer.verify_message(
                    message, 
                    message.headers.auth_signature
                )
                
                if not is_valid:
                    response = MCPResponse(
                        status="error",
                        message="Invalid message signature",
                        error_code="INVALID_SIGNATURE"
                    )
                    return json.dumps(response.to_dict())
            
            # Find handler
            handler = self._handlers.get(message.message_type.value)
            if not handler:
                response = MCPResponse(
                    status="error",
                    message=f"No handler for message type: {message.message_type.value}",
                    error_code="NO_HANDLER"
                )
                return json.dumps(response.to_dict())
            
            # Execute handler
            response = await handler(message)
            
            # Ensure response is MCPResponse
            if not isinstance(response, MCPResponse):
                response = MCPResponse(
                    status="error",
                    message="Handler returned invalid response type",
                    error_code="INVALID_HANDLER_RESPONSE"
                )
            
            return json.dumps(response.to_dict())
            
        except json.JSONDecodeError:
            response = MCPResponse(
                status="error",
                message="Invalid JSON message",
                error_code="INVALID_JSON"
            )
            return json.dumps(response.to_dict())
        
        except Exception as e:
            response = MCPResponse(
                status="error",
                message=f"Message handling error: {str(e)}",
                error_code="HANDLER_ERROR"
            )
            return json.dumps(response.to_dict())
    
    async def _send_via_transport(
        self, 
        target_agent: str, 
        message_data: str, 
        timeout: float
    ) -> str:
        """Send message via transport layer.
        
        This is a mock implementation. In production, this would
        use actual network transport (HTTP, WebSocket, etc.).
        """
        # Mock response for development
        await asyncio.sleep(0.01)  # Simulate network delay
        
        return json.dumps({
            "status": "ack",
            "message": "Message received",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def shutdown(self) -> None:
        """Shutdown protocol."""
        self._handlers.clear()
        # Close transport connections