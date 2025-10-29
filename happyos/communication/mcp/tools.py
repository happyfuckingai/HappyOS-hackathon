"""
MCP Tools Registry and Management

Tool registration, discovery, and execution management for MCP protocol.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Union
from enum import Enum
import json

from ...exceptions import ValidationError, HappyOSError


class MCPToolType(Enum):
    """MCP tool types."""
    FUNCTION = "function"
    RESOURCE = "resource"
    PROMPT = "prompt"


@dataclass
class MCPToolSchema:
    """JSON Schema for MCP tool input/output validation."""
    
    type: str = "object"
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    description: Optional[str] = None
    
    def validate(self, data: Dict[str, Any]) -> None:
        """Validate data against schema.
        
        Args:
            data: Data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        # Check required fields
        for field_name in self.required:
            if field_name not in data:
                raise ValidationError(f"Required field '{field_name}' missing")
        
        # Basic type validation
        if self.type == "object" and not isinstance(data, dict):
            raise ValidationError(f"Expected object, got {type(data).__name__}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "type": self.type,
            "properties": self.properties,
            "required": self.required
        }
        
        if self.description:
            result["description"] = self.description
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPToolSchema":
        """Create from dictionary."""
        return cls(
            type=data.get("type", "object"),
            properties=data.get("properties", {}),
            required=data.get("required", []),
            description=data.get("description")
        )


