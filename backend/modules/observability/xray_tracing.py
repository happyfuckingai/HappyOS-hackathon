"""
AWS X-Ray distributed tracing integration.
"""

import time
import uuid
import json
from typing import Dict, Optional, Any, List
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps

try:
    from aws_xray_sdk.core import xray_recorder, patch_all
    from aws_xray_sdk.core.context import Context
    from aws_xray_sdk.core.models.segment import Segment
    from aws_xray_sdk.core.models.subsegment import Subsegment
    XRAY_AVAILABLE = True
except ImportError:
    XRAY_AVAILABLE = False
    # Mock X-Ray classes
    class MockXRayRecorder:
        def configure(self, **kwargs): pass
        def begin_segment(self, name, **kwargs): return MockSegment()
        def end_segment(self): pass
        def begin_subsegment(self, name, **kwargs): return MockSubsegment()
        def end_subsegment(self): pass
        def put_annotation(self, key, value): pass
        def put_metadata(self, key, value, namespace="default"): pass
        def current_segment(self): return MockSegment()
        def current_subsegment(self): return MockSubsegment()
    
    class MockSegment:
        def __init__(self):
            self.id = str(uuid.uuid4())
            self.trace_id = str(uuid.uuid4())
        def put_annotation(self, key, value): pass
        def put_metadata(self, key, value, namespace="default"): pass
        def add_exception(self, exception): pass
        def set_user(self, user): pass
    
    class MockSubsegment:
        def __init__(self):
            self.id = str(uuid.uuid4())
        def put_annotation(self, key, value): pass
        def put_metadata(self, key, value, namespace="default"): pass
        def add_exception(self, exception): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    xray_recorder = MockXRayRecorder()
    def patch_all(): pass

try:
    from backend.modules.config.settings import settings
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.modules.config.settings import settings

from backend.services.observability.logger import get_logger


# Context variables for correlation IDs
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)


