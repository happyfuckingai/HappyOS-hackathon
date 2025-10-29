"""
HappyOS Metrics Collection

Enterprise-grade metrics collection with support for counters, gauges,
histograms, and integration with monitoring platforms.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional, Any, Union
from enum import Enum


class MetricType(Enum):
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """Individual metric value."""
    value: Union[int, float]
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Metric summary statistics."""
    name: str
    type: MetricType
    current_value: Union[int, float]
    total_samples: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None
    percentiles: Dict[str, float] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)


class Counter:
    """
    Counter metric - monotonically increasing value.
    """
    
    def __init__(self, name: str, description: str = "", labels: Dict[str, str] = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value = 0
        self._lock = Lock()
        self._history: deque = deque(maxlen=1000)  # Keep last 1000 values
    
    def increment(self, amount: Union[int, float] = 1, labels: Dict[str, str] = None) -> None:
        """Increment counter by amount."""
        with self._lock:
            self._value += amount
            metric_labels = {**self.labels, **(labels or {})}
            self._history.append(MetricValue(
                value=self._value,
                timestamp=datetime.now(),
                labels=metric_labels
            ))
    
    def get_value(self) -> Union[int, float]:
        """Get current counter value."""
        return self._value
    
    def reset(self) -> None:
        """Reset counter to zero."""
        with self._lock:
            self._value = 0
            self._history.clear()
    
    def get_summary(self) -> MetricSummary:
        """Get counter summary."""
        return MetricSummary(
            name=self.name,
            type=MetricType.COUNTER,
            current_value=self._value,
            total_samples=len(self._history),
            labels=self.labels
        )


class Gauge:
    """
    Gauge metric - value that can go up and down.
    """
    
    def __init__(self, name: str, description: str = "", labels: Dict[str, str] = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value = 0
        self._lock = Lock()
        self._history: deque = deque(maxlen=1000)
    
    def set(self, value: Union[int, float], labels: Dict[str, str] = None) -> None:
        """Set gauge value."""
        with self._lock:
            self._value = value
            metric_labels = {**self.labels, **(labels or {})}
            self._history.append(MetricValue(
                value=self._value,
                timestamp=datetime.now(),
                labels=metric_labels
            ))
    
    def increment(self, amount: Union[int, float] = 1, labels: Dict[str, str] = None) -> None:
        """Increment gauge by amount."""
        with self._lock:
            self._value += amount
            metric_labels = {**self.labels, **(labels or {})}
            self._history.append(MetricValue(
                value=self._value,
                timestamp=datetime.now(),
                labels=metric_labels
            ))
    
    def decrement(self, amount: Union[int, float] = 1, labels: Dict[str, str] = None) -> None:
        """Decrement gauge by amount."""
        self.increment(-amount, labels)
    
    def get_value(self) -> Union[int, float]:
        """Get current gauge value."""
        return self._value
    
    def get_summary(self) -> MetricSummary:
        """Get gauge summary."""
        values = [mv.value for mv in self._history]
        
        summary = MetricSummary(
            name=self.name,
            type=MetricType.GAUGE,
            current_value=self._value,
            total_samples=len(values),
            labels=self.labels
        )
        
        if values:
            summary.min_value = min(values)
            summary.max_value = max(values)
            summary.avg_value = sum(values) / len(values)
        
        return summary


class Histogram:
    """
    Histogram metric - tracks distribution of values.
    """
    
    def __init__(self, name: str, description: str = "", 
                 buckets: List[float] = None, labels: Dict[str, str] = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.buckets = buckets or [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')]
        
        self._bucket_counts = {bucket: 0 for bucket in self.buckets}
        self._sum = 0
        self._count = 0
        self._lock = Lock()
        self._values: deque = deque(maxlen=1000)
    
    def observe(self, value: Union[int, float], labels: Dict[str, str] = None) -> None:
        """Observe a value."""
        with self._lock:
            self._sum += value
            self._count += 1
            self._values.append(value)
            
            # Update bucket counts
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] += 1
    
    def get_summary(self) -> MetricSummary:
        """Get histogram summary."""
        values = list(self._values)
        
        summary = MetricSummary(
            name=self.name,
            type=MetricType.HISTOGRAM,
            current_value=self._sum / self._count if self._count > 0 else 0,
            total_samples=self._count,
            labels=self.labels
        )
        
        if values:
            sorted_values = sorted(values)
            summary.min_value = min(values)
            summary.max_value = max(values)
            summary.avg_value = sum(values) / len(values)
            
            # Calculate percentiles
            summary.percentiles = {
                "p50": self._percentile(sorted_values, 50),
                "p90": self._percentile(sorted_values, 90),
                "p95": self._percentile(sorted_values, 95),
                "p99": self._percentile(sorted_values, 99)
            }
        
        return summary
    
    def _percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0
        
        index = (percentile / 100.0) * (len(sorted_values) - 1)
        lower_index = int(index)
        upper_index = min(lower_index + 1, len(sorted_values) - 1)
        
        if lower_index == upper_index:
            return sorted_values[lower_index]
        
        # Linear interpolation
        weight = index - lower_index
        return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight


class Timer:
    """
    Timer metric - measures duration of operations.
    """
    
    def __init__(self, name: str, description: str = "", labels: Dict[str, str] = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._histogram = Histogram(f"{name}_duration_seconds", description, labels=labels)
        self._active_timers: Dict[str, float] = {}
        self._lock = Lock()
    
    def start(self, timer_id: str = "default") -> None:
        """Start timing an operation."""
        with self._lock:
            self._active_timers[timer_id] = time.time()
    
    def stop(self, timer_id: str = "default", labels: Dict[str, str] = None) -> float:
        """Stop timing and record duration."""
        with self._lock:
            if timer_id not in self._active_timers:
                raise ValueError(f"Timer {timer_id} not started")
            
            start_time = self._active_timers.pop(timer_id)
            duration = time.time() - start_time
            
            self._histogram.observe(duration, labels)
            return duration
    
    def time_context(self, timer_id: str = "default", labels: Dict[str, str] = None):
        """Context manager for timing operations."""
        return TimerContext(self, timer_id, labels)
    
    def get_summary(self) -> MetricSummary:
        """Get timer summary."""
        summary = self._histogram.get_summary()
        summary.type = MetricType.TIMER
        return summary


class TimerContext:
    """Context manager for timing operations."""
    
    def __init__(self, timer: Timer, timer_id: str, labels: Dict[str, str] = None):
        self.timer = timer
        self.timer_id = timer_id
        self.labels = labels
        self.duration = None
    
    def __enter__(self):
        self.timer.start(self.timer_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = self.timer.stop(self.timer_id, self.labels)


class MetricsCollector:
    """
    Central metrics collector for managing all metrics.
    """
    
    def __init__(self, namespace: str = "happyos"):
        self.namespace = namespace
        self._metrics: Dict[str, Union[Counter, Gauge, Histogram, Timer]] = {}
        self._lock = Lock()
    
    def counter(self, name: str, description: str = "", labels: Dict[str, str] = None) -> Counter:
        """Get or create a counter metric."""
        full_name = f"{self.namespace}_{name}"
        
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Counter(full_name, description, labels)
            
            metric = self._metrics[full_name]
            if not isinstance(metric, Counter):
                raise ValueError(f"Metric {full_name} is not a counter")
            
            return metric
    
    def gauge(self, name: str, description: str = "", labels: Dict[str, str] = None) -> Gauge:
        """Get or create a gauge metric."""
        full_name = f"{self.namespace}_{name}"
        
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Gauge(full_name, description, labels)
            
            metric = self._metrics[full_name]
            if not isinstance(metric, Gauge):
                raise ValueError(f"Metric {full_name} is not a gauge")
            
            return metric
    
    def histogram(self, name: str, description: str = "", 
                  buckets: List[float] = None, labels: Dict[str, str] = None) -> Histogram:
        """Get or create a histogram metric."""
        full_name = f"{self.namespace}_{name}"
        
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Histogram(full_name, description, buckets, labels)
            
            metric = self._metrics[full_name]
            if not isinstance(metric, Histogram):
                raise ValueError(f"Metric {full_name} is not a histogram")
            
            return metric
    
    def timer(self, name: str, description: str = "", labels: Dict[str, str] = None) -> Timer:
        """Get or create a timer metric."""
        full_name = f"{self.namespace}_{name}"
        
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Timer(full_name, description, labels)
            
            metric = self._metrics[full_name]
            if not isinstance(metric, Timer):
                raise ValueError(f"Metric {full_name} is not a timer")
            
            return metric
    
    def increment(self, name: str, amount: Union[int, float] = 1, labels: Dict[str, str] = None) -> None:
        """Increment a counter metric."""
        counter = self.counter(name)
        counter.increment(amount, labels)
    
    def set_gauge(self, name: str, value: Union[int, float], labels: Dict[str, str] = None) -> None:
        """Set a gauge metric value."""
        gauge = self.gauge(name)
        gauge.set(value, labels)
    
    def observe(self, name: str, value: Union[int, float], labels: Dict[str, str] = None) -> None:
        """Observe a value in a histogram."""
        histogram = self.histogram(name)
        histogram.observe(value, labels)
    
    def time_operation(self, name: str, labels: Dict[str, str] = None):
        """Time an operation using a timer."""
        timer = self.timer(name)
        return timer.time_context(labels=labels)
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        summaries = {}
        
        with self._lock:
            for name, metric in self._metrics.items():
                try:
                    summaries[name] = metric.get_summary().__dict__
                except Exception as e:
                    summaries[name] = {"error": str(e)}
        
        return {
            "namespace": self.namespace,
            "total_metrics": len(self._metrics),
            "metrics": summaries,
            "timestamp": datetime.now().isoformat()
        }
    
    def reset_all(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for metric in self._metrics.values():
                if hasattr(metric, 'reset'):
                    metric.reset()


# Global metrics collector
_default_collector = MetricsCollector()


def get_metrics_collector(namespace: str = None) -> MetricsCollector:
    """Get the default metrics collector or create a new one."""
    if namespace is None:
        return _default_collector
    else:
        return MetricsCollector(namespace)