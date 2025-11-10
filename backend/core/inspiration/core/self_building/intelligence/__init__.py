"""Intelligence and audit modules."""

from .audit_logger import (
    audit_logger,
    AuditEventType,
    AuditEvent,
    log_component_discovered,
    log_skill_auto_generated,
    log_error
)

from .learning_engine import (
    LearningEngine,
    TelemetryInsight,
    ImprovementOpportunity
)

from .cloudwatch_streamer import (
    CloudWatchTelemetryStreamer,
    MetricDataPoint,
    LogEvent,
    CloudWatchEvent
)

__all__ = [
    "audit_logger",
    "AuditEventType", 
    "AuditEvent",
    "log_component_discovered",
    "log_skill_auto_generated",
    "log_error",
    "LearningEngine",
    "TelemetryInsight",
    "ImprovementOpportunity",
    "CloudWatchTelemetryStreamer",
    "MetricDataPoint",
    "LogEvent",
    "CloudWatchEvent"
]