@dataclass
class MCPTool:
    """MCP tool definition with metadata and validation."""
    
    name: str
    description: str
    tool_type: MCPToolType = MCPToolType.FUNCTION
    input_schema: Optional[MCPToolSchema] = None
    output_schema: Optional[MCPToolSchema] = None
    
    # Enterprise features
    requires_auth: bool = True
    tenant_isolated: bool = True
    rate_limit: Optional[int] = None  # calls per minute
    timeout: int = 30
    tags: List[str] = field(default_factory=list)
    
    def validate_input(self, data: Dict[str, Any]) -> None:
        """Validate input data against schema.
        
        Args:
            data: Input data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        if self.input_schema:
            self.input_schema.validate(data)
    
    def validate_output(self, data: Dict[str, Any]) -> None:
        """Validate output data against schema.
        
        Args:
            data: Output data to validate
            
        Raises:
            ValidationError: If validation fails
        """
        if self.output_schema:
            self.output_schema.validate(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "name": self.name,
            "description": self.description,
            "type": self.tool_type.value,
            "requires_auth": self.requires_auth,
            "tenant_isolated": self.tenant_isolated,
            "timeout": self.timeout,
            "tags": self.tags
        }
        
        if self.input_schema:
            result["input_schema"] = self.input_schema.to_dict()
        
        if self.output_schema:
            result["output_schema"] = self.output_schema.to_dict()
        
        if self.rate_limit:
            result["rate_limit"] = self.rate_limit
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPTool":
        """Create from dictionary."""
        input_schema = None
        if "input_schema" in data:
            input_schema = MCPToolSchema.from_dict(data["input_schema"])
        
        output_schema = None
        if "output_schema" in data:
            output_schema = MCPToolSchema.from_dict(data["output_schema"])
        
        return cls(
            name=data["name"],
            description=data["description"],
            tool_type=MCPToolType(data.get("type", "function")),
            input_schema=input_schema,
            output_schema=output_schema,
            requires_auth=data.get("requires_auth", True),
            tenant_isolated=data.get("tenant_isolated", True),
            rate_limit=data.get("rate_limit"),
            timeout=data.get("timeout", 30),
            tags=data.get("tags", [])
        )


class MCPToolRegistry:
    """Registry for managing MCP tools and their handlers.
    
    Provides tool registration, discovery, and execution management
    with enterprise features like rate limiting and access control.
    """
    
    def __init__(self):
        """Initialize tool registry."""
        self._tools: Dict[str, MCPTool] = {}
        self._handlers: Dict[str, Callable] = {}
        self._rate_limits: Dict[str, Dict[str, Any]] = {}
    
    def register(self, tool: MCPTool, handler: Callable) -> None:
        """Register a tool with its handler.
        
        Args:
            tool: Tool definition
            handler: Async handler function
            
        Raises:
            ValidationError: If tool or handler is invalid
        """
        if not tool.name:
            raise ValidationError("Tool name is required")
        
        if not callable(handler):
            raise ValidationError("Handler must be callable")
        
        # Validate tool definition
        if tool.input_schema:
            # Test schema validation with empty dict
            try:
                tool.input_schema.validate({})
            except ValidationError:
                pass  # Expected for required fields
        
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler
        
        # Initialize rate limiting if configured
        if tool.rate_limit:
            self._rate_limits[tool.name] = {
                "limit": tool.rate_limit,
                "calls": [],
                "window_minutes": 1
            }
    
    def unregister(self, tool_name: str) -> bool:
        """Unregister a tool.
        
        Args:
            tool_name: Name of tool to unregister
            
        Returns:
            True if tool was unregistered
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            del self._handlers[tool_name]
            self._rate_limits.pop(tool_name, None)
            return True
        return False
    
    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """Get tool definition by name.
        
        Args:
            tool_name: Tool name
            
        Returns:
            Tool definition or None if not found
        """
        return self._tools.get(tool_name)
    
    def get_handler(self, tool_name: str) -> Optional[Callable]:
        """Get tool handler by name.
        
        Args:
            tool_name: Tool name
            
        Returns:
            Handler function or None if not found
        """
        return self._handlers.get(tool_name)
    
    def list_tools(self, tags: Optional[List[str]] = None) -> List[MCPTool]:
        """List registered tools, optionally filtered by tags.
        
        Args:
            tags: Optional tags to filter by
            
        Returns:
            List of matching tools
        """
        tools = list(self._tools.values())
        
        if tags:
            tools = [
                tool for tool in tools
                if any(tag in tool.tags for tag in tags)
            ]
        
        return tools
    
    def check_rate_limit(self, tool_name: str, tenant_id: str) -> bool:
        """Check if tool call is within rate limits.
        
        Args:
            tool_name: Tool name
            tenant_id: Tenant identifier
            
        Returns:
            True if within rate limits
        """
        if tool_name not in self._rate_limits:
            return True
        
        rate_limit_info = self._rate_limits[tool_name]
        limit = rate_limit_info["limit"]
        calls = rate_limit_info["calls"]
        
        # Clean old calls (older than window)
        import time
        current_time = time.time()
        window_seconds = rate_limit_info["window_minutes"] * 60
        
        # Filter calls within window
        recent_calls = [
            call_time for call_time in calls
            if current_time - call_time < window_seconds
        ]
        
        # Update calls list
        rate_limit_info["calls"] = recent_calls
        
        # Check if under limit
        tenant_calls = len([
            call for call in recent_calls
            # In production, would track per tenant
        ])
        
        return tenant_calls < limit
    
    def record_call(self, tool_name: str, tenant_id: str) -> None:
        """Record a tool call for rate limiting.
        
        Args:
            tool_name: Tool name
            tenant_id: Tenant identifier
        """
        if tool_name in self._rate_limits:
            import time
            self._rate_limits[tool_name]["calls"].append(time.time())
    
    def get_tool_stats(self) -> Dict[str, Any]:
        """Get registry statistics.
        
        Returns:
            Statistics about registered tools
        """
        stats = {
            "total_tools": len(self._tools),
            "tools_by_type": {},
            "tools_with_rate_limits": len(self._rate_limits),
            "tools_requiring_auth": 0,
            "tenant_isolated_tools": 0
        }
        
        # Count by type
        for tool in self._tools.values():
            tool_type = tool.tool_type.value
            stats["tools_by_type"][tool_type] = stats["tools_by_type"].get(tool_type, 0) + 1
            
            if tool.requires_auth:
                stats["tools_requiring_auth"] += 1
            
            if tool.tenant_isolated:
                stats["tenant_isolated_tools"] += 1
        
        return stats