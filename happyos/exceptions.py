"""
HappyOS SDK Exception Hierarchy

Comprehensive exception system for enterprise error handling and debugging.
"""


class HappyOSSDKError(Exception):
    """Base exception for all HappyOS SDK errors."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "HAPPYOS_ERROR"
        self.details = details or {}


class AgentError(HappyOSSDKError):
    """Agent-related errors."""
    
    def __init__(self, message: str, agent_id: str = None, **kwargs):
        super().__init__(message, error_code="AGENT_ERROR", **kwargs)
        self.agent_id = agent_id


class MCPError(HappyOSSDKError):
    """MCP protocol communication errors."""
    
    def __init__(self, message: str, mcp_message_id: str = None, **kwargs):
        super().__init__(message, error_code="MCP_ERROR", **kwargs)
        self.mcp_message_id = mcp_message_id


class SecurityError(HappyOSSDKError):
    """Security-related errors."""
    
    def __init__(self, message: str, security_context: dict = None, **kwargs):
        super().__init__(message, error_code="SECURITY_ERROR", **kwargs)
        self.security_context = security_context or {}


class ComplianceError(SecurityError):
    """Compliance violation errors."""
    
    def __init__(self, message: str, compliance_standard: str = None, **kwargs):
        super().__init__(message, error_code="COMPLIANCE_ERROR", **kwargs)
        self.compliance_standard = compliance_standard


class ServiceUnavailableError(HappyOSSDKError):
    """Service availability errors."""
    
    def __init__(self, message: str, service_name: str = None, **kwargs):
        super().__init__(message, error_code="SERVICE_UNAVAILABLE", **kwargs)
        self.service_name = service_name


class AuthenticationError(SecurityError):
    """Authentication failures."""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, error_code="AUTH_ERROR", **kwargs)


class AuthorizationError(SecurityError):
    """Authorization failures."""
    
    def __init__(self, message: str = "Authorization denied", **kwargs):
        super().__init__(message, error_code="AUTHZ_ERROR", **kwargs)


class TenantIsolationError(SecurityError):
    """Tenant isolation violations."""
    
    def __init__(self, message: str, tenant_id: str = None, **kwargs):
        super().__init__(message, error_code="TENANT_ISOLATION_ERROR", **kwargs)
        self.tenant_id = tenant_id


class CircuitBreakerError(HappyOSSDKError):
    """Circuit breaker state errors."""
    
    def __init__(self, message: str = "Circuit breaker is open", **kwargs):
        super().__init__(message, error_code="CIRCUIT_BREAKER_ERROR", **kwargs)


class RetryExhaustedError(HappyOSSDKError):
    """Retry attempts exhausted."""
    
    def __init__(self, message: str, attempts: int = None, **kwargs):
        super().__init__(message, error_code="RETRY_EXHAUSTED", **kwargs)
        self.attempts = attempts


class CommunicationError(HappyOSSDKError):
    """Communication protocol errors."""
    
    def __init__(self, message: str, protocol: str = None, **kwargs):
        super().__init__(message, error_code="COMMUNICATION_ERROR", **kwargs)
        self.protocol = protocol


class ValidationError(HappyOSSDKError):
    """Data validation errors."""
    
    def __init__(self, message: str, field_name: str = None, **kwargs):
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)
        self.field_name = field_name


# Alias for backward compatibility
HappyOSError = HappyOSSDKError