"""
Distributed tracing from HTTP requests through worker processes to LLM calls.
"""

import time
import uuid
from contextvars import ContextVar
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps

try:
    import sentry_sdk
    from sentry_sdk import start_transaction, start_span
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.httpx import HttpxIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    # Mock Sentry functions
    def start_transaction(*args, **kwargs):
        return MockTransaction()
    def start_span(*args, **kwargs):
        return MockSpan()
    
    class MockTransaction:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def set_tag(self, *args): pass
        def set_data(self, *args): pass
    
    class MockSpan:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def set_tag(self, *args): pass
        def set_data(self, *args): pass

try:
    from backend.modules.config.settings import settings
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.modules.config.settings import settings
from .logger import get_logger


# Context variables for tracing
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar('span_id', default=None)
parent_span_id_var: ContextVar[Optional[str]] = ContextVar('parent_span_id', default=None)


@dataclass
class TraceSpan:
    """Represents a trace span with timing and metadata."""
    
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"  # ok, error, timeout
    
    def finish(self):
        """Mark span as finished and calculate duration."""
        self.end_time = datetime.now(timezone.utc)
        if self.start_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
    
    def set_tag(self, key: str, value: Any):
        """Set a tag on the span."""
        self.tags[key] = value
    
    def log(self, message: str, **kwargs):
        """Add a log entry to the span."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            **kwargs
        }
        self.logs.append(log_entry)
    
    def set_error(self, error: Exception):
        """Mark span as error and add error details."""
        self.status = "error"
        self.set_tag("error", True)
        self.set_tag("error.type", type(error).__name__)
        self.set_tag("error.message", str(error))
        self.log("error", error_type=type(error).__name__, error_message=str(error))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for serialization."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "tags": self.tags,
            "logs": self.logs,
            "status": self.status
        }


class TracingManager:
    """Manages distributed tracing across the application."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.active_spans: Dict[str, TraceSpan] = {}
        self._setup_sentry()
    
    def _setup_sentry(self):
        """Setup Sentry integration if available and configured."""
        if SENTRY_AVAILABLE and settings.SENTRY_DSN:
            try:
                sentry_sdk.init(
                    dsn=settings.SENTRY_DSN,
                    environment=settings.ENVIRONMENT,
                    traces_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 1.0,
                    integrations=[
                        FastApiIntegration(auto_enabling_integrations=False),
                        SqlalchemyIntegration(),
                        HttpxIntegration(),
                    ],
                    send_default_pii=False,
                    attach_stacktrace=True,
                    max_breadcrumbs=50,
                )
                self.logger.info("Sentry tracing initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Sentry: {e}")
        else:
            if not SENTRY_AVAILABLE:
                self.logger.warning("Sentry SDK not available - using local tracing only")
            elif not settings.SENTRY_DSN:
                self.logger.info("Sentry DSN not configured - using local tracing only")
    
    def start_trace(self, operation_name: str, **tags) -> TraceSpan:
        """Start a new trace (root span)."""
        span = TraceSpan(operation_name=operation_name)
        span.tags.update(tags)
        
        # Set context variables
        trace_id_var.set(span.trace_id)
        span_id_var.set(span.span_id)
        parent_span_id_var.set(None)
        
        self.active_spans[span.span_id] = span
        
        self.logger.debug(
            f"Started trace: {operation_name}",
            trace_id=span.trace_id,
            span_id=span.span_id,
            operation=operation_name
        )
        
        return span
    
    def start_span(self, operation_name: str, parent_span_id: Optional[str] = None, **tags) -> TraceSpan:
        """Start a new span within an existing trace."""
        current_trace_id = trace_id_var.get()
        current_span_id = span_id_var.get()
        
        if not current_trace_id:
            # No active trace, start a new one
            return self.start_trace(operation_name, **tags)
        
        span = TraceSpan(
            trace_id=current_trace_id,
            operation_name=operation_name,
            parent_span_id=parent_span_id or current_span_id
        )
        span.tags.update(tags)
        
        # Update context variables
        span_id_var.set(span.span_id)
        parent_span_id_var.set(span.parent_span_id)
        
        self.active_spans[span.span_id] = span
        
        self.logger.debug(
            f"Started span: {operation_name}",
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            operation=operation_name
        )
        
        return span
    
    def finish_span(self, span: TraceSpan):
        """Finish a span and remove from active spans."""
        span.finish()
        
        # Log span completion
        self.logger.debug(
            f"Finished span: {span.operation_name}",
            trace_id=span.trace_id,
            span_id=span.span_id,
            duration_ms=span.duration_ms,
            status=span.status
        )
        
        # Remove from active spans
        if span.span_id in self.active_spans:
            del self.active_spans[span.span_id]
        
        # Restore parent context
        if span.parent_span_id:
            span_id_var.set(span.parent_span_id)
            parent_span = self.active_spans.get(span.parent_span_id)
            if parent_span:
                parent_span_id_var.set(parent_span.parent_span_id)
    
    def get_current_trace_id(self) -> Optional[str]:
        """Get current trace ID from context."""
        return trace_id_var.get()
    
    def get_current_span_id(self) -> Optional[str]:
        """Get current span ID from context."""
        return span_id_var.get()
    
    def add_span_tag(self, key: str, value: Any):
        """Add tag to current span."""
        current_span_id = span_id_var.get()
        if current_span_id and current_span_id in self.active_spans:
            self.active_spans[current_span_id].set_tag(key, value)
    
    def log_to_span(self, message: str, **kwargs):
        """Add log entry to current span."""
        current_span_id = span_id_var.get()
        if current_span_id and current_span_id in self.active_spans:
            self.active_spans[current_span_id].log(message, **kwargs)
    
    def record_error(self, error: Exception):
        """Record error in current span."""
        current_span_id = span_id_var.get()
        if current_span_id and current_span_id in self.active_spans:
            self.active_spans[current_span_id].set_error(error)
    
    def trace_http_request(self, method: str, path: str, **tags):
        """Create span for HTTP request."""
        return self.start_span(
            f"HTTP {method} {path}",
            http_method=method,
            http_path=path,
            component="http",
            **tags
        )
    
    def trace_ai_call(self, provider: str, model: str, operation: str, **tags):
        """Create span for AI/LLM call."""
        return self.start_span(
            f"AI {provider}/{model} {operation}",
            ai_provider=provider,
            ai_model=model,
            ai_operation=operation,
            component="ai",
            **tags
        )
    
    def trace_db_query(self, query_type: str, table: str, **tags):
        """Create span for database query."""
        return self.start_span(
            f"DB {query_type} {table}",
            db_query_type=query_type,
            db_table=table,
            component="database",
            **tags
        )
    
    def trace_worker_task(self, task_type: str, task_id: str, **tags):
        """Create span for worker task."""
        return self.start_span(
            f"Worker {task_type}",
            worker_task_type=task_type,
            worker_task_id=task_id,
            component="worker",
            **tags
        )
    
    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """Get summary of all spans in a trace."""
        trace_spans = [
            span for span in self.active_spans.values() 
            if span.trace_id == trace_id
        ]
        
        if not trace_spans:
            return {}
        
        root_span = min(trace_spans, key=lambda s: s.start_time)
        total_duration = max(
            (span.end_time or datetime.now(timezone.utc)) - root_span.start_time
            for span in trace_spans
        ).total_seconds() * 1000
        
        return {
            "trace_id": trace_id,
            "root_operation": root_span.operation_name,
            "total_duration_ms": total_duration,
            "span_count": len(trace_spans),
            "error_count": sum(1 for span in trace_spans if span.status == "error"),
            "spans": [span.to_dict() for span in trace_spans]
        }


