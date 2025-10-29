"""
Unified Error Handling for HappyOS SDK

Provides standardized error codes, error formats, and recovery patterns
that work across both MCP and Backend Core A2A protocols.

This module creates a translation layer between MCP protocol errors and
Backend Core A2A protocol errors, ensuring consistent error handling
across all HappyOS agent systems.
"""

import logging
import traceback
import asyncio
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from .exceptions import HappyOSSDKError, A2AError, ServiceUnavailableError

# Try to import backend observability components for integration
try:
    from backend.modules.observability.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
    from backend.services.observability.logger import get_logger as get_backend_logger
    BACKEND_OBSERVABILITY_AVAILABLE = True
except ImportError:
    BACKEND_OBSERVABILITY_AVAILABLE = False

logger = logging.getLogger(__name__)


class UnifiedErrorCode(Enum):
    """Standardized error codes across all HappyOS agent systems."""
    
    # MCP Communication Errors
    MCP_COMMUNICATION_ERROR = "MCP_COMM_001"
    MCP_TOOL_NOT_FOUND = "MCP_TOOL_001"
    MCP_CALLBACK_FAILED = "MCP_CALLBACK_001"
    MCP_HEADER_INVALID = "MCP_HEADER_001"
    MCP_TIMEOUT = "MCP_TIMEOUT_001"
    
    # A2A Communication Errors
    A2A_COMMUNICATION_ERROR = "A2A_COMM_001"
    A2A_SERVICE_UNAVAILABLE = "A2A_SERVICE_001"
    A2A_TIMEOUT = "A2A_TIMEOUT_001"
    A2A_AUTHENTICATION_FAILED = "A2A_AUTH_001"
    
    # Circuit Breaker Errors
    CIRCUIT_BREAKER_OPEN = "CB_OPEN_001"
    CIRCUIT_BREAKER_TIMEOUT = "CB_TIMEOUT_001"
    SERVICE_DEGRADED = "CB_DEGRADED_001"
    FAILOVER_FAILED = "CB_FAILOVER_001"
    
    # Service Facade Errors
    DATABASE_ERROR = "DB_ERROR_001"
    STORAGE_ERROR = "STORAGE_ERROR_001"
    COMPUTE_ERROR = "COMPUTE_ERROR_001"
    SEARCH_ERROR = "SEARCH_ERROR_001"
    CACHE_ERROR = "CACHE_ERROR_001"
    SECRETS_ERROR = "SECRETS_ERROR_001"
    
    # Authentication and Authorization
    AUTHENTICATION_FAILED = "AUTH_FAILED_001"
    AUTHORIZATION_FAILED = "AUTH_DENIED_001"
    TENANT_ISOLATION_VIOLATION = "TENANT_VIOLATION_001"
    INVALID_CREDENTIALS = "AUTH_INVALID_001"
    
    # Data Validation Errors
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_001"
    SCHEMA_VALIDATION_ERROR = "SCHEMA_VALIDATION_001"
    REQUIRED_FIELD_MISSING = "DATA_MISSING_001"
    INVALID_DATA_FORMAT = "DATA_FORMAT_001"
    
    # System Errors
    SYSTEM_ERROR = "SYSTEM_ERROR_001"
    CONFIGURATION_ERROR = "CONFIG_ERROR_001"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED_001"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_001"
    
    # Tool Execution Errors
    TOOL_EXECUTION_FAILED = "TOOL_EXEC_001"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND_001"
    TOOL_TIMEOUT = "TOOL_TIMEOUT_001"
    
    # Compliance and Business Logic Errors
    COMPLIANCE_VIOLATION = "COMPLIANCE_001"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_001"
    WORKFLOW_ERROR = "WORKFLOW_ERROR_001"


@dataclass
class UnifiedError:
    """Standardized error format across all HappyOS agent systems."""
    
    error_code: UnifiedErrorCode
    message: str
    details: Dict[str, Any]
    trace_id: Optional[str] = None
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    agent_type: Optional[str] = None
    component: Optional[str] = None
    timestamp: str = None
    recoverable: bool = True
    retry_after: Optional[int] = None
    stack_trace: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "trace_id": self.trace_id,
            "conversation_id": self.conversation_id,
            "tenant_id": self.tenant_id,
            "agent_type": self.agent_type,
            "component": self.component,
            "timestamp": self.timestamp,
            "recoverable": self.recoverable,
            "retry_after": self.retry_after,
            "stack_trace": self.stack_trace
        }
    
    def to_mcp_response(self) -> Dict[str, Any]:
        """Convert to MCP response format."""
        return {
            "status": "error",
            "message": self.message,
            "error_code": self.error_code.value,
            "data": self.details,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "recoverable": self.recoverable,
            "retry_after": self.retry_after
        }


