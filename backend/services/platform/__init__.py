"""
Platform Services for MCP UI Hub

Core platform services that provide the integration backbone for all startup MCP servers.
"""

from .mcp_ui_hub_service import (
    MCPUIHubService,
    TenantConfig,
    get_platform_service,
    initialize_platform_service,
    cleanup_platform_service
)

from .mcp_agent_sdk import (
    MCPAgentClient,
    UIResource,
    create_startup_agent,
    generate_jwt_token_for_agent
)

__all__ = [
    "MCPUIHubService",
    "TenantConfig", 
    "get_platform_service",
    "initialize_platform_service",
    "cleanup_platform_service",
    "MCPAgentClient",
    "UIResource",
    "create_startup_agent",
    "generate_jwt_token_for_agent"
]