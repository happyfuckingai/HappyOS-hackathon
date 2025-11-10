"""
CAMEL Integration Module

This module provides integration with the CAMEL (Communicative Agents for Mind Exploration and Language) 
framework, enabling advanced multi-agent collaboration and reasoning capabilities.
"""

from app.core.camel.camel_client import CamelClient, CamelResponse
from app.core.camel.camel_config import CamelConfig, AgentRole
from app.core.camel.agent_factory import create_agent, get_agent_by_role

__all__ = [
    'CamelClient', 
    'CamelResponse', 
    'CamelConfig', 
    'AgentRole',
    'create_agent',
    'get_agent_by_role'
]