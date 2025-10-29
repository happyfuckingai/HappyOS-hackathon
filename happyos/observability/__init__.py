"""
HappyOS Observability & Monitoring

Enterprise-grade observability features including structured logging,
metrics collection, distributed tracing, and real-time monitoring.
"""

try:
    from .logging import get_logger, StructuredLogger, LogLevel
except ImportError:
    from .logging import get_logger
    # Fallback implementations
    class StructuredLogger:
        pass
    class LogLevel:
        pass

try:
    from .metrics import MetricsCollector, Counter, Gauge, Histogram
except ImportError:
    from .metrics import MetricsCollector
    # Fallback implementations
    class Counter:
        pass
    class Gauge:
        pass
    class Histogram:
        pass

try:
    from .tracing import TracingManager, Span, TraceContext
except ImportError:
    from .tracing import TracingManager, Span
    # Fallback implementations
    class TraceContext:
        pass

__all__ = [
    "get_logger",
    "StructuredLogger",
    "LogLevel",
    "MetricsCollector",
    "Counter",
    "Gauge", 
    "Histogram",
    "TracingManager",
    "Span",
    "TraceContext",
]