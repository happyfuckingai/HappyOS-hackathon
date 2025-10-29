"""
Unified Observability Integration for HappyOS SDK

This module provides a unified interface for error handling and logging that works
seamlessly across both MCP and Backend Core A2A protocols. It creates a translation
layer that ensures consistent observability patterns across all HappyOS agent systems.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime

from .error_handling import UnifiedErrorHandler, UnifiedError, UnifiedErrorCode, get_error_handler
from .logging import UnifiedLogger, LogContext, get_logger, create_log_context

# Try to import backend observability components for integration
try:
    from backend.modules.observability.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
    from backend.modules.observability.cloudwatch import get_cloudwatch_monitor, MetricUnit
    from backend.modules.observability.xray_tracing import get_xray_tracer, XRaySegmentContext
    BACKEND_OBSERVABILITY_AVAILABLE = True
except ImportError:
    BACKEND_OBSERVABILITY_AVAILABLE = False


@dataclass
class ObservabilityContext:
    """Unified observability context for both MCP and A2A protocols."""
    
    trace_id: Optional[str] = None
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    agent_type: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    protocol: Optional[str] = None  # "mcp" or "a2a"
    
    # MCP-specific context
    target_agent: Optional[str] = None
    tool_name: Optional[str] = None
    reply_to: Optional[str] = None
    
    # A2A-specific context
    service_name: Optional[str] = None
    action: Optional[str] = None
    
    # Common context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    client_ip: Optional[str] = None
    
    def to_log_context(self) -> LogContext:
        """Convert to LogContext for logging."""
        return create_log_context(
            trace_id=self.trace_id,
            conversation_id=self.conversation_id,
            tenant_id=self.tenant_id,
            agent_type=self.agent_type,
            component=self.component,
            operation=self.operation,
            user_id=self.user_id,
            session_id=self.session_id
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for metrics and audit logging."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class UnifiedObservabilityManager:
    """
    Unified observability manager that provides consistent error handling and logging
    across both MCP and Backend Core A2A protocols.
    """
    
    def __init__(self, component: str, agent_type: str = None):
        """
        Initialize observability manager.
        
        Args:
            component: Component name (e.g., "mcp_client", "service_facade")
            agent_type: Agent type if applicable
        """
        self.component = component
        self.agent_type = agent_type
        
        # Initialize core components
        self.error_handler = get_error_handler(component, agent_type)
        self.logger = get_logger(component=component, agent_type=agent_type)
        
        # Initialize backend observability integration if available
        self.audit_logger = None
        self.cloudwatch_monitor = None
        self.xray_tracer = None
        
        if BACKEND_OBSERVABILITY_AVAILABLE:
            try:
                self.audit_logger = get_audit_logger()
                self.cloudwatch_monitor = get_cloudwatch_monitor()
                self.xray_tracer = get_xray_tracer()
                self.logger.info("Backend observability integration initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize backend observability: {e}")
    
    async def execute_with_observability(self,
                                       operation: Callable,
                                       context: ObservabilityContext,
                                       operation_name: str = None) -> Any:
        """
        Execute operation with full observability (logging, metrics, tracing, error handling).
        
        Args:
            operation: Async operation to execute
            context: Observability context
            operation_name: Human-readable operation name
            
        Returns:
            Operation result
            
        Raises:
            UnifiedError: Standardized error if operation fails
        """
        start_time = time.time()
        operation_name = operation_name or context.operation or "unknown_operation"
        
        # Start distributed tracing if available
        trace_context = None
        if self.xray_tracer and context.trace_id:
            segment_name = f"{self.component}_{operation_name}"
            trace_context = XRaySegmentContext(
                segment_name,
                self.xray_tracer,
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                agent_id=context.agent_type,
                correlation_id=context.trace_id
            )
        
        try:
            # Log operation start
            await self._log_operation_start(context, operation_name)
            
            # Execute operation with tracing context if available
            if trace_context:
                with trace_context:
                    result = await operation()
            else:
                result = await operation()
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log successful completion
            await self._log_operation_success(context, operation_name, duration_ms)
            
            # Record success metrics
            await self._record_success_metrics(context, operation_name, duration_ms)
            
            return result
            
        except Exception as e:
            # Calculate duration for error case
            duration_ms = (time.time() - start_time) * 1000
            
            # Create unified error
            unified_error = await self._handle_operation_error(e, context, operation_name, duration_ms)
            
            # Log error
            await self._log_operation_error(unified_error, context, operation_name, duration_ms)
            
            # Record error metrics
            await self._record_error_metrics(unified_error, context, operation_name, duration_ms)
            
            # Log to audit system
            await self._audit_operation_error(unified_error, context, operation_name)
            
            # Attempt recovery if possible
            if unified_error.recoverable:
                recovery_successful = await self.error_handler.attempt_recovery(unified_error)
                if recovery_successful:
                    self.logger.info(
                        f"Error recovery successful for {operation_name}",
                        context=context.to_log_context(),
                        error_code=unified_error.error_code.value
                    )
                    # Could retry the operation here if desired
            
            raise unified_error
    
    async def log_mcp_operation(self,
                              operation_type: str,
                              target_agent: str = None,
                              tool_name: str = None,
                              trace_id: str = None,
                              conversation_id: str = None,
                              tenant_id: str = None,
                              success: bool = True,
                              duration_ms: float = None,
                              error: Exception = None,
                              details: Dict[str, Any] = None):
        """Log MCP operation with unified observability."""
        context = ObservabilityContext(
            trace_id=trace_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            agent_type=self.agent_type,
            component=self.component,
            operation=operation_type,
            protocol="mcp",
            target_agent=target_agent,
            tool_name=tool_name
        )
        
        if success:
            self.logger.log_mcp_call(
                target_agent=target_agent or "unknown",
                tool_name=tool_name or "unknown",
                trace_id=trace_id,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                success=True,
                duration_ms=duration_ms
            )
            
            # Record metrics
            await self._record_mcp_success_metrics(context, duration_ms, details)
            
        else:
            self.logger.log_mcp_call(
                target_agent=target_agent or "unknown",
                tool_name=tool_name or "unknown",
                trace_id=trace_id,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                success=False,
                error=error
            )
            
            # Handle and log error
            if error:
                unified_error = self.error_handler.handle_mcp_error(error, context.to_dict())
                await self.error_handler.log_mcp_error_to_audit(unified_error, operation_type)
                await self._record_mcp_error_metrics(unified_error, context)
    
    async def log_a2a_operation(self,
                              operation_type: str,
                              service_name: str = None,
                              action: str = None,
                              trace_id: str = None,
                              tenant_id: str = None,
                              success: bool = True,
                              duration_ms: float = None,
                              error: Exception = None,
                              details: Dict[str, Any] = None):
        """Log A2A operation with unified observability."""
        context = ObservabilityContext(
            trace_id=trace_id,
            tenant_id=tenant_id,
            agent_type=self.agent_type,
            component=self.component,
            operation=operation_type,
            protocol="a2a",
            service_name=service_name,
            action=action
        )
        
        if success:
            self.logger.log_a2a_call(
                service_name=service_name or "unknown",
                action=action or "unknown",
                trace_id=trace_id,
                tenant_id=tenant_id,
                success=True,
                duration_ms=duration_ms
            )
            
            # Record metrics
            await self._record_a2a_success_metrics(context, duration_ms, details)
            
        else:
            self.logger.log_a2a_call(
                service_name=service_name or "unknown",
                action=action or "unknown",
                trace_id=trace_id,
                tenant_id=tenant_id,
                success=False,
                error=error
            )
            
            # Handle and log error
            if error:
                unified_error = self.error_handler.handle_a2a_error(error, service_name, context.to_dict())
                await self.error_handler.log_a2a_error_to_audit(unified_error, service_name)
                await self._record_a2a_error_metrics(unified_error, context)
    
    async def log_circuit_breaker_event(self,
                                      service_name: str,
                                      event_type: str,
                                      trace_id: str = None,
                                      tenant_id: str = None,
                                      details: Dict[str, Any] = None):
        """Log circuit breaker events with unified observability."""
        context = ObservabilityContext(
            trace_id=trace_id,
            tenant_id=tenant_id,
            agent_type=self.agent_type,
            component=self.component,
            operation="circuit_breaker",
            service_name=service_name
        )
        
        self.logger.log_circuit_breaker_event(
            service_name=service_name,
            event_type=event_type,
            trace_id=trace_id,
            tenant_id=tenant_id,
            details=details
        )
        
        # Record circuit breaker metrics
        await self._record_circuit_breaker_metrics(context, event_type, details)
        
        # Audit critical circuit breaker events
        if event_type in ["opened", "failed"]:
            await self._audit_circuit_breaker_event(context, event_type, details)
    
    async def _log_operation_start(self, context: ObservabilityContext, operation_name: str):
        """Log operation start."""
        self.logger.debug(
            f"Starting {context.protocol or 'unknown'} operation: {operation_name}",
            context=context.to_log_context(),
            **context.to_dict()
        )
    
    async def _log_operation_success(self, context: ObservabilityContext, operation_name: str, duration_ms: float):
        """Log successful operation completion."""
        self.logger.info(
            f"Completed {context.protocol or 'unknown'} operation: {operation_name}",
            context=context.to_log_context(),
            duration_ms=duration_ms,
            **context.to_dict()
        )
    
    async def _log_operation_error(self, error: UnifiedError, context: ObservabilityContext, 
                                 operation_name: str, duration_ms: float):
        """Log operation error."""
        self.logger.log_unified_error(error)
        
        self.logger.error(
            f"Failed {context.protocol or 'unknown'} operation: {operation_name}",
            context=context.to_log_context(),
            duration_ms=duration_ms,
            error_code=error.error_code.value,
            recoverable=error.recoverable,
            **context.to_dict()
        )
    
    async def _handle_operation_error(self, error: Exception, context: ObservabilityContext, 
                                    operation_name: str, duration_ms: float) -> UnifiedError:
        """Handle operation error and create unified error."""
        if context.protocol == "mcp":
            if context.tool_name:
                return self.error_handler.handle_tool_error(error, context.tool_name, context.to_dict())
            else:
                return self.error_handler.handle_mcp_error(error, context.to_dict())
        elif context.protocol == "a2a":
            return self.error_handler.handle_a2a_error(error, context.service_name, context.to_dict())
        else:
            # Generic error handling
            return self.error_handler.create_error(
                UnifiedErrorCode.SYSTEM_ERROR,
                f"Operation failed: {operation_name} - {str(error)}",
                {"operation_name": operation_name, "duration_ms": duration_ms, "original_error": str(error)},
                trace_id=context.trace_id,
                conversation_id=context.conversation_id,
                tenant_id=context.tenant_id,
                recoverable=True,
                include_stack_trace=True
            )
    
    async def _record_success_metrics(self, context: ObservabilityContext, operation_name: str, duration_ms: float):
        """Record success metrics to CloudWatch."""
        if not self.cloudwatch_monitor:
            return
        
        try:
            dimensions = {
                "Component": self.component,
                "Operation": operation_name,
                "Protocol": context.protocol or "unknown"
            }
            
            if context.agent_type:
                dimensions["AgentType"] = context.agent_type
            
            await self.cloudwatch_monitor.put_metric(
                "OperationSuccess",
                1,
                MetricUnit.COUNT,
                dimensions,
                context.tenant_id
            )
            
            await self.cloudwatch_monitor.put_metric(
                "OperationDuration",
                duration_ms,
                MetricUnit.MILLISECONDS,
                dimensions,
                context.tenant_id
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to record success metrics: {e}")
    
    async def _record_error_metrics(self, error: UnifiedError, context: ObservabilityContext, 
                                  operation_name: str, duration_ms: float):
        """Record error metrics to CloudWatch."""
        if not self.cloudwatch_monitor:
            return
        
        try:
            dimensions = {
                "Component": self.component,
                "Operation": operation_name,
                "Protocol": context.protocol or "unknown",
                "ErrorCode": error.error_code.value
            }
            
            if context.agent_type:
                dimensions["AgentType"] = context.agent_type
            
            await self.cloudwatch_monitor.put_metric(
                "OperationError",
                1,
                MetricUnit.COUNT,
                dimensions,
                context.tenant_id
            )
            
            await self.cloudwatch_monitor.put_metric(
                "ErrorDuration",
                duration_ms,
                MetricUnit.MILLISECONDS,
                dimensions,
                context.tenant_id
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to record error metrics: {e}")
    
    async def _record_mcp_success_metrics(self, context: ObservabilityContext, duration_ms: float, details: Dict[str, Any] = None):
        """Record MCP-specific success metrics."""
        if not self.cloudwatch_monitor:
            return
        
        try:
            dimensions = {
                "Component": self.component,
                "Protocol": "mcp",
                "TargetAgent": context.target_agent or "unknown",
                "ToolName": context.tool_name or "unknown"
            }
            
            if context.agent_type:
                dimensions["SourceAgent"] = context.agent_type
            
            await self.cloudwatch_monitor.put_metric(
                "MCPCallSuccess",
                1,
                MetricUnit.COUNT,
                dimensions,
                context.tenant_id
            )
            
            if duration_ms:
                await self.cloudwatch_monitor.put_metric(
                    "MCPCallDuration",
                    duration_ms,
                    MetricUnit.MILLISECONDS,
                    dimensions,
                    context.tenant_id
                )
            
        except Exception as e:
            self.logger.warning(f"Failed to record MCP success metrics: {e}")
    
    async def _record_mcp_error_metrics(self, error: UnifiedError, context: ObservabilityContext):
        """Record MCP-specific error metrics."""
        if not self.cloudwatch_monitor:
            return
        
        try:
            dimensions = {
                "Component": self.component,
                "Protocol": "mcp",
                "ErrorCode": error.error_code.value,
                "TargetAgent": context.target_agent or "unknown",
                "ToolName": context.tool_name or "unknown"
            }
            
            if context.agent_type:
                dimensions["SourceAgent"] = context.agent_type
            
            await self.cloudwatch_monitor.put_metric(
                "MCPCallError",
                1,
                MetricUnit.COUNT,
                dimensions,
                context.tenant_id
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to record MCP error metrics: {e}")
    
    async def _record_a2a_success_metrics(self, context: ObservabilityContext, duration_ms: float, details: Dict[str, Any] = None):
        """Record A2A-specific success metrics."""
        if not self.cloudwatch_monitor:
            return
        
        try:
            dimensions = {
                "Component": self.component,
                "Protocol": "a2a",
                "ServiceName": context.service_name or "unknown",
                "Action": context.action or "unknown"
            }
            
            if context.agent_type:
                dimensions["AgentType"] = context.agent_type
            
            await self.cloudwatch_monitor.put_metric(
                "A2ACallSuccess",
                1,
                MetricUnit.COUNT,
                dimensions,
                context.tenant_id
            )
            
            if duration_ms:
                await self.cloudwatch_monitor.put_metric(
                    "A2ACallDuration",
                    duration_ms,
                    MetricUnit.MILLISECONDS,
                    dimensions,
                    context.tenant_id
                )
            
        except Exception as e:
            self.logger.warning(f"Failed to record A2A success metrics: {e}")
    
    async def _record_a2a_error_metrics(self, error: UnifiedError, context: ObservabilityContext):
        """Record A2A-specific error metrics."""
        if not self.cloudwatch_monitor:
            return
        
        try:
            dimensions = {
                "Component": self.component,
                "Protocol": "a2a",
                "ErrorCode": error.error_code.value,
                "ServiceName": context.service_name or "unknown",
                "Action": context.action or "unknown"
            }
            
            if context.agent_type:
                dimensions["AgentType"] = context.agent_type
            
            await self.cloudwatch_monitor.put_metric(
                "A2ACallError",
                1,
                MetricUnit.COUNT,
                dimensions,
                context.tenant_id
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to record A2A error metrics: {e}")
    
    async def _record_circuit_breaker_metrics(self, context: ObservabilityContext, event_type: str, details: Dict[str, Any] = None):
        """Record circuit breaker metrics."""
        if not self.cloudwatch_monitor:
            return
        
        try:
            dimensions = {
                "Component": self.component,
                "ServiceName": context.service_name or "unknown",
                "EventType": event_type
            }
            
            if context.agent_type:
                dimensions["AgentType"] = context.agent_type
            
            await self.cloudwatch_monitor.put_metric(
                "CircuitBreakerEvent",
                1,
                MetricUnit.COUNT,
                dimensions,
                context.tenant_id
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to record circuit breaker metrics: {e}")
    
    async def _audit_operation_error(self, error: UnifiedError, context: ObservabilityContext, operation_name: str):
        """Audit operation errors."""
        if not self.audit_logger:
            return
        
        try:
            # Determine audit severity based on error type
            if error.error_code in [UnifiedErrorCode.AUTHENTICATION_FAILED, UnifiedErrorCode.AUTHORIZATION_FAILED]:
                severity = AuditSeverity.HIGH
                event_type = AuditEventType.AUTH_PERMISSION_DENIED
            elif error.error_code == UnifiedErrorCode.TENANT_ISOLATION_VIOLATION:
                severity = AuditSeverity.CRITICAL
                event_type = AuditEventType.TENANT_ISOLATION_VIOLATION
            elif error.recoverable:
                severity = AuditSeverity.LOW
                event_type = AuditEventType.SYSTEM_WARNING
            else:
                severity = AuditSeverity.MEDIUM
                event_type = AuditEventType.SYSTEM_ERROR
            
            await self.audit_logger.log_security_event(
                event_type=event_type,
                message=f"HappyOS SDK operation error: {operation_name}",
                severity=severity,
                tenant_id=context.tenant_id,
                correlation_id=context.trace_id,
                details={
                    "error_code": error.error_code.value,
                    "component": self.component,
                    "agent_type": self.agent_type,
                    "operation": operation_name,
                    "protocol": context.protocol,
                    "recoverable": error.recoverable,
                    **context.to_dict(),
                    **error.details
                }
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to audit operation error: {e}")
    
    async def _audit_circuit_breaker_event(self, context: ObservabilityContext, event_type: str, details: Dict[str, Any] = None):
        """Audit critical circuit breaker events."""
        if not self.audit_logger:
            return
        
        try:
            severity = AuditSeverity.HIGH if event_type == "opened" else AuditSeverity.MEDIUM
            
            await self.audit_logger.log_security_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                message=f"Circuit breaker {event_type}: {context.service_name}",
                severity=severity,
                tenant_id=context.tenant_id,
                correlation_id=context.trace_id,
                details={
                    "component": self.component,
                    "agent_type": self.agent_type,
                    "service_name": context.service_name,
                    "event_type": event_type,
                    **(details or {})
                }
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to audit circuit breaker event: {e}")


# Global observability manager instances
_observability_managers: Dict[str, UnifiedObservabilityManager] = {}


def get_observability_manager(component: str, agent_type: str = None) -> UnifiedObservabilityManager:
    """
    Get or create unified observability manager for a component.
    
    Args:
        component: Component name
        agent_type: Agent type if applicable
        
    Returns:
        UnifiedObservabilityManager instance
    """
    key = f"{component}_{agent_type}" if agent_type else component
    
    if key not in _observability_managers:
        _observability_managers[key] = UnifiedObservabilityManager(component, agent_type)
    
    return _observability_managers[key]


# Convenience decorators for automatic observability
def with_mcp_observability(target_agent: str = None, tool_name: str = None):
    """Decorator to add MCP observability to async functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract context from kwargs or function arguments
            trace_id = kwargs.get('trace_id')
            conversation_id = kwargs.get('conversation_id')
            tenant_id = kwargs.get('tenant_id')
            
            # Get observability manager
            component = func.__module__.split('.')[-1] if hasattr(func, '__module__') else 'unknown'
            manager = get_observability_manager(component)
            
            # Create context
            context = ObservabilityContext(
                trace_id=trace_id,
                conversation_id=conversation_id,
                tenant_id=tenant_id,
                component=component,
                operation=func.__name__,
                protocol="mcp",
                target_agent=target_agent,
                tool_name=tool_name
            )
            
            # Execute with observability
            return await manager.execute_with_observability(
                lambda: func(*args, **kwargs),
                context,
                func.__name__
            )
        
        return wrapper
    return decorator


def with_a2a_observability(service_name: str = None, action: str = None):
    """Decorator to add A2A observability to async functions."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract context from kwargs or function arguments
            trace_id = kwargs.get('trace_id')
            tenant_id = kwargs.get('tenant_id')
            
            # Get observability manager
            component = func.__module__.split('.')[-1] if hasattr(func, '__module__') else 'unknown'
            manager = get_observability_manager(component)
            
            # Create context
            context = ObservabilityContext(
                trace_id=trace_id,
                tenant_id=tenant_id,
                component=component,
                operation=func.__name__,
                protocol="a2a",
                service_name=service_name,
                action=action
            )
            
            # Execute with observability
            return await manager.execute_with_observability(
                lambda: func(*args, **kwargs),
                context,
                func.__name__
            )
        
        return wrapper
    return decorator