"""
HappyOS SDK - Enterprise AI Agent Development Platform

A professional SDK for building industry-specific AI agent systems with 
enterprise-grade security, observability, and resilience patterns.

Example:
    >>> from happyos_sdk import BaseAgent, MCPClient
    >>> from happyos_sdk.industries.finance import ComplianceAgent
    >>> 
    >>> agent = ComplianceAgent(config)
    >>> await agent.start()
"""

from .version import __version__

# Core imports - using backward compatibility for now
from .version import __version__
from .config import SDKConfig, Environment
from .exceptions import HappyOSSDKError, A2AError, ServiceUnavailableError

# Legacy imports for backward compatibility
from .a2a_client import (
    A2AClient, A2ATransport, NetworkTransport, InProcessTransport,
    create_a2a_client, create_network_transport, create_inprocess_transport
)
from .mcp_client import (
    MCPClient, MCPHeaders, MCPResponse, MCPTool, AgentType,
    create_mcp_client
)
from .service_facades import (
    DatabaseFacade, StorageFacade, ComputeFacade, SearchFacade,
    SecretsFacade, CacheFacade, create_service_facades
)
from .circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker,
    reset_all_circuit_breakers, get_all_circuit_breaker_status
)
from .telemetry import TelemetryHooks, MetricsCollector
from .error_handling import (
    UnifiedErrorCode, UnifiedError, UnifiedErrorHandler, ErrorRecoveryStrategy,
    get_error_handler
)
from .logging import (
    LogContext, UnifiedLogger, setup_logging, get_logger, create_log_context
)
from .unified_observability import (
    ObservabilityContext, UnifiedObservabilityManager, get_observability_manager,
    with_mcp_observability, with_a2a_observability
)
from .mcp_security import (
    MCPSigningService, MCPAuthenticationService, SigningAlgorithm,
    MCPSigningKey, MCPSecurityError,
    mcp_signing_service, mcp_authentication_service,
    create_signed_mcp_headers, verify_mcp_headers
)
from .tenant_isolation import (
    UnifiedTenantIsolationService, TenantConfig, AgentConfig,
    TenantIsolationLevel, TenantAccessAttempt,
    TenantIsolationError, CrossTenantAccessError,
    unified_tenant_isolation_service,
    validate_mcp_tenant_access, get_agent_tenant_permissions
)
from .audit_logging import (
    UnifiedAuditLogger, AuditEvent, AuditEventType, AuditSeverity,
    AuditOutcome, AuditContext, ComplianceReport,
    unified_audit_logger, log_mcp_event
)

# New agent framework (available via subpackages)
try:
    from .agents import BaseAgent, AgentConfig, MCPServerAgent
except ImportError:
    # Agents not available yet
    pass

__all__ = [
    # A2A Communication
    "A2AClient",
    "A2ATransport", 
    "NetworkTransport",
    "InProcessTransport",
    "create_a2a_client",
    "create_network_transport", 
    "create_inprocess_transport",
    
    # MCP Communication
    "MCPClient",
    "MCPHeaders",
    "MCPResponse", 
    "MCPTool",
    "AgentType",
    "create_mcp_client",
    
    # Service Facades
    "DatabaseFacade",
    "StorageFacade", 
    "ComputeFacade",
    "SearchFacade",
    "SecretsFacade",
    "CacheFacade",
    "create_service_facades",
    
    # Resilience
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "get_circuit_breaker",
    "reset_all_circuit_breakers",
    "get_all_circuit_breaker_status",
    
    # Observability
    "TelemetryHooks",
    "MetricsCollector",
    
    # Exceptions
    "HappyOSSDKError",
    "A2AError", 
    "ServiceUnavailableError",
    
    # Error Handling
    "UnifiedErrorCode",
    "UnifiedError",
    "UnifiedErrorHandler",
    "ErrorRecoveryStrategy",
    "get_error_handler",
    
    # Logging
    "LogContext",
    "UnifiedLogger",
    "setup_logging",
    "get_logger",
    "create_log_context",
    
    # Unified Observability
    "ObservabilityContext",
    "UnifiedObservabilityManager",
    "get_observability_manager",
    "with_mcp_observability",
    "with_a2a_observability",
    
    # MCP Security
    "MCPSigningService",
    "MCPAuthenticationService",
    "SigningAlgorithm",
    "MCPSigningKey",
    "MCPSecurityError",
    "mcp_signing_service",
    "mcp_authentication_service",
    "create_signed_mcp_headers",
    "verify_mcp_headers",
    
    # Tenant Isolation
    "UnifiedTenantIsolationService",
    "TenantConfig",
    "AgentConfig",
    "TenantIsolationLevel",
    "TenantAccessAttempt",
    "TenantIsolationError",
    "CrossTenantAccessError",
    "unified_tenant_isolation_service",
    "validate_mcp_tenant_access",
    "get_agent_tenant_permissions",
    
    # Audit Logging
    "UnifiedAuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
    "AuditOutcome",
    "AuditContext",
    "ComplianceReport",
    "unified_audit_logger",
    "log_mcp_event"
]