"""
Agent Improvement Coordination Module

Provides utilities for coordinating improvement deployments with the self-building agent.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


class ImprovementCoordinator:
    """
    Coordinates improvement deployments with agent availability and traffic patterns.
    """
    
    def __init__(
        self,
        agent_id: str,
        self_building_discovery,
        metrics_collector=None
    ):
        """
        Initialize improvement coordinator.
        
        Args:
            agent_id: Unique identifier for the agent
            self_building_discovery: SelfBuildingAgentDiscovery instance
            metrics_collector: Optional AgentMetricsCollector instance
        """
        self.agent_id = agent_id
        self.self_building_discovery = self_building_discovery
        self.metrics_collector = metrics_collector
        
        # Deployment schedule
        self.scheduled_deployments: Dict[str, Dict[str, Any]] = {}
        
        # Traffic monitoring
        self.current_request_rate = 0.0
        self.low_traffic_threshold = 10.0  # requests per minute
        
        logger.info(f"Improvement coordinator initialized for {agent_id}")
    
    async def schedule_improvement_deployment(
        self,
        improvement_id: str,
        deployment_window_hours: int = 24,
        prefer_low_traffic: bool = True,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedule an improvement deployment during optimal time.
        
        Args:
            improvement_id: Unique identifier for the improvement
            deployment_window_hours: Hours within which to deploy
            prefer_low_traffic: Whether to prefer low-traffic periods
            tenant_id: Optional tenant scope
            
        Returns:
            Deployment schedule information
        """
        try:
            # Determine optimal deployment time
            if prefer_low_traffic:
                deployment_time = await self._find_low_traffic_window(
                    deployment_window_hours
                )
            else:
                # Deploy immediately
                deployment_time = datetime.utcnow()
            
            # Store deployment schedule
            self.scheduled_deployments[improvement_id] = {
                "improvement_id": improvement_id,
                "scheduled_time": deployment_time,
                "status": "scheduled",
                "tenant_id": tenant_id,
                "created_at": datetime.utcnow()
            }
            
            logger.info(
                f"Scheduled improvement {improvement_id} for deployment at {deployment_time}"
            )
            
            return {
                "success": True,
                "improvement_id": improvement_id,
                "scheduled_time": deployment_time.isoformat(),
                "status": "scheduled",
                "message": f"Improvement scheduled for {deployment_time.isoformat()}"
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule improvement deployment: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _find_low_traffic_window(
        self,
        window_hours: int
    ) -> datetime:
        """
        Find a low-traffic window for deployment.
        
        Args:
            window_hours: Hours to search for low-traffic period
            
        Returns:
            Optimal deployment time
        """
        # Get current traffic metrics
        if self.metrics_collector:
            metrics_summary = self.metrics_collector.get_summary()
            avg_latency = metrics_summary.get("average_latency_ms", 0)
            
            # If current traffic is low, deploy now
            if avg_latency < 100:  # Low latency indicates low traffic
                return datetime.utcnow()
        
        # Default: schedule for off-peak hours (2 AM UTC)
        now = datetime.utcnow()
        next_deployment = now.replace(hour=2, minute=0, second=0, microsecond=0)
        
        # If 2 AM has passed today, schedule for tomorrow
        if next_deployment <= now:
            next_deployment += timedelta(days=1)
        
        # Ensure within deployment window
        max_deployment_time = now + timedelta(hours=window_hours)
        if next_deployment > max_deployment_time:
            # Deploy at end of window if optimal time is too far
            next_deployment = max_deployment_time
        
        return next_deployment
    
    async def request_improvement_deployment(
        self,
        improvement_type: str,
        target_components: list,
        priority: str = "normal",
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request an improvement deployment from the self-building agent.
        
        Args:
            improvement_type: Type of improvement (performance, bug_fix, feature)
            target_components: List of components to improve
            priority: Priority level (low, normal, high, critical)
            tenant_id: Optional tenant scope
            
        Returns:
            Deployment request result
        """
        if not self.self_building_discovery or not self.self_building_discovery.is_discovered():
            return {
                "success": False,
                "error": "Self-building agent not available"
            }
        
        try:
            # Prepare improvement request
            request_data = {
                "agent_id": self.agent_id,
                "improvement_type": improvement_type,
                "target_components": target_components,
                "priority": priority,
                "tenant_id": tenant_id,
                "requested_at": datetime.utcnow().isoformat()
            }
            
            # Call self-building agent to trigger improvement
            result = await self.self_building_discovery.call_self_building_tool(
                tool_name="trigger_improvement_cycle",
                arguments={
                    "analysis_window_hours": 24,
                    "max_improvements": len(target_components),
                    "tenant_id": tenant_id
                }
            )
            
            if result.get("success"):
                logger.info(
                    f"Improvement deployment requested for {self.agent_id}: "
                    f"{improvement_type} on {target_components}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to request improvement deployment: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def check_deployment_readiness(self) -> Dict[str, Any]:
        """
        Check if agent is ready for improvement deployment.
        
        Returns:
            Readiness status
        """
        readiness = {
            "ready": True,
            "reasons": [],
            "current_load": "unknown",
            "active_connections": 0,
            "error_rate": 0.0
        }
        
        # Check metrics if available
        if self.metrics_collector:
            metrics_summary = self.metrics_collector.get_summary()
            
            error_rate = metrics_summary.get("error_rate_percent", 0)
            avg_latency = metrics_summary.get("average_latency_ms", 0)
            
            readiness["error_rate"] = error_rate
            readiness["average_latency_ms"] = avg_latency
            
            # Check if error rate is too high
            if error_rate > 5.0:  # More than 5% errors
                readiness["ready"] = False
                readiness["reasons"].append(
                    f"High error rate: {error_rate:.2f}%"
                )
            
            # Check if latency is too high (indicates high load)
            if avg_latency > 1000:  # More than 1 second
                readiness["ready"] = False
                readiness["reasons"].append(
                    f"High latency: {avg_latency:.2f}ms"
                )
                readiness["current_load"] = "high"
            elif avg_latency > 500:
                readiness["current_load"] = "medium"
            else:
                readiness["current_load"] = "low"
        
        # Check self-building agent availability
        if self.self_building_discovery:
            if not self.self_building_discovery.is_discovered():
                readiness["ready"] = False
                readiness["reasons"].append("Self-building agent not discovered")
            else:
                # Check self-building agent health
                health = await self.self_building_discovery.check_self_building_health()
                if health.get("status") != "ok":
                    readiness["ready"] = False
                    readiness["reasons"].append(
                        f"Self-building agent unhealthy: {health.get('status')}"
                    )
        
        if readiness["ready"]:
            readiness["message"] = "Agent ready for improvement deployment"
        else:
            readiness["message"] = "Agent not ready for deployment"
        
        return readiness
    
    async def monitor_deployment(
        self,
        improvement_id: str,
        monitoring_duration_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        Monitor an improvement deployment.
        
        Args:
            improvement_id: Unique identifier for the improvement
            monitoring_duration_seconds: How long to monitor (default: 5 minutes)
            
        Returns:
            Monitoring results
        """
        if improvement_id not in self.scheduled_deployments:
            return {
                "success": False,
                "error": f"Improvement {improvement_id} not found in schedule"
            }
        
        deployment = self.scheduled_deployments[improvement_id]
        
        # Update status to monitoring
        deployment["status"] = "monitoring"
        deployment["monitoring_started_at"] = datetime.utcnow()
        
        # Collect baseline metrics
        baseline_metrics = None
        if self.metrics_collector:
            baseline_metrics = self.metrics_collector.get_summary()
        
        # Monitor for specified duration
        monitoring_results = {
            "improvement_id": improvement_id,
            "monitoring_duration_seconds": monitoring_duration_seconds,
            "baseline_metrics": baseline_metrics,
            "samples": []
        }
        
        # Sample metrics every 30 seconds
        sample_interval = 30
        num_samples = monitoring_duration_seconds // sample_interval
        
        for i in range(num_samples):
            await asyncio.sleep(sample_interval)
            
            if self.metrics_collector:
                current_metrics = self.metrics_collector.get_summary()
                monitoring_results["samples"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "metrics": current_metrics
                })
        
        # Analyze results
        deployment["status"] = "completed"
        deployment["monitoring_completed_at"] = datetime.utcnow()
        deployment["monitoring_results"] = monitoring_results
        
        # Determine if deployment was successful
        success = True
        if baseline_metrics and monitoring_results["samples"]:
            # Check if error rate increased significantly
            baseline_error_rate = baseline_metrics.get("error_rate_percent", 0)
            final_sample = monitoring_results["samples"][-1]["metrics"]
            final_error_rate = final_sample.get("error_rate_percent", 0)
            
            if final_error_rate > baseline_error_rate * 1.5:  # 50% increase
                success = False
                deployment["status"] = "degraded"
        
        return {
            "success": success,
            "improvement_id": improvement_id,
            "status": deployment["status"],
            "monitoring_results": monitoring_results
        }
    
    def get_scheduled_deployments(self) -> Dict[str, Dict[str, Any]]:
        """Get all scheduled deployments."""
        return self.scheduled_deployments.copy()
    
    def cancel_deployment(self, improvement_id: str) -> bool:
        """Cancel a scheduled deployment."""
        if improvement_id in self.scheduled_deployments:
            self.scheduled_deployments[improvement_id]["status"] = "cancelled"
            logger.info(f"Cancelled deployment for improvement {improvement_id}")
            return True
        return False
