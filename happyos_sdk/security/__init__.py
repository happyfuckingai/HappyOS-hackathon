"""
HappyOS Security Framework

Provides enterprise-grade security including authentication, authorization,
tenant isolation, and MCP message signing.
"""

from .signing import (
    MCPSigningService, MCPAuthenticationService, SigningAlgorithm,
    MCPSigningKey, MCPSecurityError, mcp_signing_service, 
    mcp_authentication_service, create_signed_mcp_headers, verify_mcp_headers
)
from .tenant import (
    UnifiedTenantIsolationService, TenantConfig, AgentConfig,
    TenantIsolationLevel, TenantAccessAttempt, TenantIsolationError,
    CrossTenantAccessError, unified_tenant_isolation_service,
    validate_mcp_tenant_access, get_agent_tenant_permissions
)
from .audit import (
    UnifiedAuditLogger, AuditEvent, AuditEventType, AuditSeverity,
    AuditOutcome, AuditContext, ComplianceReport, unified_audit_logger,
    log_mcp_event
)

__all__ = [
    # MCP Security & Signing
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
    "log_mcp_event",
]