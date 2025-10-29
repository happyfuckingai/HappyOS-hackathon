"""
HappyOS Observability Framework

Provides comprehensive observability including logging, metrics, tracing,
and health monitoring for enterprise deployments.
"""

from .logging import (
    LogContext, UnifiedLogger, setup_logging, get_logger, create_log_context
)
from .metrics import TelemetryHooks, MetricsCollector
from .tracing import (
    ObservabilityContext, UnifiedObservabilityManager, get_observability_manager,
    with_mcp_observability, with_a2a_observability
)

__all__ = [
    # Logging
    "LogContext",
    "UnifiedLogger", 
    "setup_logging",
    "get_logger",
    "create_log_context",
    
    # Metrics & Telemetry
    "TelemetryHooks",
    "MetricsCollector",
    
    # Distributed Tracing
    "ObservabilityContext",
    "UnifiedObservabilityManager",
    "get_observability_manager", 
    "with_mcp_observability",
    "with_a2a_observability",
]