"""
HappyOS Agent Framework

Provides base classes and utilities for building enterprise-grade AI agents
with MCP protocol support and industry-specific templates.
"""

from .base import BaseAgent, AgentConfig
from .mcp_server import MCPServerAgent

__all__ = [
    "BaseAgent",
    "AgentConfig", 
    "MCPServerAgent",
]