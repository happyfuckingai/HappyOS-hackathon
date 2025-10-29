"""Authentication and authorization."""
from .authentication import (
    ProductionAuthService,
    RateLimitService,
    get_current_user,
    check_auth_rate_limit,
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_jwt_token,
    verify_ui_scope,
    limiter,
    security
)

# New JWT service with tenant scoping
from .jwt_service import JWTService, JWTClaims, ScopeBuilder, jwt_service, token_refresh_service
from .dependencies import (
    get_jwt_claims, get_optional_jwt_claims, require_scope, require_tenant_access,
    validate_tenant_from_path, validate_ui_write_access, validate_ui_read_access,
    get_agent_info, require_agent_token, tenant_validator
)
from .agent_registration import (
    AgentRegistration, AgentCredentials, RegisteredAgent, AgentRegistrationService,
    PredefinedAgents, setup_demo_agents, agent_registration_service
)
from .tenant_isolation import (
    TenantIsolationService, TenantIsolationError, CrossTenantAccessError,
    DynamoDBTenantIsolation, AuditLogger, tenant_isolation_service, audit_logger
)
from .security_monitoring import (
    SecurityMonitoringService, SecurityEvent, SecurityAlert, SecurityMetrics,
    AlertSeverity, ThreatType, RateLimiter, SuspiciousActivityDetector,
    security_monitoring_service
)

__all__ = [
    # Legacy authentication
    "ProductionAuthService",
    "RateLimitService", 
    "get_current_user",
    "check_auth_rate_limit",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "verify_jwt_token",
    "verify_ui_scope",
    "limiter",
    "security",
    
    # New JWT service with tenant scoping
    "JWTService",
    "JWTClaims",
    "ScopeBuilder",
    "jwt_service",
    "token_refresh_service",
    
    # Dependencies
    "get_jwt_claims",
    "get_optional_jwt_claims",
    "require_scope",
    "require_tenant_access",
    "validate_tenant_from_path",
    "validate_ui_write_access",
    "validate_ui_read_access",
    "get_agent_info",
    "require_agent_token",
    "tenant_validator",
    
    # Agent registration
    "AgentRegistration",
    "AgentCredentials",
    "RegisteredAgent",
    "AgentRegistrationService",
    "PredefinedAgents",
    "setup_demo_agents",
    "agent_registration_service",
    
    # Tenant isolation
    "TenantIsolationService",
    "TenantIsolationError",
    "CrossTenantAccessError",
    "DynamoDBTenantIsolation",
    "AuditLogger",
    "tenant_isolation_service",
    "audit_logger",
    
    # Security monitoring
    "SecurityMonitoringService",
    "SecurityEvent",
    "SecurityAlert",
    "SecurityMetrics",
    "AlertSeverity",
    "ThreatType",
    "RateLimiter",
    "SuspiciousActivityDetector",
    "security_monitoring_service"
]
