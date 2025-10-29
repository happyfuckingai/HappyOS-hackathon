"""
MCP Server Agent Implementation

Provides MCP server functionality for agents with proper isolation
and enterprise-grade patterns.
"""

import asyncio
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass

from .base import BaseAgent, AgentConfig
from ..communication.mcp import MCPClient, MCPTool
from ..exceptions import HappyOSSDKError


@dataclass
class MCPToolDefinition:
    """Definition of an MCP tool."""
    name: str
    description: str
    handler: Callable
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None


class MCPServerAgent(BaseAgent):
    """Agent that provides MCP server functionality.
    
    Allows agents to expose tools via MCP protocol while maintaining
    proper isolation and enterprise patterns.
    """
    
    def __init__(self, config: AgentConfig, mcp_port: int = 8080):
        """Initialize MCP server agent.
        
        Args:
            config: Agent configuration
            mcp_port: Port for MCP server
        """
        super().__init__(config)
        self.mcp_port = mcp_port
        self.tools: Dict[str, MCPToolDefinition] = {}
        self._server_task: Optional[asyncio.Task] = None
    
    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        input_schema: Dict[str, Any],
        output_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register an MCP tool.
        
        Args:
            name: Tool name
            description: Tool description
            handler: Function to handle tool calls
            input_schema: JSON schema for input validation
            output_schema: JSON schema for output validation
        """
        self.tools[name] = MCPToolDefinition(
            name=name,
            description=description,
            handler=handler,
            input_schema=input_schema,
            output_schema=output_schema
        )
        
        self.logger.info(f"Registered MCP tool: {name}")
    
    async def process_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process MCP tool calls."""
        tool_name = task_data.get("tool")
        if not tool_name:
            raise HappyOSSDKError("No tool specified in task data")
        
        if tool_name not in self.tools:
            raise HappyOSSDKError(f"Unknown tool: {tool_name}")
        
        tool_def = self.tools[tool_name]
        
        try:
            # Call the tool handler
            result = await tool_def.handler(task_data.get("args", {}))
            
            if self.metrics:
                self.metrics.increment(f"mcp.tool.{tool_name}.success")
            
            return {"status": "success", "result": result}
            
        except Exception as e:
            self.logger.error(f"Tool {tool_name} failed: {e}")
            
            if self.metrics:
                self.metrics.increment(f"mcp.tool.{tool_name}.error")
            
            raise HappyOSSDKError(f"Tool execution failed: {e}") from e
    
    async def _initialize(self) -> None:
        """Initialize MCP server."""
        # Start MCP server (simplified implementation)
        self.logger.info(f"Starting MCP server on port {self.mcp_port}")
        # In a real implementation, this would start an actual MCP server
    
    async def _cleanup(self) -> None:
        """Clean up MCP server."""
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
            }
            for tool in self.tools.values()
        ]