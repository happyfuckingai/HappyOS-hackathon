"""
MCP Client - Model Context Protocol Client for HappyOS SDK

Extends the existing A2A client to support MCP protocol communication
with standardized headers, reply-to semantics, and async callbacks.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass

from .a2a_client import A2AClient, A2ATransport
from .exceptions import A2AError, ServiceUnavailableError
from .unified_observability import get_observability_manager, ObservabilityContext

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Agent types in the HappyOS ecosystem."""
    AGENT_SVEA = "agent_svea"
    FELICIAS_FINANCE = "felicias_finance"
    MEETMIND = "meetmind"
    COMMUNICATIONS_AGENT = "communications_agent"


@dataclass
class MCPHeaders:
    """Standardized MCP headers across all agent systems."""
    tenant_id: str
    trace_id: str
    conversation_id: str
    reply_to: str
    auth_sig: str
    caller: str
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for message headers."""
        return {
            "tenant-id": self.tenant_id,
            "trace-id": self.trace_id,
            "conversation-id": self.conversation_id,
            "reply-to": self.reply_to,
            "auth-sig": self.auth_sig,
            "caller": self.caller,
            "timestamp": self.timestamp
        }


@dataclass
class MCPResponse:
    """Standardized MCP response format."""
    status: str  # "ack", "success", "error"
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    trace_id: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class MCPTool:
    """Standardized MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    agent_type: AgentType


