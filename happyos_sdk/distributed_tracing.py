"""
Distributed Tracing and Correlation for HappyOS SDK

Provides standardized distributed tracing with trace_id and conversation_id
propagation across all MCP communications and A2A protocol interactions.
"""

import uuid
import time
import asyncio
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from contextvars import ContextVar
from functools import wraps

from .logging import get_logger, LogContext

# Try to import backend X-Ray integration
try:
    from backend.modules.observability.xray_tracing import get_xray_tracer, XRaySegmentContext, XRaySubsegmentContext
    XRAY_AVAILABLE = True
except ImportError:
    XRAY_AVAILABLE = False

logger = get_logger(__name__)

# Context variables for trace propagation
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
conversation_id_var: ContextVar[Optional[str]] = ContextVar('conversation_id', default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar('span_id', default=None)
parent_span_id_var: ContextVar[Optional[str]] = ContextVar('parent_span_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)
agent_type_var: ContextVar[Optional[str]] = ContextVar('agent_type', default=None)


@dataclass
class TraceContext:
    """Unified trace context for HappyOS operations."""
    
    trace_id: str
    conversation_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    
    # Agent context
    agent_type: Optional[str] = None
    agent_id: Optional[str] = None
    tenant_id: Optional[str] = None
    
    # Operation context
    operation_name: str = ""
    operation_type: str = ""  # "mcp_call", "mcp_callback", "a2a_call", "workflow"
    
    # Timing
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    
    # Status
    status: str = "active"  # "active", "success", "error"
    error_message: Optional[str] = None
    
    # Additional context
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate duration in milliseconds."""
        if not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "conversation_id": self.conversation_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "agent_type": self.agent_type,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "operation_name": self.operation_name,
            "operation_type": self.operation_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_message": self.error_message,
            "tags": self.tags,
            "logs": self.logs
        }
    
    def add_log(self, level: str, message: str, **kwargs):
        """Add a log entry to the trace."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            **kwargs
        }
        self.logs.append(log_entry)
    
    def add_tag(self, key: str, value: str):
        """Add a tag to the trace."""
        self.tags[key] = value
    
    def finish(self, status: str = "success", error_message: str = None):
        """Finish the trace span."""
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        if error_message:
            self.error_message = error_message


@dataclass
class MCPTraceHeaders:
    """MCP headers with tracing information."""
    
    trace_id: str
    conversation_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    tenant_id: Optional[str] = None
    agent_type: Optional[str] = None
    
    @classmethod
    def from_dict(cls, headers: Dict[str, str]) -> 'MCPTraceHeaders':
        """Create from dictionary of headers."""
        return cls(
            trace_id=headers.get('trace_id', str(uuid.uuid4())),
            conversation_id=headers.get('conversation_id', str(uuid.uuid4())),
            span_id=headers.get('span_id', str(uuid.uuid4())),
            parent_span_id=headers.get('parent_span_id'),
            tenant_id=headers.get('tenant_id'),
            agent_type=headers.get('agent_type')
        )
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for MCP headers."""
        headers = {
            'trace_id': self.trace_id,
            'conversation_id': self.conversation_id,
            'span_id': self.span_id
        }
        
        if self.parent_span_id:
            headers['parent_span_id'] = self.parent_span_id
        if self.tenant_id:
            headers['tenant_id'] = self.tenant_id
        if self.agent_type:
            headers['agent_type'] = self.agent_type
        
        return headers


class DistributedTracer:
    """Distributed tracing system for HappyOS agents."""
    
    def __init__(self, agent_type: str = None, agent_id: str = None):
        """
        Initialize distributed tracer.
        
        Args:
            agent_type: Type of agent (agent_svea, felicias_finance, meetmind)
            agent_id: Unique agent identifier
        """
        self.agent_type = agent_type
        self.agent_id = agent_id
        
        # Active traces
        self.active_traces: Dict[str, TraceContext] = {}
        self.completed_traces: List[TraceContext] = []
        
        # X-Ray integration
        self.xray_tracer = None
        if XRAY_AVAILABLE:
            try:
                self.xray_tracer = get_xray_tracer()
                logger.info("X-Ray distributed tracing integration enabled")
            except Exception as e:
                logger.warning(f"X-Ray tracing not available: {e}")
        
        # Trace processors
        self.trace_processors: List[Callable] = []
        
        logger.info(f"Distributed tracer initialized for {agent_type}:{agent_id}")
    
    def start_trace(self, operation_name: str, operation_type: str = "operation",
                   trace_id: str = None, conversation_id: str = None,
                   parent_span_id: str = None, tenant_id: str = None,
                   **tags) -> TraceContext:
        """Start a new trace or continue an existing one."""
        
        # Generate IDs if not provided
        trace_id = trace_id or str(uuid.uuid4())
        conversation_id = conversation_id or str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        # Create trace context
        trace_context = TraceContext(
            trace_id=trace_id,
            conversation_id=conversation_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            agent_type=self.agent_type,
            agent_id=self.agent_id,
            tenant_id=tenant_id,
            operation_name=operation_name,
            operation_type=operation_type,
            tags=tags
        )
        
        # Store active trace
        self.active_traces[span_id] = trace_context
        
        # Set context variables
        trace_id_var.set(trace_id)
        conversation_id_var.set(conversation_id)
        span_id_var.set(span_id)
        parent_span_id_var.set(parent_span_id)
        if tenant_id:
            tenant_id_var.set(tenant_id)
        if self.agent_type:
            agent_type_var.set(self.agent_type)
        
        # Start X-Ray segment if available
        if self.xray_tracer:
            try:
                self.xray_tracer.start_segment(
                    operation_name,
                    tenant_id=tenant_id,
                    agent_id=self.agent_id,
                    **tags
                )
                self.xray_tracer.add_annotation("trace_id", trace_id)
                self.xray_tracer.add_annotation("conversation_id", conversation_id)
                self.xray_tracer.add_annotation("span_id", span_id)
            except Exception as e:
                logger.warning(f"Failed to start X-Ray segment: {e}")
        
        logger.debug(
            f"Started trace: {operation_name}",
            extra={
                "trace_id": trace_id,
                "conversation_id": conversation_id,
                "span_id": span_id,
                "operation_type": operation_type
            }
        )
        
        return trace_context
    
    def finish_trace(self, span_id: str, status: str = "success", 
                    error_message: str = None, **tags):
        """Finish a trace span."""
        
        if span_id not in self.active_traces:
            logger.warning(f"Trace not found: {span_id}")
            return
        
        trace_context = self.active_traces.pop(span_id)
        
        # Add final tags
        for key, value in tags.items():
            trace_context.add_tag(key, str(value))
        
        # Finish the trace
        trace_context.finish(status, error_message)
        
        # Store completed trace
        self.completed_traces.append(trace_context)
        
        # End X-Ray segment if available
        if self.xray_tracer:
            try:
                if error_message:
                    self.xray_tracer.record_exception(Exception(error_message))
                self.xray_tracer.end_segment()
            except Exception as e:
                logger.warning(f"Failed to end X-Ray segment: {e}")
        
        # Process trace
        asyncio.create_task(self._process_trace(trace_context))
        
        logger.debug(
            f"Finished trace: {trace_context.operation_name}",
            extra={
                "trace_id": trace_context.trace_id,
                "span_id": span_id,
                "status": status,
                "duration_ms": trace_context.duration_ms
            }
        )
    
    def get_current_trace_context(self) -> Optional[TraceContext]:
        """Get current trace context from context variables."""
        trace_id = trace_id_var.get()
        conversation_id = conversation_id_var.get()
        span_id = span_id_var.get()
        
        if not trace_id or not span_id:
            return None
        
        # Try to find in active traces
        if span_id in self.active_traces:
            return self.active_traces[span_id]
        
        # Create minimal context from context variables
        return TraceContext(
            trace_id=trace_id,
            conversation_id=conversation_id or str(uuid.uuid4()),
            span_id=span_id,
            parent_span_id=parent_span_id_var.get(),
            agent_type=agent_type_var.get(),
            tenant_id=tenant_id_var.get()
        )
    
    def create_child_span(self, operation_name: str, operation_type: str = "operation",
                         **tags) -> Optional[TraceContext]:
        """Create a child span from the current trace context."""
        
        current_context = self.get_current_trace_context()
        if not current_context:
            logger.warning("No current trace context for child span")
            return None
        
        return self.start_trace(
            operation_name=operation_name,
            operation_type=operation_type,
            trace_id=current_context.trace_id,
            conversation_id=current_context.conversation_id,
            parent_span_id=current_context.span_id,
            tenant_id=current_context.tenant_id,
            **tags
        )
    
    def inject_headers(self, headers: Dict[str, str] = None) -> Dict[str, str]:
        """Inject tracing headers into MCP call headers."""
        headers = headers or {}
        
        current_context = self.get_current_trace_context()
        if not current_context:
            # Create new trace context
            trace_headers = MCPTraceHeaders(
                trace_id=str(uuid.uuid4()),
                conversation_id=str(uuid.uuid4()),
                span_id=str(uuid.uuid4()),
                tenant_id=tenant_id_var.get(),
                agent_type=self.agent_type
            )
        else:
            # Use current context
            trace_headers = MCPTraceHeaders(
                trace_id=current_context.trace_id,
                conversation_id=current_context.conversation_id,
                span_id=str(uuid.uuid4()),  # New span for outgoing call
                parent_span_id=current_context.span_id,
                tenant_id=current_context.tenant_id,
                agent_type=self.agent_type
            )
        
        # Merge with existing headers
        headers.update(trace_headers.to_dict())
        return headers
    
    def extract_headers(self, headers: Dict[str, str]) -> MCPTraceHeaders:
        """Extract tracing headers from MCP call."""
        return MCPTraceHeaders.from_dict(headers)
    
    def trace_mcp_call(self, target_agent: str, tool_name: str, 
                      headers: Dict[str, str] = None) -> TraceContext:
        """Start tracing an MCP call."""
        
        # Extract or create trace headers
        if headers:
            trace_headers = self.extract_headers(headers)
            trace_id = trace_headers.trace_id
            conversation_id = trace_headers.conversation_id
            parent_span_id = trace_headers.parent_span_id
            tenant_id = trace_headers.tenant_id
        else:
            current_context = self.get_current_trace_context()
            if current_context:
                trace_id = current_context.trace_id
                conversation_id = current_context.conversation_id
                parent_span_id = current_context.span_id
                tenant_id = current_context.tenant_id
            else:
                trace_id = str(uuid.uuid4())
                conversation_id = str(uuid.uuid4())
                parent_span_id = None
                tenant_id = None
        
        return self.start_trace(
            operation_name=f"mcp_call_{tool_name}",
            operation_type="mcp_call",
            trace_id=trace_id,
            conversation_id=conversation_id,
            parent_span_id=parent_span_id,
            tenant_id=tenant_id,
            target_agent=target_agent,
            tool_name=tool_name
        )
    
    def trace_mcp_callback(self, source_agent: str, result_type: str,
                          headers: Dict[str, str] = None) -> TraceContext:
        """Start tracing an MCP callback."""
        
        # Extract trace headers
        if headers:
            trace_headers = self.extract_headers(headers)
            trace_id = trace_headers.trace_id
            conversation_id = trace_headers.conversation_id
            parent_span_id = trace_headers.parent_span_id
            tenant_id = trace_headers.tenant_id
        else:
            trace_id = str(uuid.uuid4())
            conversation_id = str(uuid.uuid4())
            parent_span_id = None
            tenant_id = None
        
        return self.start_trace(
            operation_name=f"mcp_callback_{result_type}",
            operation_type="mcp_callback",
            trace_id=trace_id,
            conversation_id=conversation_id,
            parent_span_id=parent_span_id,
            tenant_id=tenant_id,
            source_agent=source_agent,
            result_type=result_type
        )
    
    def trace_workflow(self, workflow_type: str, participating_agents: List[str],
                      conversation_id: str = None, tenant_id: str = None) -> TraceContext:
        """Start tracing a cross-agent workflow."""
        
        return self.start_trace(
            operation_name=f"workflow_{workflow_type}",
            operation_type="workflow",
            conversation_id=conversation_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
            workflow_type=workflow_type,
            participating_agents=",".join(participating_agents)
        )
    
    def add_trace_processor(self, processor: Callable[[TraceContext], None]):
        """Add a trace processor function."""
        self.trace_processors.append(processor)
    
    async def _process_trace(self, trace_context: TraceContext):
        """Process a completed trace."""
        try:
            # Run all trace processors
            for processor in self.trace_processors:
                try:
                    if asyncio.iscoroutinefunction(processor):
                        await processor(trace_context)
                    else:
                        processor(trace_context)
                except Exception as e:
                    logger.error(f"Trace processor failed: {e}")
            
            # Log trace completion
            logger.info(
                f"Trace completed: {trace_context.operation_name}",
                extra={
                    "trace_id": trace_context.trace_id,
                    "conversation_id": trace_context.conversation_id,
                    "duration_ms": trace_context.duration_ms,
                    "status": trace_context.status
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to process trace: {e}")
    
    def get_trace_summary(self) -> Dict[str, Any]:
        """Get summary of tracing activity."""
        return {
            "active_traces": len(self.active_traces),
            "completed_traces": len(self.completed_traces),
            "agent_type": self.agent_type,
            "agent_id": self.agent_id,
            "xray_enabled": self.xray_tracer is not None,
            "processors": len(self.trace_processors)
        }


class TraceContextManager:
    """Context manager for automatic trace lifecycle management."""
    
    def __init__(self, tracer: DistributedTracer, operation_name: str,
                 operation_type: str = "operation", **kwargs):
        self.tracer = tracer
        self.operation_name = operation_name
        self.operation_type = operation_type
        self.kwargs = kwargs
        self.trace_context = None
    
    def __enter__(self) -> TraceContext:
        self.trace_context = self.tracer.start_trace(
            self.operation_name, self.operation_type, **self.kwargs
        )
        return self.trace_context
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.trace_context:
            status = "error" if exc_type else "success"
            error_message = str(exc_val) if exc_val else None
            self.tracer.finish_trace(
                self.trace_context.span_id, status, error_message
            )


# Decorators for automatic tracing
def trace_operation(operation_name: str = None, operation_type: str = "operation"):
    """Decorator for automatic operation tracing."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_distributed_tracer()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with TraceContextManager(tracer, op_name, operation_type):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_distributed_tracer()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with TraceContextManager(tracer, op_name, operation_type):
                return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def trace_mcp_call(target_agent: str, tool_name: str):
    """Decorator for automatic MCP call tracing."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_distributed_tracer()
            trace_context = tracer.trace_mcp_call(target_agent, tool_name)
            
            try:
                result = await func(*args, **kwargs)
                tracer.finish_trace(trace_context.span_id, "success")
                return result
            except Exception as e:
                tracer.finish_trace(trace_context.span_id, "error", str(e))
                raise
        
        return wrapper
    return decorator


# Global tracer instances
_distributed_tracers: Dict[str, DistributedTracer] = {}


def get_distributed_tracer(agent_type: str = None, agent_id: str = None) -> DistributedTracer:
    """Get or create distributed tracer for an agent."""
    key = f"{agent_type}:{agent_id}" if agent_type and agent_id else "default"
    
    if key not in _distributed_tracers:
        _distributed_tracers[key] = DistributedTracer(agent_type, agent_id)
    
    return _distributed_tracers[key]


# Utility functions for trace context
def get_current_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    return trace_id_var.get()


def get_current_conversation_id() -> Optional[str]:
    """Get current conversation ID from context."""
    return conversation_id_var.get()


def get_current_span_id() -> Optional[str]:
    """Get current span ID from context."""
    return span_id_var.get()


def create_log_context_from_trace() -> LogContext:
    """Create log context from current trace context."""
    from .logging import LogContext
    
    return LogContext(
        trace_id=trace_id_var.get(),
        conversation_id=conversation_id_var.get(),
        tenant_id=tenant_id_var.get(),
        agent_type=agent_type_var.get()
    )