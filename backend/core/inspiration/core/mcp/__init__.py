"""
🤖 HAPPYOS MCP MODULE

Model Control Protocol (MCP) integration för Windows AI Studio.

Denna modul innehåller:
- MCP Adapter: Kopplar HappyOS-agenter till MCP-verktyg
- MCP Server: Hanterar MCP-kommunikation med Windows AI Studio
- Agent Templates: Visuella templates för varje agenttyp
- Transport Layer: Stdio och HTTP-transport för MCP

Författare: HappyOS AI Team
Version: 1.0.0
"""

from .happyos_mcp_adapter import (
    HappyOSMCPAdapter,
    MCPTool,
    MCPToolResult,
    AgentTemplate,
    MCPSessionManager,
    mcp_adapter,
    initialize_mcp_adapter,
    execute_mcp_tool
)

from .happyos_mcp_server import (
    HappyOSMCPServer,
    MCPTransport,
    StdioMCPTransport,
    create_mcp_server,
    run_stdio_server
)

__version__ = "1.0.0"
__author__ = "HappyOS AI Team"
__description__ = "MCP integration for HappyOS AI agent system with Windows AI Studio"

# Exportera alla viktiga komponenter
__all__ = [
    # Adapter components
    'HappyOSMCPAdapter',
    'MCPTool',
    'MCPToolResult',
    'AgentTemplate',
    'MCPSessionManager',
    'mcp_adapter',
    'initialize_mcp_adapter',
    'execute_mcp_tool',

    # Server components
    'HappyOSMCPServer',
    'MCPTransport',
    'StdioMCPTransport',
    'create_mcp_server',
    'run_stdio_server',

    # Metadata
    '__version__',
    '__author__',
    '__description__'
]