class MCPClient:
    """
    MCP Client for standardized agent communication.
    
    Provides MCP protocol support with reply-to semantics and async callbacks
    while maintaining compatibility with the existing A2A infrastructure.
    """
    
    def __init__(self, 
                 agent_id: str,
                 agent_type: AgentType,
                 a2a_client: A2AClient,
                 tenant_id: str = "default"):
        """
        Initialize MCP client.
        
        Args:
            agent_id: Unique identifier for this agent
            agent_type: Type of agent
            a2a_client: Underlying A2A client for transport
            tenant_id: Tenant ID for multi-tenant deployments
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.a2a_client = a2a_client
        self.tenant_id = tenant_id
        
        # MCP-specific handlers
        self.tool_handlers: Dict[str, Callable] = {}
        self.callback_handlers: Dict[str, Callable] = {}
        
        # Active conversations and traces
        self.active_traces: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"MCP Client initialized for {agent_type.value}: {agent_id}")
    
    async def initialize(self) -> bool:
        """Initialize the MCP client."""
        try:
            # Initialize underlying A2A client
            success = await self.a2a_client.initialize()
            if not success:
                return False
            
            # Register MCP-specific message handlers
            await self._register_mcp_handlers()
            
            logger.info(f"MCP Client initialized successfully for {self.agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"MCP Client initialization failed: {e}")
            return False
    
    async def _register_mcp_handlers(self):
        """Register MCP-specific message handlers."""
        # Register handler for MCP tool calls
        await self.a2a_client.register_message_handler("mcp_tool_call", self._handle_mcp_tool_call)
        
        # Register handler for MCP callbacks
        await self.a2a_client.register_message_handler("mcp_callback", self._handle_mcp_callback)
        
        # Register handler for MCP tool discovery
        await self.a2a_client.register_message_handler("mcp_discover_tools", self._handle_tool_discovery)
    
    async def call_tool(self,
                       target_agent: str,
                       tool_name: str,
                       arguments: Dict[str, Any],
                       headers: MCPHeaders,
                       timeout: float = 30.0) -> MCPResponse:
        """
        Call an MCP tool on another agent.
        
        Args:
            target_agent: Target agent ID
            tool_name: Name of the tool to call
            arguments: Tool arguments
            headers: MCP headers with trace info and reply-to
            timeout: Request timeout in seconds
            
        Returns:
            MCP response (usually immediate ACK)
        """
        # Get observability manager
        observability = get_observability_manager("mcp_client", self.agent_type.value)
        start_time = datetime.utcnow()
        
        try:
            # Create MCP tool call message
            message_payload = {
                "action": "mcp_tool_call",
                "tool_name": tool_name,
                "arguments": arguments,
                "mcp_headers": headers.to_dict(),
                "sender_agent_type": self.agent_type.value,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Store trace information for correlation
            self.active_traces[headers.trace_id] = {
                "conversation_id": headers.conversation_id,
                "target_agent": target_agent,
                "tool_name": tool_name,
                "started_at": start_time,
                "reply_to": headers.reply_to
            }
            
            # Send via A2A client
            response = await self.a2a_client.send_request(
                recipient_id=target_agent,
                action="mcp_tool_call",
                data=message_payload,
                timeout=timeout
            )
            
            # Calculate duration
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if not response.get("success", False):
                # Log failed MCP operation
                await observability.log_mcp_operation(
                    operation_type="tool_call",
                    target_agent=target_agent,
                    tool_name=tool_name,
                    trace_id=headers.trace_id,
                    conversation_id=headers.conversation_id,
                    tenant_id=headers.tenant_id,
                    success=False,
                    duration_ms=duration_ms,
                    error=Exception(response.get('error', 'Unknown error'))
                )
                
                return MCPResponse(
                    status="error",
                    message=f"Tool call failed: {response.get('error', 'Unknown error')}",
                    error_code="TOOL_CALL_FAILED",
                    trace_id=headers.trace_id
                )
            
            # Log successful MCP operation
            await observability.log_mcp_operation(
                operation_type="tool_call",
                target_agent=target_agent,
                tool_name=tool_name,
                trace_id=headers.trace_id,
                conversation_id=headers.conversation_id,
                tenant_id=headers.tenant_id,
                success=True,
                duration_ms=duration_ms
            )
            
            # Parse response
            response_data = response.get("response", {})
            return MCPResponse(
                status=response_data.get("status", "ack"),
                message=response_data.get("message", "Tool call initiated"),
                data=response_data.get("data"),
                trace_id=headers.trace_id
            )
            
        except Exception as e:
            # Calculate duration for error case
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Log failed MCP operation
            await observability.log_mcp_operation(
                operation_type="tool_call",
                target_agent=target_agent,
                tool_name=tool_name,
                trace_id=headers.trace_id,
                conversation_id=headers.conversation_id,
                tenant_id=headers.tenant_id,
                success=False,
                duration_ms=duration_ms,
                error=e
            )
            
            logger.error(f"MCP tool call failed: {e}")
            return MCPResponse(
                status="error",
                message=f"Tool call error: {str(e)}",
                error_code="TOOL_CALL_ERROR",
                trace_id=headers.trace_id
            )
    
    async def send_callback(self,
                           reply_to: str,
                           result: Dict[str, Any],
                           headers: MCPHeaders) -> bool:
        """
        Send async callback result to reply-to endpoint.
        
        Args:
            reply_to: Reply-to endpoint (e.g., "mcp://meetmind/ingest_result")
            result: Callback result data
            headers: MCP headers for correlation
            
        Returns:
            Success status
        """
        # Get observability manager
        observability = get_observability_manager("mcp_client", self.agent_type.value)
        start_time = datetime.utcnow()
        
        try:
            # Parse reply-to endpoint
            if not reply_to.startswith("mcp://"):
                raise ValueError(f"Invalid reply-to format: {reply_to}")
            
            # Extract target agent and tool from reply-to
            # Format: mcp://agent_id/tool_name
            reply_parts = reply_to[6:].split("/", 1)
            if len(reply_parts) != 2:
                raise ValueError(f"Invalid reply-to format: {reply_to}")
            
            target_agent, target_tool = reply_parts
            
            # Create callback message
            callback_payload = {
                "action": "mcp_callback",
                "source_agent": self.agent_id,
                "source_agent_type": self.agent_type.value,
                "target_tool": target_tool,
                "result": result,
                "mcp_headers": headers.to_dict(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Send callback via A2A client
            response = await self.a2a_client.send_request(
                recipient_id=target_agent,
                action="mcp_callback",
                data=callback_payload
            )
            
            # Calculate duration
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            success = response.get("success", False)
            
            # Log MCP callback operation
            await observability.log_mcp_operation(
                operation_type="callback",
                target_agent=target_agent,
                tool_name=target_tool,
                trace_id=headers.trace_id,
                conversation_id=headers.conversation_id,
                tenant_id=headers.tenant_id,
                success=success,
                duration_ms=duration_ms,
                error=None if success else Exception(response.get('error', 'Unknown error'))
            )
            
            if not success:
                logger.error(f"Callback failed: {response.get('error', 'Unknown error')}")
            
            return success
            
        except Exception as e:
            # Calculate duration for error case
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Log failed MCP callback operation
            await observability.log_mcp_operation(
                operation_type="callback",
                target_agent="unknown",
                tool_name="unknown",
                trace_id=headers.trace_id,
                conversation_id=headers.conversation_id,
                tenant_id=headers.tenant_id,
                success=False,
                duration_ms=duration_ms,
                error=e
            )
            
            logger.error(f"Failed to send MCP callback: {e}")
            return False
    
    async def register_tool(self, tool: MCPTool, handler: Callable):
        """
        Register an MCP tool with its handler.
        
        Args:
            tool: MCP tool definition
            handler: Async function to handle tool calls
        """
        self.tool_handlers[tool.name] = handler
        logger.debug(f"Registered MCP tool: {tool.name}")
    
    async def register_callback_handler(self, tool_name: str, handler: Callable):
        """
        Register a callback handler for receiving async results.
        
        Args:
            tool_name: Name of the tool that receives callbacks
            handler: Async function to handle callbacks
        """
        self.callback_handlers[tool_name] = handler
        logger.debug(f"Registered MCP callback handler: {tool_name}")
    
    async def discover_tools(self, target_agent: str) -> List[MCPTool]:
        """
        Discover available tools on another agent.
        
        Args:
            target_agent: Target agent ID
            
        Returns:
            List of available MCP tools
        """
        try:
            response = await self.a2a_client.send_request(
                recipient_id=target_agent,
                action="mcp_discover_tools",
                data={
                    "requesting_agent": self.agent_id,
                    "requesting_agent_type": self.agent_type.value
                }
            )
            
            if not response.get("success", False):
                logger.error(f"Tool discovery failed: {response.get('error')}")
                return []
            
            tools_data = response.get("response", {}).get("tools", [])
            tools = []
            
            for tool_data in tools_data:
                try:
                    tool = MCPTool(
                        name=tool_data["name"],
                        description=tool_data["description"],
                        input_schema=tool_data["input_schema"],
                        output_schema=tool_data["output_schema"],
                        agent_type=AgentType(tool_data["agent_type"])
                    )
                    tools.append(tool)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Invalid tool definition: {e}")
            
            return tools
            
        except Exception as e:
            logger.error(f"Tool discovery failed: {e}")
            return []
    
    async def _handle_mcp_tool_call(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP tool calls."""
        try:
            tool_name = parameters.get("tool_name")
            arguments = parameters.get("arguments", {})
            mcp_headers_dict = parameters.get("mcp_headers", {})
            
            # Parse MCP headers
            mcp_headers = MCPHeaders(
                tenant_id=mcp_headers_dict.get("tenant-id"),
                trace_id=mcp_headers_dict.get("trace-id"),
                conversation_id=mcp_headers_dict.get("conversation-id"),
                reply_to=mcp_headers_dict.get("reply-to"),
                auth_sig=mcp_headers_dict.get("auth-sig"),
                caller=mcp_headers_dict.get("caller"),
                timestamp=mcp_headers_dict.get("timestamp")
            )
            
            # Validate headers
            if not all([mcp_headers.tenant_id, mcp_headers.trace_id, mcp_headers.reply_to]):
                return {
                    "status": "error",
                    "message": "Missing required MCP headers",
                    "error_code": "INVALID_HEADERS"
                }
            
            # Find tool handler
            handler = self.tool_handlers.get(tool_name)
            if not handler:
                return {
                    "status": "error",
                    "message": f"Tool not found: {tool_name}",
                    "error_code": "TOOL_NOT_FOUND"
                }
            
            # Return immediate ACK
            ack_response = {
                "status": "ack",
                "message": f"Tool call received: {tool_name}",
                "trace_id": mcp_headers.trace_id
            }
            
            # Process tool call asynchronously
            asyncio.create_task(self._process_tool_call_async(
                handler, arguments, mcp_headers, tool_name
            ))
            
            return ack_response
            
        except Exception as e:
            logger.error(f"Error handling MCP tool call: {e}")
            return {
                "status": "error",
                "message": f"Tool call processing error: {str(e)}",
                "error_code": "PROCESSING_ERROR"
            }
    
    async def _process_tool_call_async(self,
                                     handler: Callable,
                                     arguments: Dict[str, Any],
                                     mcp_headers: MCPHeaders,
                                     tool_name: str):
        """Process tool call asynchronously and send callback."""
        try:
            # Execute tool handler
            result = await handler(arguments, mcp_headers)
            
            # Send callback with result
            callback_success = await self.send_callback(
                reply_to=mcp_headers.reply_to,
                result={
                    "tool_name": tool_name,
                    "status": "success",
                    "data": result,
                    "agent_type": self.agent_type.value,
                    "agent_id": self.agent_id
                },
                headers=mcp_headers
            )
            
            if not callback_success:
                logger.error(f"Failed to send callback for tool: {tool_name}")
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            
            # Send error callback
            await self.send_callback(
                reply_to=mcp_headers.reply_to,
                result={
                    "tool_name": tool_name,
                    "status": "error",
                    "error": str(e),
                    "agent_type": self.agent_type.value,
                    "agent_id": self.agent_id
                },
                headers=mcp_headers
            )
    
    async def _handle_mcp_callback(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP callbacks."""
        try:
            target_tool = parameters.get("target_tool")
            result = parameters.get("result", {})
            mcp_headers_dict = parameters.get("mcp_headers", {})
            
            # Parse MCP headers
            mcp_headers = MCPHeaders(
                tenant_id=mcp_headers_dict.get("tenant-id"),
                trace_id=mcp_headers_dict.get("trace-id"),
                conversation_id=mcp_headers_dict.get("conversation-id"),
                reply_to=mcp_headers_dict.get("reply-to"),
                auth_sig=mcp_headers_dict.get("auth-sig"),
                caller=mcp_headers_dict.get("caller"),
                timestamp=mcp_headers_dict.get("timestamp")
            )
            
            # Find callback handler
            handler = self.callback_handlers.get(target_tool)
            if not handler:
                logger.warning(f"No callback handler for tool: {target_tool}")
                return {
                    "status": "error",
                    "message": f"No callback handler for tool: {target_tool}"
                }
            
            # Process callback
            await handler(result, mcp_headers)
            
            return {
                "status": "success",
                "message": "Callback processed"
            }
            
        except Exception as e:
            logger.error(f"Error handling MCP callback: {e}")
            return {
                "status": "error",
                "message": f"Callback processing error: {str(e)}"
            }
    
    async def _handle_tool_discovery(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool discovery requests."""
        try:
            tools = []
            
            for tool_name, handler in self.tool_handlers.items():
                # Get tool metadata (this would be stored when registering tools)
                # For now, return basic info
                tools.append({
                    "name": tool_name,
                    "description": f"Tool: {tool_name}",
                    "agent_type": self.agent_type.value,
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"}
                })
            
            return {
                "status": "success",
                "tools": tools,
                "agent_id": self.agent_id,
                "agent_type": self.agent_type.value
            }
            
        except Exception as e:
            logger.error(f"Tool discovery error: {e}")
            return {
                "status": "error",
                "message": f"Tool discovery error: {str(e)}"
            }
    
    def create_mcp_headers(self,
                          tenant_id: str,
                          reply_to: str,
                          trace_id: str = None,
                          conversation_id: str = None) -> MCPHeaders:
        """
        Create standardized MCP headers.
        
        Args:
            tenant_id: Tenant ID
            reply_to: Reply-to endpoint
            trace_id: Optional trace ID (generated if not provided)
            conversation_id: Optional conversation ID (generated if not provided)
            
        Returns:
            MCPHeaders instance
        """
        return MCPHeaders(
            tenant_id=tenant_id,
            trace_id=trace_id or str(uuid.uuid4()),
            conversation_id=conversation_id or str(uuid.uuid4()),
            reply_to=reply_to,
            auth_sig="",  # Would be generated based on authentication
            caller=self.agent_id
        )
    
    async def shutdown(self):
        """Shutdown the MCP client."""
        try:
            # Clean up active traces
            self.active_traces.clear()
            
            # Shutdown underlying A2A client
            await self.a2a_client.disconnect()
            
            logger.info(f"MCP Client shutdown completed for {self.agent_id}")
            
        except Exception as e:
            logger.error(f"Error during MCP Client shutdown: {e}")


def create_mcp_client(agent_id: str,
                     agent_type: AgentType,
                     transport_type: str = "inprocess",
                     endpoint: Optional[str] = None,
                     tenant_id: str = "default") -> MCPClient:
    """
    Factory function to create MCP client with appropriate transport.
    
    Args:
        agent_id: Unique agent identifier
        agent_type: Type of agent
        transport_type: "network" or "inprocess"
        endpoint: Network endpoint (required for network transport)
        tenant_id: Tenant ID for multi-tenant deployments
        
    Returns:
        Configured MCPClient instance
    """
    from .a2a_client import create_a2a_client
    
    # Create underlying A2A client
    a2a_client = create_a2a_client(
        agent_id=agent_id,
        transport_type=transport_type,
        endpoint=endpoint,
        tenant_id=tenant_id
    )
    
    # Create MCP client
    return MCPClient(
        agent_id=agent_id,
        agent_type=agent_type,
        a2a_client=a2a_client,
        tenant_id=tenant_id
    )