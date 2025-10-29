"""
Unified Logging for HappyOS SDK

Provides standardized logging with trace-id correlation that works across
both MCP and Backend Core A2A protocols.

This module creates a translation layer between SDK logging and backend
observability systems, ensuring consistent logging patterns across all
HappyOS agent systems.
"""

import logging
import json
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from .error_handling import UnifiedError

# Try to import backend observability components for integration
try:
    from backend.services.observability.logger import get_logger as get_backend_logger, LogContext as BackendLogContext
    from backend.modules.observability.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
    BACKEND_OBSERVABILITY_AVAILABLE = True
except ImportError:
    BACKEND_OBSERVABILITY_AVAILABLE = False


@dataclass
class LogContext:
    """Standardized log context across all HappyOS agent systems."""
    
    trace_id: Optional[str] = None
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    agent_type: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class UnifiedLogger:
    """Standardized logger for HappyOS SDK components."""
    
    def __init__(self, name: str, component: str = None, agent_type: str = None):
        """
        Initialize unified logger.
        
        Args:
            name: Logger name
            component: Component name
            agent_type: Agent type if applicable
        """
        self.logger = logging.getLogger(name)
        self.component = component
        self.agent_type = agent_type
        self.default_context = LogContext(
            component=component,
            agent_type=agent_type
        )
    
    def _merge_context(self, context: LogContext = None, **kwargs) -> Dict[str, Any]:
        """Merge default context with provided context."""
        merged_context = self.default_context.to_dict()
        
        if context:
            merged_context.update(context.to_dict())
        
        # Override with any direct kwargs
        merged_context.update({k: v for k, v in kwargs.items() if v is not None})
        
        return merged_context
    
    def debug(self, message: str, context: LogContext = None, **kwargs):
        """Log debug message with context."""
        extra = self._merge_context(context, **kwargs)
        self.logger.debug(message, extra=extra)
    
    def info(self, message: str, context: LogContext = None, **kwargs):
        """Log info message with context."""
        extra = self._merge_context(context, **kwargs)
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, context: LogContext = None, **kwargs):
        """Log warning message with context."""
        extra = self._merge_context(context, **kwargs)
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, context: LogContext = None, error: Exception = None, **kwargs):
        """Log error message with context."""
        extra = self._merge_context(context, **kwargs)
        
        if error:
            extra["error_type"] = type(error).__name__
            extra["error_message"] = str(error)
        
        self.logger.error(message, extra=extra, exc_info=error is not None)
    
    def critical(self, message: str, context: LogContext = None, error: Exception = None, **kwargs):
        """Log critical message with context."""
        extra = self._merge_context(context, **kwargs)
        
        if error:
            extra["error_type"] = type(error).__name__
            extra["error_message"] = str(error)
        
        self.logger.critical(message, extra=extra, exc_info=error is not None)
    
    def log_mcp_call(self, 
                    target_agent: str,
                    tool_name: str,
                    trace_id: str,
                    conversation_id: str = None,
                    tenant_id: str = None,
                    success: bool = True,
                    duration_ms: float = None,
                    error: Exception = None):
        """Log MCP tool call with standardized format."""
        context = LogContext(
            trace_id=trace_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            operation="mcp_call"
        )
        
        extra = {
            "target_agent": target_agent,
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms
        }
        
        if success:
            self.info(
                f"MCP call successful: {tool_name} -> {target_agent}",
                context=context,
                **extra
            )
        else:
            self.error(
                f"MCP call failed: {tool_name} -> {target_agent}",
                context=context,
                error=error,
                **extra
            )
    
    def log_mcp_callback(self,
                        source_agent: str,
                        tool_name: str,
                        trace_id: str,
                        conversation_id: str = None,
                        tenant_id: str = None,
                        success: bool = True,
                        error: Exception = None):
        """Log MCP callback with standardized format."""
        context = LogContext(
            trace_id=trace_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            operation="mcp_callback"
        )
        
        extra = {
            "source_agent": source_agent,
            "tool_name": tool_name,
            "success": success
        }
        
        if success:
            self.info(
                f"MCP callback received: {tool_name} from {source_agent}",
                context=context,
                **extra
            )
        else:
            self.error(
                f"MCP callback failed: {tool_name} from {source_agent}",
                context=context,
                error=error,
                **extra
            )
    
    def log_a2a_call(self,
                    service_name: str,
                    action: str,
                    trace_id: str = None,
                    tenant_id: str = None,
                    success: bool = True,
                    duration_ms: float = None,
                    error: Exception = None):
        """Log A2A service call with standardized format."""
        context = LogContext(
            trace_id=trace_id,
            tenant_id=tenant_id,
            operation="a2a_call"
        )
        
        extra = {
            "service_name": service_name,
            "action": action,
            "success": success,
            "duration_ms": duration_ms
        }
        
        if success:
            self.info(
                f"A2A call successful: {action} -> {service_name}",
                context=context,
                **extra
            )
        else:
            self.error(
                f"A2A call failed: {action} -> {service_name}",
                context=context,
                error=error,
                **extra
            )
    
    def log_circuit_breaker_event(self,
                                 service_name: str,
                                 event_type: str,
                                 trace_id: str = None,
                                 tenant_id: str = None,
                                 details: Dict[str, Any] = None):
        """Log circuit breaker events."""
        context = LogContext(
            trace_id=trace_id,
            tenant_id=tenant_id,
            operation="circuit_breaker"
        )
        
        extra = {
            "service_name": service_name,
            "event_type": event_type,
            **(details or {})
        }
        
        if event_type in ["opened", "failed"]:
            self.warning(
                f"Circuit breaker {event_type}: {service_name}",
                context=context,
                **extra
            )
        else:
            self.info(
                f"Circuit breaker {event_type}: {service_name}",
                context=context,
                **extra
            )
    
    def log_unified_error(self, error: UnifiedError):
        """Log unified error with full context."""
        context = LogContext(
            trace_id=error.trace_id,
            conversation_id=error.conversation_id,
            tenant_id=error.tenant_id,
            agent_type=error.agent_type,
            component=error.component
        )
        
        extra = {
            "error_code": error.error_code.value,
            "recoverable": error.recoverable,
            "retry_after": error.retry_after,
            **error.details
        }
        
        if error.recoverable:
            self.warning(
                f"Recoverable error: {error.message}",
                context=context,
                **extra
            )
        else:
            self.error(
                f"Non-recoverable error: {error.message}",
                context=context,
                **extra
            )


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields from the record
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname", 
                          "filename", "module", "lineno", "funcName", "created", 
                          "msecs", "relativeCreated", "thread", "threadName", 
                          "processName", "process", "getMessage", "exc_info", 
                          "exc_text", "stack_info"]:
                log_data[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, separators=(',', ':'))


