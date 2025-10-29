"""
Observability Integration for HappyOS SDK

Integrates all observability components (health monitoring, metrics collection,
dashboards, alerting, and distributed tracing) into a unified system.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .health_monitoring import get_health_monitor, StandardizedHealthMonitor
from .metrics_collection import get_metrics_collector, StandardizedMetricsCollector
from .unified_dashboards import get_dashboard_manager, UnifiedDashboardManager
from .unified_alerting import get_alerting_system, UnifiedAlertingSystem
from .distributed_tracing import get_distributed_tracer, DistributedTracer
from .logging import get_logger

logger = get_logger(__name__)


class ObservabilityIntegration:
    """Unified observability integration for HappyOS agents."""
    
    def __init__(self, agent_type: str, agent_id: str, environment: str = "development"):
        """
        Initialize observability integration.
        
        Args:
            agent_type: Type of agent (agent_svea, felicias_finance, meetmind)
            agent_id: Unique agent identifier
            environment: Environment name (development, staging, production)
        """
        self.agent_type = agent_type
        self.agent_id = agent_id
        self.environment = environment
        
        # Initialize all observability components
        self.health_monitor = get_health_monitor(agent_type, agent_id)
        self.metrics_collector = get_metrics_collector(agent_type, agent_id, environment)
        self.dashboard_manager = get_dashboard_manager()
        self.alerting_system = get_alerting_system()
        self.distributed_tracer = get_distributed_tracer(agent_type, agent_id)
        
        # Setup integrations
        self._setup_integrations()
        
        logger.info(f"Observability integration initialized for {agent_type}:{agent_id}")
    
    def _setup_integrations(self):
        """Setup integrations between observability components."""
        
        # Register notification handlers for alerting
        self.alerting_system.register_notification_handler(
            "metrics", self._metrics_notification_handler
        )
        
        # Register trace processor for metrics
        self.distributed_tracer.add_trace_processor(self._trace_metrics_processor)
        
        # Register health check dependencies
        self._register_health_dependencies()
        
        logger.debug("Observability component integrations configured")
    
    def _register_health_dependencies(self):
        """Register health check dependencies."""
        
        # Register observability system health checks
        self.health_monitor.register_dependency_check(
            "metrics_collection",
            lambda: {"status": "available"}  # Metrics collection is always available
        )
        
        self.health_monitor.register_dependency_check(
            "distributed_tracing",
            lambda: {
                "status": "available" if self.distributed_tracer else "unavailable"
            }
        )
        
        self.health_monitor.register_dependency_check(
            "alerting_system",
            lambda: {
                "status": "available" if self.alerting_system else "unavailable"
            }
        )
    
    async def _metrics_notification_handler(self, alert, rule):
        """Handle alert notifications by recording metrics."""
        try:
            await self.metrics_collector.record_counter(
                self.metrics_collector.StandardizedMetrics.COMPLIANCE_CHECKS,
                1,
                {"CheckType": "alert_triggered", "Severity": alert.severity.value},
                alert.tenant_id
            )
        except Exception as e:
            logger.error(f"Failed to record alert metrics: {e}")
    
    async def _trace_metrics_processor(self, trace_context):
        """Process completed traces to generate metrics."""
        try:
            # Record operation metrics based on trace
            if trace_context.operation_type == "mcp_call":
                target_agent = trace_context.tags.get("target_agent", "unknown")
                tool_name = trace_context.tags.get("tool_name", "unknown")
                
                await self.metrics_collector.record_mcp_call(
                    target_agent=target_agent,
                    tool_name=tool_name,
                    duration_ms=trace_context.duration_ms or 0,
                    success=trace_context.status == "success",
                    tenant_id=trace_context.tenant_id,
                    error_code=trace_context.error_message if trace_context.status == "error" else None
                )
            
            elif trace_context.operation_type == "mcp_callback":
                source_agent = trace_context.tags.get("source_agent", "unknown")
                
                await self.metrics_collector.record_mcp_callback(
                    source_agent=source_agent,
                    duration_ms=trace_context.duration_ms or 0,
                    success=trace_context.status == "success",
                    tenant_id=trace_context.tenant_id
                )
            
            elif trace_context.operation_type == "workflow":
                workflow_type = trace_context.tags.get("workflow_type", "unknown")
                participating_agents = trace_context.tags.get("participating_agents", "").split(",")
                
                await self.metrics_collector.record_workflow_metrics(
                    workflow_type=workflow_type,
                    participating_agents=participating_agents,
                    duration_ms=trace_context.duration_ms,
                    success=trace_context.status == "success",
                    tenant_id=trace_context.tenant_id
                )
            
            # Record general performance metrics
            await self.metrics_collector.record_agent_performance(
                operation=trace_context.operation_name,
                duration_ms=trace_context.duration_ms or 0,
                success=trace_context.status == "success",
                tenant_id=trace_context.tenant_id
            )
            
        except Exception as e:
            logger.error(f"Failed to process trace metrics: {e}")
    
    async def start_mcp_operation(self, operation_name: str, target_agent: str = None,
                                tool_name: str = None, headers: Dict[str, str] = None,
                                tenant_id: str = None):
        """Start an MCP operation with full observability."""
        
        # Start distributed trace
        if target_agent and tool_name:
            trace_context = self.distributed_tracer.trace_mcp_call(target_agent, tool_name, headers)
        else:
            trace_context = self.distributed_tracer.start_trace(
                operation_name=operation_name,
                operation_type="mcp_operation",
                tenant_id=tenant_id
            )
        
        # Record operation start metrics
        await self.metrics_collector.record_counter(
            self.metrics_collector.StandardizedMetrics.MCP_CALL_SUCCESS,
            0,  # Will be incremented on success
            {"TargetAgent": target_agent or "unknown", "ToolName": tool_name or "unknown"},
            tenant_id
        )
        
        return trace_context
    
    async def finish_mcp_operation(self, trace_context, success: bool = True,
                                 error_message: str = None, result_data: Dict[str, Any] = None):
        """Finish an MCP operation with full observability."""
        
        # Finish distributed trace
        status = "success" if success else "error"
        self.distributed_tracer.finish_trace(
            trace_context.span_id, status, error_message
        )
        
        # Record final metrics
        if success:
            await self.metrics_collector.record_counter(
                self.metrics_collector.StandardizedMetrics.MCP_CALL_SUCCESS,
                1,
                {
                    "TargetAgent": trace_context.tags.get("target_agent", "unknown"),
                    "ToolName": trace_context.tags.get("tool_name", "unknown")
                },
                trace_context.tenant_id
            )
        else:
            await self.metrics_collector.record_counter(
                self.metrics_collector.StandardizedMetrics.MCP_CALL_ERROR,
                1,
                {
                    "TargetAgent": trace_context.tags.get("target_agent", "unknown"),
                    "ToolName": trace_context.tags.get("tool_name", "unknown"),
                    "ErrorCode": error_message or "unknown"
                },
                trace_context.tenant_id
            )
        
        # Evaluate metrics for alerting
        if trace_context.duration_ms:
            await self.alerting_system.evaluate_metric(
                "AgentResponseTime",
                trace_context.duration_ms,
                {"AgentType": self.agent_type},
                self.agent_type,
                self.agent_id,
                trace_context.tenant_id
            )
    
    async def record_health_check(self, tenant_id: str = None) -> Dict[str, Any]:
        """Perform health check with full observability integration."""
        
        # Start trace for health check
        trace_context = self.distributed_tracer.start_trace(
            operation_name="health_check",
            operation_type="health_check",
            tenant_id=tenant_id
        )
        
        try:
            # Get health status
            health_response = await self.health_monitor.get_health_status(tenant_id)
            
            # Record health metrics
            await self.metrics_collector.record_health_status(
                health_response.status.value,
                health_response.response_time_ms,
                tenant_id
            )
            
            # Evaluate health for alerting
            await self.alerting_system.evaluate_metric(
                "HealthStatus",
                {"healthy": 2, "degraded": 1, "unhealthy": 0}[health_response.status.value],
                {"AgentType": self.agent_type},
                self.agent_type,
                self.agent_id,
                tenant_id
            )
            
            # Finish trace
            self.distributed_tracer.finish_trace(trace_context.span_id, "success")
            
            return health_response.to_dict()
            
        except Exception as e:
            # Finish trace with error
            self.distributed_tracer.finish_trace(trace_context.span_id, "error", str(e))
            
            # Record error metrics
            await self.metrics_collector.record_counter(
                self.metrics_collector.StandardizedMetrics.MCP_CALL_ERROR,
                1,
                {"ErrorCode": "health_check_failed"},
                tenant_id
            )
            
            raise
    
    async def record_circuit_breaker_event(self, service_name: str, event_type: str,
                                         state: str, success_rate: float = None,
                                         tenant_id: str = None):
        """Record circuit breaker event with full observability."""
        
        # Record metrics
        await self.metrics_collector.record_circuit_breaker_event(
            service_name, event_type, state, success_rate, tenant_id
        )
        
        # Evaluate for alerting
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        await self.alerting_system.evaluate_metric(
            "CircuitBreakerState",
            state_value,
            {"AgentType": self.agent_type, "ServiceName": service_name},
            self.agent_type,
            self.agent_id,
            tenant_id
        )
        
        # Log circuit breaker event
        logger.info(
            f"Circuit breaker event: {service_name} {event_type}",
            extra={
                "agent_type": self.agent_type,
                "service_name": service_name,
                "event_type": event_type,
                "state": state,
                "success_rate": success_rate,
                "tenant_id": tenant_id
            }
        )
    
    async def setup_monitoring_infrastructure(self) -> Dict[str, Any]:
        """Setup complete monitoring infrastructure for the agent."""
        
        logger.info(f"Setting up monitoring infrastructure for {self.agent_type}")
        
        results = {}
        
        try:
            # Create dashboards
            dashboard_results = await self.dashboard_manager.create_all_standard_dashboards()
            results["dashboards"] = dashboard_results
            
            # Create alert rules
            alert_results = await self.alerting_system.create_alert_rules()
            results["alerts"] = alert_results
            
            # Setup health monitoring
            results["health_monitoring"] = {
                "dependencies_registered": len(self.health_monitor.dependency_checks),
                "circuit_breakers_registered": len(self.health_monitor.circuit_breaker_checks)
            }
            
            # Setup metrics collection
            results["metrics_collection"] = {
                "collector_initialized": True,
                "cloudwatch_available": hasattr(self.metrics_collector, 'cloudwatch') and self.metrics_collector.cloudwatch is not None
            }
            
            # Setup distributed tracing
            results["distributed_tracing"] = {
                "tracer_initialized": True,
                "xray_available": hasattr(self.distributed_tracer, 'xray_tracer') and self.distributed_tracer.xray_tracer is not None,
                "processors_registered": len(self.distributed_tracer.trace_processors)
            }
            
            results["overall_success"] = all([
                all(dashboard_results.values()) if dashboard_results else True,
                all(alert_results.values()) if alert_results else True
            ])
            
            logger.info(f"Monitoring infrastructure setup completed: {results}")
            
        except Exception as e:
            logger.error(f"Failed to setup monitoring infrastructure: {e}")
            results["error"] = str(e)
            results["overall_success"] = False
        
        return results
    
    async def get_observability_status(self) -> Dict[str, Any]:
        """Get comprehensive observability status."""
        
        return {
            "agent_info": {
                "agent_type": self.agent_type,
                "agent_id": self.agent_id,
                "environment": self.environment
            },
            "health_monitoring": {
                "status": "active",
                "dependencies": len(self.health_monitor.dependency_checks),
                "circuit_breakers": len(self.health_monitor.circuit_breaker_checks)
            },
            "metrics_collection": self.metrics_collector.get_metrics_summary(),
            "alerting": self.alerting_system.get_alert_summary(),
            "distributed_tracing": self.distributed_tracer.get_trace_summary(),
            "dashboards": {
                "manager_initialized": self.dashboard_manager is not None,
                "cloudwatch_available": hasattr(self.dashboard_manager, 'cloudwatch') and self.dashboard_manager.cloudwatch is not None
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global observability integrations
_observability_integrations: Dict[str, ObservabilityIntegration] = {}


def get_observability_integration(agent_type: str, agent_id: str, 
                                environment: str = "development") -> ObservabilityIntegration:
    """Get or create observability integration for an agent."""
    key = f"{agent_type}:{agent_id}"
    
    if key not in _observability_integrations:
        _observability_integrations[key] = ObservabilityIntegration(agent_type, agent_id, environment)
    
    return _observability_integrations[key]


# Convenience functions for common operations
async def setup_agent_observability(agent_type: str, agent_id: str, 
                                  environment: str = "development") -> Dict[str, Any]:
    """Setup complete observability for an agent."""
    integration = get_observability_integration(agent_type, agent_id, environment)
    return await integration.setup_monitoring_infrastructure()


async def get_agent_observability_status(agent_type: str, agent_id: str) -> Dict[str, Any]:
    """Get observability status for an agent."""
    integration = get_observability_integration(agent_type, agent_id)
    return await integration.get_observability_status()


async def record_agent_health(agent_type: str, agent_id: str, 
                            tenant_id: str = None) -> Dict[str, Any]:
    """Record health check for an agent with full observability."""
    integration = get_observability_integration(agent_type, agent_id)
    return await integration.record_health_check(tenant_id)