# Global tracing manager instance
_tracing_manager: Optional[TracingManager] = None


def get_tracing_manager() -> TracingManager:
    """Get or create the global tracing manager."""
    global _tracing_manager
    if _tracing_manager is None:
        _tracing_manager = TracingManager()
    return _tracing_manager


def trace_operation(operation_name: str, component: str = "general", **tags):
    """Decorator to automatically trace function execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracing = get_tracing_manager()
            
            # Create span with function metadata
            span_tags = {
                "component": component,
                "function": func.__name__,
                "module": func.__module__,
                **tags
            }
            
            span = tracing.start_span(operation_name, **span_tags)
            
            try:
                result = func(*args, **kwargs)
                span.set_tag("status", "success")
                return result
            except Exception as e:
                span.set_error(e)
                tracing.record_error(e)
                raise
            finally:
                tracing.finish_span(span)
        
        return wrapper
    return decorator


class TraceContext:
    """Context manager for manual span management."""
    
    def __init__(self, operation_name: str, **tags):
        self.operation_name = operation_name
        self.tags = tags
        self.span = None
        self.tracing = get_tracing_manager()
    
    def __enter__(self) -> TraceSpan:
        self.span = self.tracing.start_span(self.operation_name, **self.tags)
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type:
                self.span.set_error(exc_val)
                self.tracing.record_error(exc_val)
            self.tracing.finish_span(self.span)