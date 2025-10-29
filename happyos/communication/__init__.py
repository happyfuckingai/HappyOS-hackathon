"""
HappyOS Communication Protocols

Enterprise-grade communication protocols for AI agent systems including
MCP (Model Context Protocol) and A2A (Agent-to-Agent) communication.
"""

from .mcp import MCPClient, MCPMessage, MCPProtocol
from .a2a import A2AClient, A2AMessage, A2AProtocol
from .mcp_ui_hub import (
    MCPUIHubClient, 
    UIResource, 
    create_startup_agent_client,
    generate_jwt_token_for_agent
)

__all__ = [
    "MCPClient",
    "MCPMessage", 
    "MCPProtocol",
    "A2AClient",
    "A2AMessage",
    "A2AProtocol",
    "MCPUIHubClient",
    "UIResource",
    "create_startup_agent_client",
    "generate_jwt_token_for_agent",
]