@dataclass
class TraceContext:
    """Enhanced trace context with correlation IDs and tenant information."""
    
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    segment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging and metadata."""
        return {
            "trace_id": self.trace_id,
            "segment_id": self.segment_id,
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "start_time": self.start_time.isoformat()
        }


class XRayTracer:
    """AWS X-Ray distributed tracing with correlation ID management."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._setup_xray()
    
    def _setup_xray(self):
        """Setup X-Ray tracing configuration."""
        if not XRAY_AVAILABLE:
            self.logger.warning("AWS X-Ray SDK not available - tracing will be no-op")
            return
        
        try:
            # Configure X-Ray recorder
            xray_recorder.configure(
                context_missing='LOG_ERROR',
                plugins=('EC2Plugin', 'ECSPlugin'),
                daemon_address=getattr(settings, 'XRAY_DAEMON_ADDRESS', '127.0.0.1:2000'),
                use_ssl=False,
                service=f"meetmind-mcp-ui-hub-{settings.ENVIRONMENT}"
            )
            
            # Patch AWS SDK and HTTP libraries
            if settings.ENVIRONMENT != "development":
                patch_all()
            
            self.logger.info("X-Ray tracing initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize X-Ray tracing: {e}")
    
    def start_segment(
        self,
        name: str,
        tenant_id: str = None,
        session_id: str = None,
        agent_id: str = None,
        user_id: str = None,
        **annotations
    ) -> TraceContext:
        """Start a new X-Ray segment with enhanced context."""
        context = TraceContext(
            tenant_id=tenant_id,
            session_id=session_id,
            agent_id=agent_id,
            user_id=user_id
        )
        
        # Set context variables
        correlation_id_var.set(context.correlation_id)
        request_id_var.set(context.request_id)
        if tenant_id:
            tenant_id_var.set(tenant_id)
        
        try:
            # Start X-Ray segment
            segment = xray_recorder.begin_segment(name)
            
            # Add standard annotations
            xray_recorder.put_annotation("correlation_id", context.correlation_id)
            xray_recorder.put_annotation("request_id", context.request_id)
            xray_recorder.put_annotation("environment", settings.ENVIRONMENT)
            
            if tenant_id:
                xray_recorder.put_annotation("tenant_id", tenant_id)
            if session_id:
                xray_recorder.put_annotation("session_id", session_id)
            if agent_id:
                xray_recorder.put_annotation("agent_id", agent_id)
            if user_id:
                xray_recorder.put_annotation("user_id", user_id)
            
            # Add custom annotations
            for key, value in annotations.items():
                xray_recorder.put_annotation(key, str(value))
            
            # Add metadata
            xray_recorder.put_metadata("trace_context", context.to_dict(), "meetmind")
            
            # Update context with actual segment info
            if hasattr(segment, 'id'):
                context.segment_id = segment.id
            if hasattr(segment, 'trace_id'):
                context.trace_id = segment.trace_id
            
            self.logger.debug(
                f"Started X-Ray segment: {name}",
                **context.to_dict()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to start X-Ray segment: {e}")
        
        return context
    
    def end_segment(self):
        """End the current X-Ray segment."""
        try:
            xray_recorder.end_segment()
            self.logger.debug("Ended X-Ray segment")
        except Exception as e:
            self.logger.error(f"Failed to end X-Ray segment: {e}")
    
    def start_subsegment(
        self,
        name: str,
        subsegment_type: str = "subsegment",  # subsegment, aws, http
        **annotations
    ) -> Optional[Any]:
        """Start a new X-Ray subsegment."""
        try:
            subsegment = xray_recorder.begin_subsegment(name, namespace=subsegment_type)
            
            # Add correlation ID to subsegment
            correlation_id = correlation_id_var.get()
            if correlation_id:
                xray_recorder.put_annotation("correlation_id", correlation_id)
            
            # Add tenant context
            tenant_id = tenant_id_var.get()
            if tenant_id:
                xray_recorder.put_annotation("tenant_id", tenant_id)
            
            # Add custom annotations
            for key, value in annotations.items():
                xray_recorder.put_annotation(key, str(value))
            
            self.logger.debug(f"Started X-Ray subsegment: {name}")
            return subsegment
            
        except Exception as e:
            self.logger.error(f"Failed to start X-Ray subsegment: {e}")
            return None
    
    def end_subsegment(self):
        """End the current X-Ray subsegment."""
        try:
            xray_recorder.end_subsegment()
            self.logger.debug("Ended X-Ray subsegment")
        except Exception as e:
            self.logger.error(f"Failed to end X-Ray subsegment: {e}")
    
    def add_annotation(self, key: str, value: Any):
        """Add annotation to current segment/subsegment."""
        try:
            xray_recorder.put_annotation(key, str(value))
        except Exception as e:
            self.logger.error(f"Failed to add X-Ray annotation: {e}")
    
    def add_metadata(self, key: str, value: Any, namespace: str = "meetmind"):
        """Add metadata to current segment/subsegment."""
        try:
            xray_recorder.put_metadata(key, value, namespace)
        except Exception as e:
            self.logger.error(f"Failed to add X-Ray metadata: {e}")
    
    def record_exception(self, exception: Exception):
        """Record exception in current segment/subsegment."""
        try:
            current_segment = xray_recorder.current_segment()
            if current_segment:
                current_segment.add_exception(exception)
            
            # Also add as annotation for easier filtering
            self.add_annotation("error", True)
            self.add_annotation("error_type", type(exception).__name__)
            
        except Exception as e:
            self.logger.error(f"Failed to record X-Ray exception: {e}")
    
    def trace_http_request(
        self,
        method: str,
        path: str,
        tenant_id: str = None,
        session_id: str = None,
        **annotations
    ):
        """Create subsegment for HTTP request tracing."""
        return self.start_subsegment(
            f"HTTP {method} {path}",
            subsegment_type="http",
            http_method=method,
            http_path=path,
            tenant_id=tenant_id or tenant_id_var.get(),
            session_id=session_id,
            **annotations
        )
    
    def trace_database_operation(
        self,
        operation: str,
        table: str,
        tenant_id: str = None,
        **annotations
    ):
        """Create subsegment for database operation tracing."""
        return self.start_subsegment(
            f"DB {operation} {table}",
            subsegment_type="aws",
            db_operation=operation,
            db_table=table,
            tenant_id=tenant_id or tenant_id_var.get(),
            **annotations
        )
    
    def trace_mcp_operation(
        self,
        operation: str,
        agent_id: str,
        tenant_id: str = None,
        session_id: str = None,
        **annotations
    ):
        """Create subsegment for MCP operation tracing."""
        return self.start_subsegment(
            f"MCP {operation}",
            subsegment_type="subsegment",
            mcp_operation=operation,
            agent_id=agent_id,
            tenant_id=tenant_id or tenant_id_var.get(),
            session_id=session_id,
            **annotations
        )
    
    def trace_websocket_operation(
        self,
        operation: str,
        tenant_id: str = None,
        session_id: str = None,
        **annotations
    ):
        """Create subsegment for WebSocket operation tracing."""
        return self.start_subsegment(
            f"WebSocket {operation}",
            subsegment_type="subsegment",
            ws_operation=operation,
            tenant_id=tenant_id or tenant_id_var.get(),
            session_id=session_id,
            **annotations
        )
    
    def get_current_trace_context(self) -> Optional[TraceContext]:
        """Get current trace context with correlation IDs."""
        try:
            segment = xray_recorder.current_segment()
            if not segment:
                return None
            
            return TraceContext(
                trace_id=getattr(segment, 'trace_id', str(uuid.uuid4())),
                segment_id=getattr(segment, 'id', str(uuid.uuid4())),
                correlation_id=correlation_id_var.get() or str(uuid.uuid4()),
                request_id=request_id_var.get() or str(uuid.uuid4()),
                tenant_id=tenant_id_var.get()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get current trace context: {e}")
            return None
    
    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID."""
        return correlation_id_var.get()
    
    def get_request_id(self) -> Optional[str]:
        """Get current request ID."""
        return request_id_var.get()
    
    def get_tenant_id(self) -> Optional[str]:
        """Get current tenant ID from context."""
        return tenant_id_var.get()


class XRaySegmentContext:
    """Context manager for X-Ray segment lifecycle."""
    
    def __init__(
        self,
        name: str,
        tracer: XRayTracer,
        tenant_id: str = None,
        session_id: str = None,
        agent_id: str = None,
        **annotations
    ):
        self.name = name
        self.tracer = tracer
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.agent_id = agent_id
        self.annotations = annotations
        self.context = None
    
    def __enter__(self) -> TraceContext:
        self.context = self.tracer.start_segment(
            self.name,
            tenant_id=self.tenant_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            **self.annotations
        )
        return self.context
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.tracer.record_exception(exc_val)
        self.tracer.end_segment()


class XRaySubsegmentContext:
    """Context manager for X-Ray subsegment lifecycle."""
    
    def __init__(
        self,
        name: str,
        tracer: XRayTracer,
        subsegment_type: str = "subsegment",
        **annotations
    ):
        self.name = name
        self.tracer = tracer
        self.subsegment_type = subsegment_type
        self.annotations = annotations
        self.subsegment = None
    
    def __enter__(self):
        self.subsegment = self.tracer.start_subsegment(
            self.name,
            subsegment_type=self.subsegment_type,
            **self.annotations
        )
        return self.subsegment
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.tracer.record_exception(exc_val)
        self.tracer.end_subsegment()


def trace_segment(
    name: str,
    tenant_id: str = None,
    session_id: str = None,
    agent_id: str = None,
    **annotations
):
    """Decorator for automatic X-Ray segment tracing."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_xray_tracer()
            
            with XRaySegmentContext(
                name,
                tracer,
                tenant_id=tenant_id,
                session_id=session_id,
                agent_id=agent_id,
                **annotations
            ):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def trace_subsegment(
    name: str,
    subsegment_type: str = "subsegment",
    **annotations
):
    """Decorator for automatic X-Ray subsegment tracing."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_xray_tracer()
            
            with XRaySubsegmentContext(
                name,
                tracer,
                subsegment_type=subsegment_type,
                **annotations
            ):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global X-Ray tracer instance
_xray_tracer: Optional[XRayTracer] = None


def get_xray_tracer() -> XRayTracer:
    """Get or create the global X-Ray tracer."""
    global _xray_tracer
    if _xray_tracer is None:
        _xray_tracer = XRayTracer()
    return _xray_tracer