class UnifiedErrorHandler:
    """
    Standardized error handling across all HappyOS agent systems.
    
    This class provides a translation layer between MCP protocol errors
    and Backend Core A2A protocol errors, ensuring consistent error handling
    and logging across both communication protocols.
    """
    
    def __init__(self, component: str, agent_type: Optional[str] = None):
        """
        Initialize error handler.
        
        Args:
            component: Component name (e.g., "mcp_client", "service_facade")
            agent_type: Agent type if applicable
        """
        self.component = component
        self.agent_type = agent_type
        self.logger = logging.getLogger(f"{__name__}.{component}")
        
        # Initialize backend observability integration if available
        self.backend_logger = None
        self.audit_logger = None
        
        if BACKEND_OBSERVABILITY_AVAILABLE:
            try:
                self.backend_logger = get_backend_logger(f"happyos_sdk.{component}")
                self.audit_logger = get_audit_logger()
            except Exception as e:
                logger.warning(f"Failed to initialize backend observability: {e}")
                self.backend_logger = None
                self.audit_logger = None
    
    def create_error(self,
                    error_code: UnifiedErrorCode,
                    message: str,
                    details: Dict[str, Any] = None,
                    trace_id: str = None,
                    conversation_id: str = None,
                    tenant_id: str = None,
                    recoverable: bool = True,
                    retry_after: int = None,
                    include_stack_trace: bool = False) -> UnifiedError:
        """
        Create a standardized error.
        
        Args:
            error_code: Standardized error code
            message: Human-readable error message
            details: Additional error details
            trace_id: Trace ID for correlation
            conversation_id: Conversation ID for correlation
            tenant_id: Tenant ID for isolation
            recoverable: Whether the error is recoverable
            retry_after: Seconds to wait before retry
            include_stack_trace: Whether to include stack trace
            
        Returns:
            UnifiedError instance
        """
        stack_trace = None
        if include_stack_trace:
            stack_trace = traceback.format_exc()
        
        return UnifiedError(
            error_code=error_code,
            message=message,
            details=details or {},
            trace_id=trace_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            agent_type=self.agent_type,
            component=self.component,
            recoverable=recoverable,
            retry_after=retry_after,
            stack_trace=stack_trace
        )
    
    def handle_mcp_error(self,
                        error: Exception,
                        context: Dict[str, Any] = None) -> UnifiedError:
        """Handle MCP communication errors."""
        trace_id = context.get("trace_id") if context else None
        conversation_id = context.get("conversation_id") if context else None
        tenant_id = context.get("tenant_id") if context else None
        
        if isinstance(error, TimeoutError):
            return self.create_error(
                UnifiedErrorCode.MCP_TIMEOUT,
                f"MCP communication timeout: {str(error)}",
                {"original_error": str(error)},
                trace_id=trace_id,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                recoverable=True,
                retry_after=5
            )
        
        return self.create_error(
            UnifiedErrorCode.MCP_COMMUNICATION_ERROR,
            f"MCP communication failed: {str(error)}",
            {"original_error": str(error), "context": context or {}},
            trace_id=trace_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            recoverable=True,
            retry_after=3
        )
    
    def handle_a2a_error(self,
                        error: Exception,
                        service_name: str = None,
                        context: Dict[str, Any] = None) -> UnifiedError:
        """Handle A2A communication errors."""
        trace_id = context.get("trace_id") if context else None
        tenant_id = context.get("tenant_id") if context else None
        
        if isinstance(error, ServiceUnavailableError):
            return self.create_error(
                UnifiedErrorCode.A2A_SERVICE_UNAVAILABLE,
                f"Backend service unavailable: {service_name or 'unknown'}",
                {"service_name": service_name, "original_error": str(error)},
                trace_id=trace_id,
                tenant_id=tenant_id,
                recoverable=True,
                retry_after=10
            )
        
        if isinstance(error, A2AError):
            return self.create_error(
                UnifiedErrorCode.A2A_COMMUNICATION_ERROR,
                f"A2A communication failed: {str(error)}",
                {"service_name": service_name, "original_error": str(error)},
                trace_id=trace_id,
                tenant_id=tenant_id,
                recoverable=True,
                retry_after=5
            )
        
        return self.create_error(
            UnifiedErrorCode.SYSTEM_ERROR,
            f"Unexpected error in A2A communication: {str(error)}",
            {"service_name": service_name, "original_error": str(error)},
            trace_id=trace_id,
            tenant_id=tenant_id,
            recoverable=False,
            include_stack_trace=True
        )
    
    def handle_circuit_breaker_error(self,
                                   service_name: str,
                                   error: Exception,
                                   context: Dict[str, Any] = None) -> UnifiedError:
        """Handle circuit breaker errors."""
        trace_id = context.get("trace_id") if context else None
        tenant_id = context.get("tenant_id") if context else None
        
        error_message = str(error).lower()
        
        if "circuit breaker is open" in error_message:
            return self.create_error(
                UnifiedErrorCode.CIRCUIT_BREAKER_OPEN,
                f"Circuit breaker is open for service: {service_name}",
                {"service_name": service_name, "original_error": str(error)},
                trace_id=trace_id,
                tenant_id=tenant_id,
                recoverable=True,
                retry_after=30
            )
        
        if "timeout" in error_message:
            return self.create_error(
                UnifiedErrorCode.CIRCUIT_BREAKER_TIMEOUT,
                f"Circuit breaker timeout for service: {service_name}",
                {"service_name": service_name, "original_error": str(error)},
                trace_id=trace_id,
                tenant_id=tenant_id,
                recoverable=True,
                retry_after=15
            )
        
        return self.create_error(
            UnifiedErrorCode.SERVICE_DEGRADED,
            f"Service degraded: {service_name}",
            {"service_name": service_name, "original_error": str(error)},
            trace_id=trace_id,
            tenant_id=tenant_id,
            recoverable=True,
            retry_after=10
        )
    
    def handle_authentication_error(self,
                                  error: Exception,
                                  context: Dict[str, Any] = None) -> UnifiedError:
        """Handle authentication errors."""
        trace_id = context.get("trace_id") if context else None
        tenant_id = context.get("tenant_id") if context else None
        
        return self.create_error(
            UnifiedErrorCode.AUTHENTICATION_FAILED,
            f"Authentication failed: {str(error)}",
            {"original_error": str(error), "context": context or {}},
            trace_id=trace_id,
            tenant_id=tenant_id,
            recoverable=False
        )
    
    def handle_validation_error(self,
                              error: Exception,
                              field_name: str = None,
                              context: Dict[str, Any] = None) -> UnifiedError:
        """Handle data validation errors."""
        trace_id = context.get("trace_id") if context else None
        tenant_id = context.get("tenant_id") if context else None
        
        return self.create_error(
            UnifiedErrorCode.DATA_VALIDATION_ERROR,
            f"Data validation failed: {str(error)}",
            {"field_name": field_name, "original_error": str(error)},
            trace_id=trace_id,
            tenant_id=tenant_id,
            recoverable=False
        )
    
    def handle_tool_error(self,
                         error: Exception,
                         tool_name: str = None,
                         context: Dict[str, Any] = None) -> UnifiedError:
        """Handle MCP tool execution errors."""
        trace_id = context.get("trace_id") if context else None
        conversation_id = context.get("conversation_id") if context else None
        tenant_id = context.get("tenant_id") if context else None
        
        if isinstance(error, TimeoutError):
            return self.create_error(
                UnifiedErrorCode.TOOL_TIMEOUT,
                f"Tool execution timeout: {tool_name}",
                {"tool_name": tool_name, "original_error": str(error)},
                trace_id=trace_id,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                recoverable=True,
                retry_after=5
            )
        
        return self.create_error(
            UnifiedErrorCode.TOOL_EXECUTION_FAILED,
            f"Tool execution failed: {tool_name} - {str(error)}",
            {"tool_name": tool_name, "original_error": str(error)},
            trace_id=trace_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            recoverable=True,
            retry_after=3
        )
    
    def handle_compliance_error(self,
                              error: Exception,
                              compliance_type: str = None,
                              context: Dict[str, Any] = None) -> UnifiedError:
        """Handle compliance violation errors."""
        trace_id = context.get("trace_id") if context else None
        tenant_id = context.get("tenant_id") if context else None
        
        return self.create_error(
            UnifiedErrorCode.COMPLIANCE_VIOLATION,
            f"Compliance violation: {compliance_type} - {str(error)}",
            {"compliance_type": compliance_type, "original_error": str(error)},
            trace_id=trace_id,
            tenant_id=tenant_id,
            recoverable=False  # Compliance errors are typically not recoverable
        )
    
    async def attempt_recovery(self, error: UnifiedError) -> bool:
        """
        Attempt automatic error recovery.
        
        Args:
            error: UnifiedError to attempt recovery for
            
        Returns:
            True if recovery was successful, False otherwise
        """
        if not error.recoverable:
            return False
        
        try:
            # Log recovery attempt
            await self._log_recovery_attempt(error)
            
            # Implement recovery strategies based on error type
            if error.error_code in [UnifiedErrorCode.MCP_TIMEOUT, UnifiedErrorCode.A2A_TIMEOUT]:
                # For timeout errors, just wait and return True to indicate retry is possible
                if error.retry_after:
                    await asyncio.sleep(error.retry_after)
                return True
            
            elif error.error_code == UnifiedErrorCode.CIRCUIT_BREAKER_OPEN:
                # For circuit breaker errors, wait for the retry period
                if error.retry_after:
                    await asyncio.sleep(error.retry_after)
                return True
            
            elif error.error_code in [UnifiedErrorCode.A2A_SERVICE_UNAVAILABLE, UnifiedErrorCode.SERVICE_DEGRADED]:
                # For service unavailable errors, attempt to use circuit breaker failover
                return True  # Let circuit breaker handle the failover
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error recovery failed: {e}")
            await self._log_recovery_failure(error, e)
            return False
    
    def log_error(self, error: UnifiedError, level: int = logging.ERROR):
        """
        Log error with standardized format using both SDK and backend logging.
        
        Args:
            error: UnifiedError to log
            level: Logging level
        """
        extra_data = {
            "error_code": error.error_code.value,
            "trace_id": error.trace_id,
            "conversation_id": error.conversation_id,
            "tenant_id": error.tenant_id,
            "agent_type": error.agent_type,
            "component": error.component,
            "recoverable": error.recoverable,
            "retry_after": error.retry_after,
            **error.details
        }
        
        # Log to SDK logger
        self.logger.log(
            level,
            f"[{error.error_code.value}] {error.message}",
            extra=extra_data
        )
        
        # Log to backend logger if available
        if self.backend_logger:
            try:
                self.backend_logger.error(
                    f"HappyOS SDK Error: {error.message}",
                    error_code=error.error_code.value,
                    component=self.component,
                    agent_type=self.agent_type,
                    recoverable=error.recoverable,
                    **extra_data
                )
            except Exception as e:
                self.logger.warning(f"Failed to log to backend logger: {e}")
        
        if error.stack_trace:
            self.logger.debug(f"Stack trace for {error.error_code.value}: {error.stack_trace}")
    
    async def log_mcp_error_to_audit(self, error: UnifiedError, operation: str = None):
        """
        Log MCP protocol errors to backend audit system.
        
        Args:
            error: UnifiedError to audit
            operation: MCP operation that failed
        """
        if not self.audit_logger:
            return
        
        try:
            # Determine audit event type based on error code
            if error.error_code in [UnifiedErrorCode.AUTHENTICATION_FAILED, UnifiedErrorCode.AUTHORIZATION_FAILED]:
                event_type = AuditEventType.AUTH_PERMISSION_DENIED
                severity = AuditSeverity.HIGH
            elif error.error_code == UnifiedErrorCode.TENANT_ISOLATION_VIOLATION:
                event_type = AuditEventType.TENANT_ISOLATION_VIOLATION
                severity = AuditSeverity.CRITICAL
            elif error.error_code in [UnifiedErrorCode.MCP_COMMUNICATION_ERROR, UnifiedErrorCode.A2A_COMMUNICATION_ERROR]:
                event_type = AuditEventType.SYSTEM_ERROR
                severity = AuditSeverity.MEDIUM
            else:
                event_type = AuditEventType.SYSTEM_ERROR
                severity = AuditSeverity.LOW if error.recoverable else AuditSeverity.MEDIUM
            
            await self.audit_logger.log_security_event(
                event_type=event_type,
                message=f"HappyOS SDK Error in {self.component}: {error.message}",
                severity=severity,
                tenant_id=error.tenant_id,
                correlation_id=error.trace_id,
                details={
                    "error_code": error.error_code.value,
                    "component": self.component,
                    "agent_type": self.agent_type,
                    "operation": operation,
                    "recoverable": error.recoverable,
                    "conversation_id": error.conversation_id,
                    **error.details
                }
            )
        except Exception as e:
            self.logger.warning(f"Failed to log error to audit system: {e}")
    
    async def log_a2a_error_to_audit(self, error: UnifiedError, service_name: str = None):
        """
        Log A2A protocol errors to backend audit system.
        
        Args:
            error: UnifiedError to audit
            service_name: Backend service that failed
        """
        if not self.audit_logger:
            return
        
        try:
            await self.audit_logger.log_security_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                message=f"A2A Communication Error: {error.message}",
                severity=AuditSeverity.MEDIUM if error.recoverable else AuditSeverity.HIGH,
                tenant_id=error.tenant_id,
                correlation_id=error.trace_id,
                details={
                    "error_code": error.error_code.value,
                    "component": self.component,
                    "agent_type": self.agent_type,
                    "service_name": service_name,
                    "recoverable": error.recoverable,
                    "conversation_id": error.conversation_id,
                    **error.details
                }
            )
        except Exception as e:
            self.logger.warning(f"Failed to log A2A error to audit system: {e}")
    
    async def _log_recovery_attempt(self, error: UnifiedError):
        """Log error recovery attempt."""
        if self.audit_logger:
            try:
                await self.audit_logger.log_security_event(
                    event_type=AuditEventType.SYSTEM_INFO,
                    message=f"Attempting error recovery for {error.error_code.value}",
                    severity=AuditSeverity.LOW,
                    tenant_id=error.tenant_id,
                    correlation_id=error.trace_id,
                    details={
                        "error_code": error.error_code.value,
                        "component": self.component,
                        "recovery_strategy": "automatic",
                        "retry_after": error.retry_after
                    }
                )
            except Exception as e:
                self.logger.warning(f"Failed to log recovery attempt: {e}")
    
    async def _log_recovery_failure(self, original_error: UnifiedError, recovery_error: Exception):
        """Log error recovery failure."""
        if self.audit_logger:
            try:
                await self.audit_logger.log_security_event(
                    event_type=AuditEventType.SYSTEM_ERROR,
                    message=f"Error recovery failed for {original_error.error_code.value}",
                    severity=AuditSeverity.MEDIUM,
                    tenant_id=original_error.tenant_id,
                    correlation_id=original_error.trace_id,
                    details={
                        "original_error_code": original_error.error_code.value,
                        "recovery_error": str(recovery_error),
                        "component": self.component
                    }
                )
            except Exception as e:
                self.logger.warning(f"Failed to log recovery failure: {e}")


