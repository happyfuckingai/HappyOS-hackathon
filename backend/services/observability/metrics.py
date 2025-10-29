"""
Prometheus metrics collection for comprehensive system monitoring.
"""

import time
from typing import Dict, Optional, Any
from contextlib import contextmanager
from functools import wraps

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Info, CollectorRegistry, 
        generate_latest, CONTENT_TYPE_LATEST, start_http_server
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock classes for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def time(self): return contextmanager(lambda: (yield))()
        def labels(self, *args, **kwargs): return self
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Info:
        def __init__(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
    
    class CollectorRegistry:
        def __init__(self): pass
    
    def generate_latest(registry): return b""
    CONTENT_TYPE_LATEST = "text/plain"
    def start_http_server(port, registry=None): pass

try:
    from backend.modules.config.settings import settings
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.modules.config.settings import settings
from .logger import get_logger


class MetricsCollector:
    """Centralized metrics collection for system monitoring."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.registry = CollectorRegistry()
        self._setup_metrics()
        
        if PROMETHEUS_AVAILABLE:
            self.logger.info("Prometheus metrics initialized")
        else:
            self.logger.warning("Prometheus client not available - metrics will be no-op")
    
    def _setup_metrics(self):
        """Initialize all Prometheus metrics."""
        
        # HTTP Request metrics
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry,
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        # AI/LLM metrics
        self.ai_requests_total = Counter(
            'ai_requests_total',
            'Total AI/LLM requests',
            ['provider', 'model', 'operation', 'status'],
            registry=self.registry
        )
        
        self.ai_request_duration = Histogram(
            'ai_request_duration_seconds',
            'AI/LLM request duration in seconds',
            ['provider', 'model', 'operation'],
            registry=self.registry,
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        self.ai_tokens_used = Counter(
            'ai_tokens_used_total',
            'Total AI tokens consumed',
            ['provider', 'model', 'operation'],
            registry=self.registry
        )
        
        self.ai_cost_total = Counter(
            'ai_cost_total',
            'Total AI cost in USD',
            ['provider', 'model'],
            registry=self.registry
        )
        
        # Database metrics
        self.db_queries_total = Counter(
            'db_queries_total',
            'Total database queries',
            ['query_type', 'table', 'status'],
            registry=self.registry
        )
        
        self.db_query_duration = Histogram(
            'db_query_duration_seconds',
            'Database query duration in seconds',
            ['query_type', 'table'],
            registry=self.registry,
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        )
        
        self.db_connections_active = Gauge(
            'db_connections_active',
            'Active database connections',
            registry=self.registry
        )
        
        # Worker/Agent metrics
        self.worker_tasks_total = Counter(
            'worker_tasks_total',
            'Total worker tasks processed',
            ['task_type', 'status'],
            registry=self.registry
        )
        
        self.worker_task_duration = Histogram(
            'worker_task_duration_seconds',
            'Worker task duration in seconds',
            ['task_type'],
            registry=self.registry,
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0]
        )
        
        self.active_agents = Gauge(
            'active_agents',
            'Number of active agent processes',
            ['agent_type'],
            registry=self.registry
        )
        
        # System resource metrics
        self.memory_usage_bytes = Gauge(
            'memory_usage_bytes',
            'Memory usage in bytes',
            ['component'],
            registry=self.registry
        )
        
        self.cpu_usage_percent = Gauge(
            'cpu_usage_percent',
            'CPU usage percentage',
            ['component'],
            registry=self.registry
        )
        
        # Meeting/Session metrics
        self.active_meetings = Gauge(
            'active_meetings',
            'Number of active meetings',
            registry=self.registry
        )
        
        self.meeting_duration = Histogram(
            'meeting_duration_seconds',
            'Meeting duration in seconds',
            registry=self.registry,
            buckets=[60, 300, 900, 1800, 3600, 7200, 14400]  # 1min to 4hrs
        )
        
        # Error metrics
        self.errors_total = Counter(
            'errors_total',
            'Total errors by type and component',
            ['error_type', 'component'],
            registry=self.registry
        )
        
        # System info
        self.system_info = Info(
            'system_info',
            'System information',
            registry=self.registry
        )
        
        # Set system info
        self.system_info.info({
            'version': '2.0.0',
            'environment': settings.ENVIRONMENT,
            'python_version': '3.11',
            'prometheus_available': str(PROMETHEUS_AVAILABLE)
        })
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, 
                           duration_seconds: float):
        """Record HTTP request metrics."""
        self.http_requests_total.labels(
            method=method, 
            endpoint=endpoint, 
            status_code=str(status_code)
        ).inc()
        
        self.http_request_duration.labels(
            method=method, 
            endpoint=endpoint
        ).observe(duration_seconds)
    
    def record_ai_request(self, provider: str, model: str, operation: str, 
                         status: str, duration_seconds: float, 
                         tokens_used: int = 0, cost: float = 0.0):
        """Record AI/LLM request metrics."""
        self.ai_requests_total.labels(
            provider=provider,
            model=model,
            operation=operation,
            status=status
        ).inc()
        
        self.ai_request_duration.labels(
            provider=provider,
            model=model,
            operation=operation
        ).observe(duration_seconds)
        
        if tokens_used > 0:
            self.ai_tokens_used.labels(
                provider=provider,
                model=model,
                operation=operation
            ).inc(tokens_used)
        
        if cost > 0:
            self.ai_cost_total.labels(
                provider=provider,
                model=model
            ).inc(cost)
    
    def record_db_query(self, query_type: str, table: str, status: str, 
                       duration_seconds: float):
        """Record database query metrics."""
        self.db_queries_total.labels(
            query_type=query_type,
            table=table,
            status=status
        ).inc()
        
        self.db_query_duration.labels(
            query_type=query_type,
            table=table
        ).observe(duration_seconds)
    
    def record_worker_task(self, task_type: str, status: str, 
                          duration_seconds: float):
        """Record worker task metrics."""
        self.worker_tasks_total.labels(
            task_type=task_type,
            status=status
        ).inc()
        
        self.worker_task_duration.labels(
            task_type=task_type
        ).observe(duration_seconds)
    
    def set_active_agents(self, agent_type: str, count: int):
        """Set number of active agents."""
        self.active_agents.labels(agent_type=agent_type).set(count)
    
    def set_active_meetings(self, count: int):
        """Set number of active meetings."""
        self.active_meetings.set(count)
    
    def record_meeting_duration(self, duration_seconds: float):
        """Record meeting duration."""
        self.meeting_duration.observe(duration_seconds)
    
    def record_error(self, error_type: str, component: str):
        """Record error occurrence."""
        self.errors_total.labels(
            error_type=error_type,
            component=component
        ).inc()
    
    def set_memory_usage(self, component: str, bytes_used: int):
        """Set memory usage for component."""
        self.memory_usage_bytes.labels(component=component).set(bytes_used)
    
    def set_cpu_usage(self, component: str, percent: float):
        """Set CPU usage for component."""
        self.cpu_usage_percent.labels(component=component).set(percent)
    
    def set_db_connections(self, count: int):
        """Set active database connections."""
        self.db_connections_active.set(count)
    
    @contextmanager
    def time_operation(self, operation_type: str, **labels):
        """Context manager to time operations."""
        start_time = time.time()
        try:
            yield
            duration = time.time() - start_time
            # Record success metrics based on operation type
            if operation_type == "http":
                self.record_http_request(duration_seconds=duration, **labels)
            elif operation_type == "ai":
                self.record_ai_request(duration_seconds=duration, status="success", **labels)
            elif operation_type == "db":
                self.record_db_query(duration_seconds=duration, status="success", **labels)
            elif operation_type == "worker":
                self.record_worker_task(duration_seconds=duration, status="success", **labels)
        except Exception as e:
            duration = time.time() - start_time
            # Record error metrics
            if operation_type == "ai":
                self.record_ai_request(duration_seconds=duration, status="error", **labels)
            elif operation_type == "db":
                self.record_db_query(duration_seconds=duration, status="error", **labels)
            elif operation_type == "worker":
                self.record_worker_task(duration_seconds=duration, status="error", **labels)
            
            self.record_error(error_type=type(e).__name__, component=operation_type)
            raise
    
    def get_metrics(self) -> bytes:
        """Get current metrics in Prometheus format."""
        if PROMETHEUS_AVAILABLE:
            return generate_latest(self.registry)
        return b"# Prometheus client not available\n"
    
    def start_metrics_server(self, port: int = 8000):
        """Start Prometheus metrics HTTP server."""
        if PROMETHEUS_AVAILABLE:
            try:
                start_http_server(port, registry=self.registry)
                self.logger.info(f"Metrics server started on port {port}")
            except Exception as e:
                self.logger.error(f"Failed to start metrics server: {e}")
        else:
            self.logger.warning("Cannot start metrics server - Prometheus client not available")


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def metrics_middleware(operation_type: str = "http"):
    """Decorator to automatically collect metrics for functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics_collector()
            
            # Extract relevant labels based on function and args
            labels = {}
            if operation_type == "http" and len(args) >= 1:
                # Assume first arg is request object for HTTP operations
                request = args[0]
                if hasattr(request, 'method') and hasattr(request, 'url'):
                    labels.update({
                        'method': request.method,
                        'endpoint': str(request.url.path)
                    })
            
            with metrics.time_operation(operation_type, **labels):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator