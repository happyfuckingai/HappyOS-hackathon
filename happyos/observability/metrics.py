"""
Metrics collection for HappyOS SDK.

Stub implementation for testing purposes.
"""

from typing import Dict, Any


class MetricsCollector:
    """Metrics collector."""
    
    def __init__(self, name: str):
        self.name = name
        self.metrics = {}
    
    def increment(self, metric_name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = 0
        self.metrics[metric_name] += value
    
    def gauge(self, metric_name: str, value: float) -> None:
        """Set a gauge metric."""
        self.metrics[metric_name] = value
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return self.metrics.copy()