class ErrorRecoveryStrategy:
    """Strategies for automatic error recovery."""
    
    @staticmethod
    async def exponential_backoff_retry(operation: callable,
                                      max_retries: int = 3,
                                      base_delay: float = 1.0,
                                      max_delay: float = 60.0,
                                      error_handler: UnifiedErrorHandler = None) -> Any:
        """
        Retry operation with exponential backoff.
        
        Args:
            operation: Async operation to retry
            max_retries: Maximum number of retries
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            error_handler: Error handler for logging
            
        Returns:
            Operation result
            
        Raises:
            Last exception if all retries fail
        """
        import asyncio
        import random
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                last_error = e
                
                if error_handler:
                    unified_error = error_handler.handle_a2a_error(e, context={"attempt": attempt})
                    error_handler.log_error(unified_error, level=logging.WARNING)
                
                if attempt < max_retries:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
                    total_delay = delay + jitter
                    
                    await asyncio.sleep(total_delay)
                else:
                    # Last attempt failed, raise the error
                    raise last_error
        
        raise last_error


# Global error handler instances for common components
_error_handlers: Dict[str, UnifiedErrorHandler] = {}


def get_error_handler(component: str, agent_type: str = None) -> UnifiedErrorHandler:
    """
    Get or create error handler for a component.
    
    Args:
        component: Component name
        agent_type: Agent type if applicable
        
    Returns:
        UnifiedErrorHandler instance
    """
    key = f"{component}_{agent_type}" if agent_type else component
    
    if key not in _error_handlers:
        _error_handlers[key] = UnifiedErrorHandler(component, agent_type)
    
    return _error_handlers[key]