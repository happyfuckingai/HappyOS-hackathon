"""
HappyOS SDK - Enterprise AI Agent Development Kit

A professional, enterprise-grade SDK for building industry-specific AI agent systems
with built-in security, observability, resilience, and MCP-based communication.

Example usage:
    >>> from happyos import BaseAgent, MCPClient
    >>> from happyos.industries.finance import ComplianceAgent
    >>> 
    >>> # Create a finance compliance agent
    >>> agent = ComplianceAgent(config)
    >>> await agent.start()
"""

from .version import __version__
from .config import SDKConfig, Environment
from .exceptions import (
    HappyOSSDKError,
    AgentError,
    MCPError,
    SecurityError,
    ComplianceError,
    ServiceUnavailableError,
    CommunicationError,
    ValidationError,
)

# Core agent framework
from .agents import BaseAgent, AgentConfig, AgentState, MCPServerManager, create_agent_config
from .communication import MCPClient, MCPProtocol, A2AClient, MCPUIHubClient
from .security import AuthProvider, TenantIsolation, MessageSigner
from .observability import get_logger, MetricsCollector, TracingManager
from .resilience import CircuitBreaker, RetryStrategy
from .services import UnifiedServiceFacades

# Industry templates (optional imports)
try:
    from . import industries
except ImportError:
    industries = None

__version__ = "1.0.0"

__all__ = [
    # Version and configuration
    "__version__",
    "SDKConfig",
    "Environment",
    
    # Exceptions
    "HappyOSSDKError",
    "AgentError", 
    "MCPError",
    "SecurityError",
    "ComplianceError",
    "ServiceUnavailableError",
    "CommunicationError",
    "ValidationError",
    
    # Core framework
    "BaseAgent",
    "AgentConfig",
    "AgentState",
    "MCPServerManager",
    "create_agent_config",
    
    # Communication
    "MCPClient",
    "MCPProtocol",
    "A2AClient",
    "MCPUIHubClient",
    
    # Security
    "AuthProvider",
    "TenantIsolation", 
    "MessageSigner",
    
    # Observability
    "get_logger",
    "MetricsCollector",
    "TracingManager",
    
    # Resilience
    "CircuitBreaker",
    "RetryStrategy",
    
    # Services
    "UnifiedServiceFacades",
]

# Add industries to __all__ if available
if industries:
    __all__.append("industries")