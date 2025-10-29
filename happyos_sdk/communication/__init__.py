"""
HappyOS Communication Protocols

Provides MCP and A2A communication protocols for agent-to-agent communication
with enterprise-grade security and reliability.
"""

# Import from the copied files
try:
    from .mcp import MCPClient, MCPHeaders, MCPResponse, MCPTool, AgentType, create_mcp_client
except ImportError:
    # Fallback to root level imports
    from ..mcp_client import MCPClient, MCPHeaders, MCPResponse, MCPTool, AgentType, create_mcp_client

try:
    from .a2a import (
        A2AClient, A2ATransport, NetworkTransport, InProcessTransport,
        create_a2a_client, create_network_transport, create_inprocess_transport
    )
except ImportError:
    # Fallback to root level imports
    from ..a2a_client import (
        A2AClient, A2ATransport, NetworkTransport, InProcessTransport,
        create_a2a_client, create_network_transport, create_inprocess_transport
    )

__all__ = [
    # MCP Protocol
    "MCPClient",
    "MCPHeaders", 
    "MCPResponse",
    "MCPTool",
    "AgentType",
    "create_mcp_client",
    
    # A2A Protocol
    "A2AClient",
    "A2ATransport",
    "NetworkTransport", 
    "InProcessTransport",
    "create_a2a_client",
    "create_network_transport",
    "create_inprocess_transport",
]