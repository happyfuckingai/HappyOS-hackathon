"""
Telemetry and Metrics Collection for HappyOS SDK

Provides telemetry hooks and metrics collection for agent modules
to monitor performance and health.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and aggregates metrics for agent modules."""
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize metrics collector.
        
        Args:
            max_history: Maximum number of metric entries to keep in history
        """
        self.max_history = max_history
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        key = self._make_key(name, tags)
        self.counters[key] += value
        
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric."""
        key = self._make_key(name, tags)
        self.gauges[key] = value
        
    def record_timing(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """Record a timing metric."""
        key = self._make_key(name, tags)
        self.metrics[key].append({
            "value": duration,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def record_value(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a general value metric."""
        key = self._make_key(name, tags)
        self.metrics[key].append({
            "value": value,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def _make_key(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Create a metric key from name and tags."""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all collected metrics."""
        summary = {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {}
        }
        
        # Calculate histogram statistics
        for key, values in self.metrics.items():
            if values:
                numeric_values = [v["value"] for v in values]
                summary["histograms"][key] = {
                    "count": len(numeric_values),
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "avg": sum(numeric_values) / len(numeric_values),
                    "recent_values": list(values)[-10:]  # Last 10 values
                }
        
        return summary


class TelemetryHooks:
    """Provides telemetry hooks for monitoring agent operations."""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize telemetry hooks.
        
        Args:
            metrics_collector: Optional metrics collector instance
        """
        self.metrics = metrics_collector or MetricsCollector()
        self.active_operations: Dict[str, float] = {}
        
    def start_operation(self, operation_name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """
        Start tracking an operation.
        
        Args:
            operation_name: Name of the operation
            tags: Optional tags for the operation
            
        Returns:
            Operation ID for tracking
        """
        operation_id = f"{operation_name}_{int(time.time() * 1000000)}"
        self.active_operations[operation_id] = time.time()
        
        # Record operation start
        self.metrics.increment_counter("operations_started", tags=tags)
        
        return operation_id
        
    def end_operation(self, operation_id: str, success: bool = True, 
                     tags: Optional[Dict[str, str]] = None):
        """
        End tracking an operation.
        
        Args:
            operation_id: Operation ID from start_operation
            success: Whether the operation was successful
            tags: Optional tags for the operation
        """
        if operation_id not in self.active_operations:
            logger.warning(f"Unknown operation ID: {operation_id}")
            return
            
        start_time = self.active_operations.pop(operation_id)
        duration = time.time() - start_time
        
        # Extract operation name from ID
        operation_name = operation_id.rsplit("_", 1)[0]
        
        # Record metrics
        self.metrics.record_timing(f"{operation_name}_duration", duration, tags)
        
        if success:
            self.metrics.increment_counter("operations_succeeded", tags=tags)
        else:
            self.metrics.increment_counter("operations_failed", tags=tags)
            
    def record_a2a_message(self, message_type: str, direction: str, success: bool = True):
        """
        Record A2A message metrics.
        
        Args:
            message_type: Type of A2A message
            direction: "sent" or "received"
            success: Whether the message was successful
        """
        tags = {"message_type": message_type, "direction": direction}
        
        self.metrics.increment_counter("a2a_messages", tags=tags)
        
        if success:
            self.metrics.increment_counter("a2a_messages_success", tags=tags)
        else:
            self.metrics.increment_counter("a2a_messages_failed", tags=tags)
            
    def record_service_call(self, service_name: str, operation: str, 
                           duration: float, success: bool = True):
        """
        Record service call metrics.
        
        Args:
            service_name: Name of the service
            operation: Operation performed
            duration: Duration of the call
            success: Whether the call was successful
        """
        tags = {"service": service_name, "operation": operation}
        
        self.metrics.record_timing("service_call_duration", duration, tags)
        self.metrics.increment_counter("service_calls", tags=tags)
        
        if success:
            self.metrics.increment_counter("service_calls_success", tags=tags)
        else:
            self.metrics.increment_counter("service_calls_failed", tags=tags)
            
    def record_circuit_breaker_event(self, circuit_name: str, event_type: str):
        """
        Record circuit breaker events.
        
        Args:
            circuit_name: Name of the circuit breaker
            event_type: Type of event (open, close, half_open, failure, success)
        """
        tags = {"circuit": circuit_name, "event": event_type}
        self.metrics.increment_counter("circuit_breaker_events", tags=tags)
        
    def get_telemetry_summary(self) -> Dict[str, Any]:
        """Get a summary of all telemetry data."""
        return {
            "metrics": self.metrics.get_metrics_summary(),
            "active_operations": len(self.active_operations),
            "timestamp": datetime.utcnow().isoformat()
        }


# Global telemetry instance
_global_telemetry: Optional[TelemetryHooks] = None


def get_telemetry() -> TelemetryHooks:
    """Get or create global telemetry instance."""
    global _global_telemetry
    if _global_telemetry is None:
        _global_telemetry = TelemetryHooks()
    return _global_telemetry


def set_telemetry(telemetry: TelemetryHooks):
    """Set global telemetry instance."""
    global _global_telemetry
    _global_telemetry = telemetry