"""
Standardized Metrics Collection for HappyOS SDK

Provides unified metrics collection with consistent naming, dimensions,
and collection patterns across all HappyOS agent systems.
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .logging import get_logger
from .telemetry import get_telemetry

# Try to import backend observability for integration
try:
    from backend.modules.observability.cloudwatch import get_cloudwatch_monitor, MetricUnit
    CLOUDWATCH_AVAILABLE = True
except ImportError:
    CLOUDWATCH_AVAILABLE = False
    MetricUnit = None

logger = get_logger(__name__)


class MetricType(Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricDefinition:
    """Definition of a standardized metric."""
    name: str
    metric_type: MetricType
    unit: str
    description: str
    dimensions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for registration."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "unit": self.unit,
            "description": self.description,
            "dimensions": self.dimensions
        }


class StandardizedMetrics:
    """Standardized metric definitions for HappyOS agents."""
    
    # MCP Protocol Metrics
    MCP_CALL_DURATION = MetricDefinition(
        name="MCPCallDuration",
        metric_type=MetricType.HISTOGRAM,
        unit="Milliseconds",
        description="Duration of MCP tool calls",
        dimensions=["AgentType", "TargetAgent", "ToolName", "TenantId", "Status"]
    )
    
    MCP_CALL_SUCCESS = MetricDefinition(
        name="MCPCallSuccess",
        metric_type=MetricType.COUNTER,
        unit="Count",
        description="Successful MCP tool calls",
        dimensions=["AgentType", "TargetAgent", "ToolName", "TenantId"]
    )
    
    MCP_CALL_ERROR = MetricDefinition(
        name="MCPCallError",
        metric_type=MetricType.COUNTER,
        unit="Count",
        description="Failed MCP tool calls",
        dimensions=["AgentType", "TargetAgent", "ToolName", "TenantId", "ErrorCode"]
    )
    
    MCP_CALLBACK_DURATION = MetricDefinition(
        name="MCPCallbackDuration",
        metric_type=MetricType.HISTOGRAM,
        unit="Milliseconds",
        description="Duration of MCP callback processing",
        dimensions=["AgentType", "SourceAgent", "TenantId", "Status"]
    )
    
    # Agent Performance Metrics
    AGENT_RESPONSE_TIME = MetricDefinition(
        name="AgentResponseTime",
        metric_type=MetricType.HISTOGRAM,
        unit="Milliseconds",
        description="Agent response time for operations",
        dimensions=["AgentType", "Operation", "TenantId", "Status"]
    )
    
    AGENT_UPTIME = MetricDefinition(
        name="AgentUptime",
        metric_type=MetricType.GAUGE,
        unit="Seconds",
        description="Agent uptime in seconds",
        dimensions=["AgentType", "AgentId", "Environment"]
    )
    
    AGENT_MEMORY_USAGE = MetricDefinition(
        name="AgentMemoryUsage",
        metric_type=MetricType.GAUGE,
        unit="Megabytes",
        description="Agent memory usage",
        dimensions=["AgentType", "AgentId", "Environment"]
    )
    
    AGENT_CPU_USAGE = MetricDefinition(
        name="AgentCPUUsage",
        metric_type=MetricType.GAUGE,
        unit="Percent",
        description="Agent CPU usage percentage",
        dimensions=["AgentType", "AgentId", "Environment"]
    )
    
    # Circuit Breaker Metrics
    CIRCUIT_BREAKER_STATE = MetricDefinition(
        name="CircuitBreakerState",
        metric_type=MetricType.GAUGE,
        unit="Count",
        description="Circuit breaker state (0=closed, 1=open, 2=half-open)",
        dimensions=["AgentType", "ServiceName", "TenantId"]
    )
    
    CIRCUIT_BREAKER_EVENTS = MetricDefinition(
        name="CircuitBreakerEvents",
        metric_type=MetricType.COUNTER,
        unit="Count",
        description="Circuit breaker state change events",
        dimensions=["AgentType", "ServiceName", "EventType", "TenantId"]
    )
    
    CIRCUIT_BREAKER_SUCCESS_RATE = MetricDefinition(
        name="CircuitBreakerSuccessRate",
        metric_type=MetricType.GAUGE,
        unit="Percent",
        description="Circuit breaker success rate",
        dimensions=["AgentType", "ServiceName", "TenantId"]
    )
    
    # Isolation and Compliance Metrics
    ISOLATION_VIOLATIONS = MetricDefinition(
        name="IsolationViolations",
        metric_type=MetricType.COUNTER,
        unit="Count",
        description="Backend.* import violations detected",
        dimensions=["AgentType", "ViolationType", "ModuleName"]
    )
    
    COMPLIANCE_CHECKS = MetricDefinition(
        name="ComplianceChecks",
        metric_type=MetricType.COUNTER,
        unit="Count",
        description="Compliance validation checks performed",
        dimensions=["AgentType", "CheckType", "TenantId", "Status"]
    )
    
    # Cross-Agent Workflow Metrics
    WORKFLOW_DURATION = MetricDefinition(
        name="WorkflowDuration",
        metric_type=MetricType.HISTOGRAM,
        unit="Milliseconds",
        description="End-to-end workflow duration",
        dimensions=["WorkflowType", "ParticipatingAgents", "TenantId", "Status"]
    )
    
    WORKFLOW_STEPS = MetricDefinition(
        name="WorkflowSteps",
        metric_type=MetricType.COUNTER,
        unit="Count",
        description="Individual workflow steps completed",
        dimensions=["WorkflowType", "StepName", "AgentType", "TenantId", "Status"]
    )
    
    FAN_IN_RESULTS = MetricDefinition(
        name="FanInResults",
        metric_type=MetricType.COUNTER,
        unit="Count",
        description="Results collected by MeetMind fan-in logic",
        dimensions=["SourceAgent", "ResultType", "TenantId", "Status"]
    )
    
    # Health Check Metrics
    HEALTH_CHECK_DURATION = MetricDefinition(
        name="HealthCheckDuration",
        metric_type=MetricType.HISTOGRAM,
        unit="Milliseconds",
        description="Health check execution duration",
        dimensions=["AgentType", "CheckType", "Status"]
    )
    
    HEALTH_STATUS = MetricDefinition(
        name="HealthStatus",
        metric_type=MetricType.GAUGE,
        unit="Count",
        description="Agent health status (0=unhealthy, 1=degraded, 2=healthy)",
        dimensions=["AgentType", "AgentId", "TenantId"]
    )
    
    @classmethod
    def get_all_metrics(cls) -> List[MetricDefinition]:
        """Get all standardized metric definitions."""
        metrics = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, MetricDefinition):
                metrics.append(attr)
        return metrics


class StandardizedMetricsCollector:
    """Standardized metrics collector for HappyOS agents."""
    
    def __init__(self, agent_type: str, agent_id: str, environment: str = "development"):
        """
        Initialize metrics collector.
        
        Args:
            agent_type: Type of agent (agent_svea, felicias_finance, meetmind)
            agent_id: Unique agent identifier
            environment: Environment name (development, staging, production)
        """
        self.agent_type = agent_type
        self.agent_id = agent_id
        self.environment = environment
        
        # Initialize telemetry and CloudWatch integration
        self.telemetry = get_telemetry()
        self.cloudwatch = None
        
        if CLOUDWATCH_AVAILABLE:
            try:
                self.cloudwatch = get_cloudwatch_monitor()
                logger.info("CloudWatch metrics integration enabled")
            except Exception as e:
                logger.warning(f"CloudWatch metrics not available: {e}")
        
        # Metric collection state
        self.active_timers: Dict[str, float] = {}
        self.metric_buffer: List[Dict[str, Any]] = []
        
        logger.info(f"Initialized metrics collector for {agent_type}:{agent_id}")
    
    def _get_base_dimensions(self, additional_dimensions: Dict[str, str] = None) -> Dict[str, str]:
        """Get base dimensions for all metrics."""
        dimensions = {
            "AgentType": self.agent_type,
            "AgentId": self.agent_id,
            "Environment": self.environment
        }
        
        if additional_dimensions:
            dimensions.update(additional_dimensions)
        
        return dimensions
    
    async def record_counter(self, metric: MetricDefinition, value: int = 1, 
                           dimensions: Dict[str, str] = None, tenant_id: str = None):
        """Record a counter metric."""
        if metric.metric_type != MetricType.COUNTER:
            raise ValueError(f"Metric {metric.name} is not a counter")
        
        # Prepare dimensions
        all_dimensions = self._get_base_dimensions(dimensions)
        if tenant_id:
            all_dimensions["TenantId"] = tenant_id
        
        # Record to telemetry
        self.telemetry.increment_counter(metric.name, value, all_dimensions)
        
        # Record to CloudWatch if available
        if self.cloudwatch:
            try:
                await self.cloudwatch.put_metric(
                    metric.name,
                    value,
                    self._get_cloudwatch_unit(metric.unit),
                    all_dimensions,
                    tenant_id
                )
            except Exception as e:
                logger.warning(f"Failed to send counter to CloudWatch: {e}")
        
        logger.debug(f"Recorded counter {metric.name}: {value}", extra=all_dimensions)
    
    async def record_gauge(self, metric: MetricDefinition, value: float,
                         dimensions: Dict[str, str] = None, tenant_id: str = None):
        """Record a gauge metric."""
        if metric.metric_type != MetricType.GAUGE:
            raise ValueError(f"Metric {metric.name} is not a gauge")
        
        # Prepare dimensions
        all_dimensions = self._get_base_dimensions(dimensions)
        if tenant_id:
            all_dimensions["TenantId"] = tenant_id
        
        # Record to telemetry
        self.telemetry.set_gauge(metric.name, value, all_dimensions)
        
        # Record to CloudWatch if available
        if self.cloudwatch:
            try:
                await self.cloudwatch.put_metric(
                    metric.name,
                    value,
                    self._get_cloudwatch_unit(metric.unit),
                    all_dimensions,
                    tenant_id
                )
            except Exception as e:
                logger.warning(f"Failed to send gauge to CloudWatch: {e}")
        
        logger.debug(f"Recorded gauge {metric.name}: {value}", extra=all_dimensions)
    
    async def record_histogram(self, metric: MetricDefinition, value: float,
                             dimensions: Dict[str, str] = None, tenant_id: str = None):
        """Record a histogram metric."""
        if metric.metric_type not in [MetricType.HISTOGRAM, MetricType.TIMER]:
            raise ValueError(f"Metric {metric.name} is not a histogram or timer")
        
        # Prepare dimensions
        all_dimensions = self._get_base_dimensions(dimensions)
        if tenant_id:
            all_dimensions["TenantId"] = tenant_id
        
        # Record to telemetry
        self.telemetry.record_value(metric.name, value, all_dimensions)
        
        # Record to CloudWatch if available
        if self.cloudwatch:
            try:
                await self.cloudwatch.put_metric(
                    metric.name,
                    value,
                    self._get_cloudwatch_unit(metric.unit),
                    all_dimensions,
                    tenant_id
                )
            except Exception as e:
                logger.warning(f"Failed to send histogram to CloudWatch: {e}")
        
        logger.debug(f"Recorded histogram {metric.name}: {value}", extra=all_dimensions)
    
    def start_timer(self, metric: MetricDefinition, timer_id: str = None) -> str:
        """Start a timer for a metric."""
        if metric.metric_type != MetricType.TIMER:
            raise ValueError(f"Metric {metric.name} is not a timer")
        
        timer_id = timer_id or f"{metric.name}_{int(time.time() * 1000000)}"
        self.active_timers[timer_id] = time.time()
        
        logger.debug(f"Started timer {timer_id} for {metric.name}")
        return timer_id
    
    async def end_timer(self, metric: MetricDefinition, timer_id: str,
                       dimensions: Dict[str, str] = None, tenant_id: str = None):
        """End a timer and record the duration."""
        if timer_id not in self.active_timers:
            logger.warning(f"Timer {timer_id} not found")
            return
        
        start_time = self.active_timers.pop(timer_id)
        duration_ms = (time.time() - start_time) * 1000
        
        await self.record_histogram(metric, duration_ms, dimensions, tenant_id)
        
        logger.debug(f"Ended timer {timer_id}: {duration_ms}ms")
    
    def _get_cloudwatch_unit(self, unit: str) -> Any:
        """Convert unit string to CloudWatch MetricUnit."""
        if not CLOUDWATCH_AVAILABLE:
            return None
        
        unit_mapping = {
            "Count": MetricUnit.COUNT,
            "Milliseconds": MetricUnit.MILLISECONDS,
            "Seconds": MetricUnit.SECONDS,
            "Percent": MetricUnit.PERCENT,
            "Megabytes": MetricUnit.MEGABYTES,
            "Bytes": MetricUnit.BYTES
        }
        
        return unit_mapping.get(unit, MetricUnit.NONE)
    
    # Convenience methods for common metrics
    
    async def record_mcp_call(self, target_agent: str, tool_name: str, 
                            duration_ms: float, success: bool, 
                            tenant_id: str = None, error_code: str = None):
        """Record MCP call metrics."""
        dimensions = {
            "TargetAgent": target_agent,
            "ToolName": tool_name,
            "Status": "success" if success else "error"
        }
        
        # Record duration
        await self.record_histogram(
            StandardizedMetrics.MCP_CALL_DURATION,
            duration_ms,
            dimensions,
            tenant_id
        )
        
        # Record success/error count
        if success:
            await self.record_counter(
                StandardizedMetrics.MCP_CALL_SUCCESS,
                1,
                dimensions,
                tenant_id
            )
        else:
            error_dimensions = {**dimensions, "ErrorCode": error_code or "unknown"}
            await self.record_counter(
                StandardizedMetrics.MCP_CALL_ERROR,
                1,
                error_dimensions,
                tenant_id
            )
    
    async def record_mcp_callback(self, source_agent: str, duration_ms: float,
                                success: bool, tenant_id: str = None):
        """Record MCP callback metrics."""
        dimensions = {
            "SourceAgent": source_agent,
            "Status": "success" if success else "error"
        }
        
        await self.record_histogram(
            StandardizedMetrics.MCP_CALLBACK_DURATION,
            duration_ms,
            dimensions,
            tenant_id
        )
    
    async def record_agent_performance(self, operation: str, duration_ms: float,
                                     success: bool, tenant_id: str = None):
        """Record agent performance metrics."""
        dimensions = {
            "Operation": operation,
            "Status": "success" if success else "error"
        }
        
        await self.record_histogram(
            StandardizedMetrics.AGENT_RESPONSE_TIME,
            duration_ms,
            dimensions,
            tenant_id
        )
    
    async def record_circuit_breaker_event(self, service_name: str, event_type: str,
                                         state: str, success_rate: float = None,
                                         tenant_id: str = None):
        """Record circuit breaker metrics."""
        # Record event
        await self.record_counter(
            StandardizedMetrics.CIRCUIT_BREAKER_EVENTS,
            1,
            {"ServiceName": service_name, "EventType": event_type},
            tenant_id
        )
        
        # Record state (0=closed, 1=open, 2=half-open)
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        await self.record_gauge(
            StandardizedMetrics.CIRCUIT_BREAKER_STATE,
            state_value,
            {"ServiceName": service_name},
            tenant_id
        )
        
        # Record success rate if provided
        if success_rate is not None:
            await self.record_gauge(
                StandardizedMetrics.CIRCUIT_BREAKER_SUCCESS_RATE,
                success_rate,
                {"ServiceName": service_name},
                tenant_id
            )
    
    async def record_isolation_violation(self, violation_type: str, module_name: str):
        """Record isolation violation metrics."""
        await self.record_counter(
            StandardizedMetrics.ISOLATION_VIOLATIONS,
            1,
            {"ViolationType": violation_type, "ModuleName": module_name}
        )
    
    async def record_health_status(self, status: str, check_duration_ms: float = None,
                                 tenant_id: str = None):
        """Record health status metrics."""
        # Record health status (0=unhealthy, 1=degraded, 2=healthy)
        status_value = {"unhealthy": 0, "degraded": 1, "healthy": 2}.get(status, 0)
        await self.record_gauge(
            StandardizedMetrics.HEALTH_STATUS,
            status_value,
            {},
            tenant_id
        )
        
        # Record health check duration if provided
        if check_duration_ms is not None:
            await self.record_histogram(
                StandardizedMetrics.HEALTH_CHECK_DURATION,
                check_duration_ms,
                {"CheckType": "full", "Status": status}
            )
    
    async def record_workflow_metrics(self, workflow_type: str, participating_agents: List[str],
                                    duration_ms: float = None, step_name: str = None,
                                    success: bool = True, tenant_id: str = None):
        """Record cross-agent workflow metrics."""
        agents_str = ",".join(sorted(participating_agents))
        status = "success" if success else "error"
        
        # Record workflow duration if provided
        if duration_ms is not None:
            await self.record_histogram(
                StandardizedMetrics.WORKFLOW_DURATION,
                duration_ms,
                {
                    "WorkflowType": workflow_type,
                    "ParticipatingAgents": agents_str,
                    "Status": status
                },
                tenant_id
            )
        
        # Record workflow step if provided
        if step_name is not None:
            await self.record_counter(
                StandardizedMetrics.WORKFLOW_STEPS,
                1,
                {
                    "WorkflowType": workflow_type,
                    "StepName": step_name,
                    "Status": status
                },
                tenant_id
            )
    
    async def record_fan_in_result(self, source_agent: str, result_type: str,
                                 success: bool = True, tenant_id: str = None):
        """Record fan-in result collection metrics."""
        await self.record_counter(
            StandardizedMetrics.FAN_IN_RESULTS,
            1,
            {
                "SourceAgent": source_agent,
                "ResultType": result_type,
                "Status": "success" if success else "error"
            },
            tenant_id
        )
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        return self.telemetry.get_telemetry_summary()


# Global metrics collectors
_metrics_collectors: Dict[str, StandardizedMetricsCollector] = {}


def get_metrics_collector(agent_type: str, agent_id: str, 
                         environment: str = "development") -> StandardizedMetricsCollector:
    """Get or create standardized metrics collector for an agent."""
    key = f"{agent_type}:{agent_id}"
    
    if key not in _metrics_collectors:
        _metrics_collectors[key] = StandardizedMetricsCollector(agent_type, agent_id, environment)
    
    return _metrics_collectors[key]