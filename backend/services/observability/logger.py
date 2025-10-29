"""
Structured JSON logging with request/meeting IDs for comprehensive observability.
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional, Union
from pathlib import Path

try:
    from backend.modules.config.settings import settings
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.modules.config.settings import settings


# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
meeting_id_var: ContextVar[Optional[str]] = ContextVar('meeting_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class LogContext:
    """Context manager for setting logging context variables."""
    
    def __init__(self, request_id: Optional[str] = None, 
                 meeting_id: Optional[str] = None,
                 user_id: Optional[str] = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.meeting_id = meeting_id
        self.user_id = user_id
        self._tokens = []
    
    def __enter__(self):
        self._tokens.append(request_id_var.set(self.request_id))
        if self.meeting_id:
            self._tokens.append(meeting_id_var.set(self.meeting_id))
        if self.user_id:
            self._tokens.append(user_id_var.set(self.user_id))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        for token in reversed(self._tokens):
            token.var.set(token.old_value)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        
        # Base log structure
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
        request_id = request_id_var.get()
        meeting_id = meeting_id_var.get()
        user_id = user_id_var.get()
        
        if request_id:
            log_entry["request_id"] = request_id
        if meeting_id:
            log_entry["meeting_id"] = meeting_id
        if user_id:
            log_entry["user_id"] = user_id
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields from record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                'filename', 'module', 'lineno', 'funcName', 'created', 
                'msecs', 'relativeCreated', 'thread', 'threadName', 
                'processName', 'process', 'getMessage', 'exc_info', 
                'exc_text', 'stack_info'
            }:
                try:
                    # Skip context variables that might not be JSON serializable
                    if hasattr(value, '__class__') and 'MISSING' in str(type(value)):
                        continue
                    # Ensure value is JSON serializable
                    json.dumps(value)
                    extra_fields[key] = value
                except (TypeError, ValueError):
                    extra_fields[key] = str(value)
        
        if extra_fields:
            log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False)


class ProductionLogger:
    """Production-grade logger with structured JSON output."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with structured formatting."""
        
        # Avoid duplicate handlers
        if self.logger.handlers:
            return
        
        # Set log level
        log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        self.logger.setLevel(log_level)
        
        # Create structured formatter
        formatter = StructuredFormatter()
        
        # Console handler for development
        if settings.ENVIRONMENT == "development" or settings.BACKEND_DEBUG:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # File handler for production
        if settings.ENVIRONMENT == "production":
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            file_handler = logging.FileHandler(log_dir / "meetmind_backend.log")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            # Error log file
            error_handler = logging.FileHandler(log_dir / "meetmind_errors.log")
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            self.logger.addHandler(error_handler)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with extra context."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with extra context."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with extra context."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with extra context."""
        self.logger.error(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with extra context."""
        self.logger.critical(message, extra=kwargs)
    
    def log_request(self, method: str, path: str, status_code: int, 
                   duration_ms: float, **kwargs):
        """Log HTTP request with structured data."""
        self.info(
            f"{method} {path} - {status_code}",
            http_method=method,
            http_path=path,
            http_status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_ai_call(self, provider: str, model: str, tokens_used: int, 
                   cost: float, duration_ms: float, operation: str, **kwargs):
        """Log AI/LLM call with cost and performance data."""
        self.info(
            f"AI call to {provider}/{model} - {operation}",
            ai_provider=provider,
            ai_model=model,
            ai_tokens_used=tokens_used,
            ai_cost=cost,
            ai_operation=operation,
            duration_ms=duration_ms,
            **kwargs
        )
    
    def log_worker_task(self, task_type: str, task_id: str, status: str, 
                       duration_ms: Optional[float] = None, **kwargs):
        """Log worker task execution."""
        message = f"Worker task {task_type} [{task_id}] - {status}"
        extra = {
            "worker_task_type": task_type,
            "worker_task_id": task_id,
            "worker_task_status": status,
            **kwargs
        }
        
        if duration_ms is not None:
            extra["duration_ms"] = duration_ms
        
        self.info(message, **extra)
    
    def log_database_query(self, query_type: str, table: str, duration_ms: float, 
                          rows_affected: Optional[int] = None, **kwargs):
        """Log database query with performance data."""
        message = f"DB {query_type} on {table}"
        extra = {
            "db_query_type": query_type,
            "db_table": table,
            "duration_ms": duration_ms,
            **kwargs
        }
        
        if rows_affected is not None:
            extra["db_rows_affected"] = rows_affected
        
        self.info(message, **extra)


# Global logger instances
_loggers: Dict[str, ProductionLogger] = {}


def get_logger(name: str) -> ProductionLogger:
    """Get or create a production logger instance."""
    if name not in _loggers:
        _loggers[name] = ProductionLogger(name)
    return _loggers[name]


def setup_structured_logging():
    """Setup structured logging for the entire application."""
    
    # Configure root logger to use structured format
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Create structured formatter
    formatter = StructuredFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for production
    if settings.ENVIRONMENT == "production":
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / "meetmind_backend.log")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from some libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Log setup completion
    logger = get_logger(__name__)
    logger.info("Structured logging initialized", 
                log_level=settings.LOG_LEVEL,
                environment=settings.ENVIRONMENT)


# Request timing decorator
def log_execution_time(logger: Optional[ProductionLogger] = None, 
                      operation: str = "operation"):
    """Decorator to log execution time of functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Completed {operation}",
                    operation=operation,
                    function=func.__name__,
                    duration_ms=duration_ms,
                    status="success"
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Failed {operation}: {str(e)}",
                    operation=operation,
                    function=func.__name__,
                    duration_ms=duration_ms,
                    status="error",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise
        return wrapper
    return decorator