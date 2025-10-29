"""
HappyOS Structured Logging

Enterprise-grade structured logging with JSON formatting, correlation IDs,
and integration with observability platforms.
"""

import json
import logging
import sys
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Union
from contextvars import ContextVar

# Context variables for request correlation
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
tenant_id: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)
user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class LogLevel(Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add context information
        if correlation_id.get():
            log_entry["correlation_id"] = correlation_id.get()
        
        if tenant_id.get():
            log_entry["tenant_id"] = tenant_id.get()
        
        if user_id.get():
            log_entry["user_id"] = user_id.get()
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'message'
            }:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class StructuredLogger:
    """
    Structured logger with context management and enterprise features.
    """
    
    def __init__(self, name: str, level: Union[str, LogLevel] = LogLevel.INFO):
        self.logger = logging.getLogger(name)
        
        # Set level
        if isinstance(level, LogLevel):
            level = level.value
        self.logger.setLevel(getattr(logging, level))
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Add structured handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self.logger.error(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.logger.critical(message, extra=kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self.logger.exception(message, extra=kwargs)
    
    def with_context(self, **context) -> 'ContextualLogger':
        """Create a contextual logger with additional context."""
        return ContextualLogger(self.logger, context)


class ContextualLogger:
    """
    Logger that automatically includes context in all log messages.
    """
    
    def __init__(self, logger: logging.Logger, context: Dict[str, Any]):
        self.logger = logger
        self.context = context
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(message, extra={**self.context, **kwargs})
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(message, extra={**self.context, **kwargs})
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(message, extra={**self.context, **kwargs})
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self.logger.error(message, extra={**self.context, **kwargs})
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self.logger.critical(message, extra={**self.context, **kwargs})
    
    def exception(self, message: str, **kwargs):
        """Log exception with context and traceback."""
        self.logger.exception(message, extra={**self.context, **kwargs})


# Global logger cache
_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str, level: Union[str, LogLevel] = LogLevel.INFO) -> StructuredLogger:
    """
    Get or create a structured logger.
    
    Args:
        name: Logger name (typically module name)
        level: Log level
    
    Returns:
        StructuredLogger instance
    """
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name, level)
    
    return _loggers[name]


def set_correlation_id(corr_id: str) -> None:
    """Set correlation ID for current context."""
    correlation_id.set(corr_id)


def set_tenant_id(tenant: str) -> None:
    """Set tenant ID for current context."""
    tenant_id.set(tenant)


def set_user_id(user: str) -> None:
    """Set user ID for current context."""
    user_id.set(user)


def clear_context() -> None:
    """Clear all context variables."""
    correlation_id.set(None)
    tenant_id.set(None)
    user_id.set(None)


class LogContext:
    """
    Context manager for setting log context.
    
    Example:
        with LogContext(correlation_id="123", tenant_id="tenant1"):
            logger.info("This will include context")
    """
    
    def __init__(self, correlation_id: str = None, tenant_id: str = None, user_id: str = None):
        self.correlation_id = correlation_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.previous_correlation_id = None
        self.previous_tenant_id = None
        self.previous_user_id = None
    
    def __enter__(self):
        # Save previous values
        self.previous_correlation_id = correlation_id.get()
        self.previous_tenant_id = tenant_id.get()
        self.previous_user_id = user_id.get()
        
        # Set new values
        if self.correlation_id:
            correlation_id.set(self.correlation_id)
        if self.tenant_id:
            tenant_id.set(self.tenant_id)
        if self.user_id:
            user_id.set(self.user_id)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous values
        correlation_id.set(self.previous_correlation_id)
        tenant_id.set(self.previous_tenant_id)
        user_id.set(self.previous_user_id)