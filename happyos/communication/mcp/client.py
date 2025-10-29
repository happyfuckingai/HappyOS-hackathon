"""
MCP Client - Enterprise Model Context Protocol Client

Production-ready MCP client with enterprise patterns including security,
observability, resilience, and tenant isolation.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from .protocol import MCPProtocol, MCPMessage, MCPHeaders, MCPResponse
from .tools import MCPTool, MCPToolRegistry
from ...config import Config
from ...exceptions import CommunicationError, ValidationError
from ...security.tenant import TenantContext
from ...observability.logging import get_logger
from ...observability.metrics import MetricsCollector
from ...resilience.circuit_breaker import CircuitBreaker


class MCPClient:
    """Enterprise MCP Client for agent communication.
    
    Features:
    - Standardized MCP protocol implementation
    - Reply-to semantics with async callbacks
    - Circuit breaker protection
    - Comprehensive observability
    - Tenant isolation
    - Tool discovery and registration
    
    Example:
        >>> client = MCPClient("agent-1", config)
        >>> await client.initialize()
        >>> 
        >>> response = await client.call_tool(
        ...     "agent-2", 
        ...     "analyze_data",
        ...     {"data": [1, 2, 3]},
        ...     headers
        ... )
    """
    
    def __init__(self, agent_id: str, config: Config):
        """Initialize MCP client.
        
        Args:
            agent_id: Unique agent identifier
            config: SDK configuration
        """
        self.agent_id = agent_id
        self.config = config
        
        # Initialize components
        self.logger = get_logger(f"mcp_client.{agent_id}")
        self.metrics = MetricsCollector() if config.observability.enable_metrics else None
        self.protocol = MCPProtocol(config)
        self.tool_registry = MCPToolRegistry()
        
        # Circuit breaker for resilience
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.communication.circuit_breaker_failure_threshold,
            recovery_timeout=config.communication.circuit_breaker_recovery_timeout
        )
        
        # Runtime state
        self._initialized = False
        self._active_traces: Dict[str, Dict[str, Any]] = {}
        self._callback_handlers: Dict[str, Callable] = {}
    
    async def initialize(self) -> bool:
        """Initialize the MCP client.
        
        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True
        
        try:
            # Initialize protocol
            await self.protocol.initialize()
            
            # Register message handlers
            await self._register_handlers()
            
            self._initialized = True
            self.logger.info("MCP client initialized successfully")
            
            if self.metrics:
                self.metrics.increment("mcp.client.initialized")
            
            return True
            
        except Exception as e:
            self.logger.error(f"MCP client initialization failed: {e}")
            if self.metrics:
                self.metrics.increment("mcp.client.init_failed")
            return False
    
    async def call_tool(
        self,
        target_agent: str,
        tool_name: str,
        arguments: Dict[str, Any],
        headers: MCPHeaders,
        timeout: float = 30.0
    ) -> MCPResponse:
        """Call a tool on another agent.
        
        Args:
            target_agent: Target agent identifier
            tool_name: Name of tool to call
            arguments: Tool arguments
            headers: MCP headers with trace info
            timeout: Request timeout
            
        Returns:
            MCP response (usually immediate ACK)
            
        Raises:
            CommunicationError: If call fails
        """
        if not self._initialized:
            raise CommunicationError("MCP client not initialized")
        
        start_time = datetime.utcnow()
        
        try:
            # Store trace for correlation
            self._active_traces[headers.trace_id] = {
                "target_agent": target_agent,
                "tool_name": tool_name,
                "started_at": start_time,
                "reply_to": headers.reply_to
            }
            
            # Create MCP message
            message = MCPMessage(
                message_type="tool_call",
                headers=headers,
                payload={
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "sender": self.agent_id
                }
            )
            
            # Send with circuit breaker protection
            response = await self.circuit_breaker.call(
                self.protocol.send_message,
                target_agent,
                message,
                timeout
            )
            
            # Record metrics
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if self.metrics:
                self.metrics.record_histogram(
                    "mcp.tool_call.duration_ms",
                    duration_ms,
                    tags={"tool": tool_name, "target": target_agent}
                )
                self.metrics.increment(
                    "mcp.tool_call.success",
                    tags={"tool": tool_name}
                )
            
            return response
            
        except Exception as e:
            # Clean up trace on error
            self._active_traces.pop(headers.trace_id, None)
            
            if self.metrics:
                self.metrics.increment(
                    "mcp.tool_call.error",
                    tags={"tool": tool_name, "error": type(e).__name__}
                )
            
            self.logger.error(f"Tool call failed: {e}")
            raise CommunicationError(f"Tool call failed: {e}") from e
    
    async def send_callback(
        self,
        reply_to: str,
        result: Dict[str, Any],
        headers: MCPHeaders
    ) -> bool:
        """Send async callback result.
        
        Args:
            reply_to: Reply-to endpoint (mcp://agent/tool)
            result: Callback result data
            headers: MCP headers for correlation
            
        Returns:
            True if callback sent successfully
        """
        try:
            # Parse reply-to endpoint
            target_agent, target_tool = self._parse_reply_to(reply_to)
            
            # Create callback message
            message = MCPMessage(
                message_type="callback",
                headers=headers,
                payload={
                    "target_tool": target_tool,
                    "result": result,
                    "source_agent": self.agent_id
                }
            )
            
            # Send callback
            await self.protocol.send_message(target_agent, message)
            
            if self.metrics:
                self.metrics.increment("mcp.callback.sent")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send callback: {e}")
            if self.metrics:
                self.metrics.increment("mcp.callback.error")
            return False
    
    def register_tool(self, tool: MCPTool, handler: Callable) -> None:
        """Register a tool with handler.
        
        Args:
            tool: Tool definition
            handler: Async handler function
        """
        self.tool_registry.register(tool, handler)
        self.logger.debug(f"Registered tool: {tool.name}")
    
    def register_callback_handler(self, tool_name: str, handler: Callable) -> None:
        """Register callback handler for receiving results.
        
        Args:
            tool_name: Tool name that receives callbacks
            handler: Async callback handler
        """
        self._callback_handlers[tool_name] = handler
        self.logger.debug(f"Registered callback handler: {tool_name}")
    
    async def discover_tools(self, target_agent: str) -> List[MCPTool]:
        """Discover available tools on another agent.
        
        Args:
            target_agent: Target agent identifier
            
        Returns:
            List of available tools
        """
        try:
            headers = MCPHeaders.create(
                tenant_id="system",
                trace_id=f"discovery-{target_agent}",
                reply_to=f"mcp://{self.agent_id}/discovery_response",
                caller=self.agent_id
            )
            
            message = MCPMessage(
                message_type="discover_tools",
                headers=headers,
                payload={"requesting_agent": self.agent_id}
            )
            
            response = await self.protocol.send_message(target_agent, message)
            
            # Parse tools from response
            tools_data = response.payload.get("tools", [])
            return [MCPTool.from_dict(tool_data) for tool_data in tools_data]
            
        except Exception as e:
            self.logger.error(f"Tool discovery failed: {e}")
            return []
    
    async def _register_handlers(self) -> None:
        """Register message handlers."""
        await self.protocol.register_handler("tool_call", self._handle_tool_call)
        await self.protocol.register_handler("callback", self._handle_callback)
        await self.protocol.register_handler("discover_tools", self._handle_discover_tools)
    
    async def _handle_tool_call(self, message: MCPMessage) -> MCPResponse:
        """Handle incoming tool calls."""
        tool_name = message.payload.get("tool_name")
        arguments = message.payload.get("arguments", {})
        
        # Find tool handler
        handler = self.tool_registry.get_handler(tool_name)
        if not handler:
            return MCPResponse(
                status="error",
                message=f"Tool not found: {tool_name}",
                error_code="TOOL_NOT_FOUND"
            )
        
        # Return immediate ACK
        ack_response = MCPResponse(
            status="ack",
            message=f"Tool call received: {tool_name}",
            trace_id=message.headers.trace_id
        )
        
        # Process asynchronously
        asyncio.create_task(
            self._process_tool_async(handler, arguments, message.headers, tool_name)
        )
        
        return ack_response
    
    async def _process_tool_async(
        self,
        handler: Callable,
        arguments: Dict[str, Any],
        headers: MCPHeaders,
        tool_name: str
    ) -> None:
        """Process tool call asynchronously."""
        try:
            # Execute tool
            result = await handler(arguments, headers)
            
            # Send success callback
            await self.send_callback(
                headers.reply_to,
                {
                    "tool_name": tool_name,
                    "status": "success",
                    "data": result,
                    "agent_id": self.agent_id
                },
                headers
            )
            
        except Exception as e:
            # Send error callback
            await self.send_callback(
                headers.reply_to,
                {
                    "tool_name": tool_name,
                    "status": "error",
                    "error": str(e),
                    "agent_id": self.agent_id
                },
                headers
            )
    
    async def _handle_callback(self, message: MCPMessage) -> MCPResponse:
        """Handle incoming callbacks."""
        target_tool = message.payload.get("target_tool")
        result = message.payload.get("result", {})
        
        handler = self._callback_handlers.get(target_tool)
        if handler:
            await handler(result, message.headers)
        
        return MCPResponse(status="success", message="Callback processed")
    
    async def _handle_discover_tools(self, message: MCPMessage) -> MCPResponse:
        """Handle tool discovery requests."""
        tools = self.tool_registry.list_tools()
        
        return MCPResponse(
            status="success",
            message="Tools discovered",
            data={
                "tools": [tool.to_dict() for tool in tools],
                "agent_id": self.agent_id
            }
        )
    
    def _parse_reply_to(self, reply_to: str) -> tuple[str, str]:
        """Parse reply-to endpoint.
        
        Args:
            reply_to: Format mcp://agent/tool
            
        Returns:
            Tuple of (agent_id, tool_name)
        """
        if not reply_to.startswith("mcp://"):
            raise ValidationError(f"Invalid reply-to format: {reply_to}")
        
        parts = reply_to[6:].split("/", 1)
        if len(parts) != 2:
            raise ValidationError(f"Invalid reply-to format: {reply_to}")
        
        return parts[0], parts[1]
    
    async def shutdown(self) -> None:
        """Shutdown the MCP client."""
        try:
            self._active_traces.clear()
            await self.protocol.shutdown()
            self._initialized = False
            
            self.logger.info("MCP client shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")