def setup_logging(level: str = "INFO", 
                 format_type: str = "json",
                 component: str = None,
                 agent_type: str = None) -> UnifiedLogger:
    """
    Setup standardized logging for HappyOS SDK.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ("json" or "text")
        component: Component name
        agent_type: Agent type if applicable
        
    Returns:
        UnifiedLogger instance
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    
    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Create unified logger
    logger_name = f"happyos_sdk"
    if component:
        logger_name += f".{component}"
    if agent_type:
        logger_name += f".{agent_type}"
    
    return UnifiedLogger(logger_name, component, agent_type)


# Global logger instances
_loggers: Dict[str, UnifiedLogger] = {}


def get_logger(name: str = None, component: str = None, agent_type: str = None) -> UnifiedLogger:
    """
    Get or create unified logger.
    
    Args:
        name: Logger name (defaults to happyos_sdk)
        component: Component name
        agent_type: Agent type if applicable
        
    Returns:
        UnifiedLogger instance
    """
    if name is None:
        name = "happyos_sdk"
        if component:
            name += f".{component}"
        if agent_type:
            name += f".{agent_type}"
    
    key = f"{name}_{component}_{agent_type}"
    
    if key not in _loggers:
        _loggers[key] = UnifiedLogger(name, component, agent_type)
    
    return _loggers[key]


# Convenience function for creating context
def create_log_context(trace_id: str = None,
                      conversation_id: str = None,
                      tenant_id: str = None,
                      agent_type: str = None,
                      component: str = None,
                      operation: str = None,
                      user_id: str = None,
                      session_id: str = None) -> LogContext:
    """Create log context with provided parameters."""
    return LogContext(
        trace_id=trace_id,
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        agent_type=agent_type,
        component=component,
        operation=operation,
        user_id=user_id,
        session_id=session_id
    )