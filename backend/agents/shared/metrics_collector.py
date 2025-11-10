"""
Agent Metrics Collection Module

Provides utilities for collecting and sending agent-specific metrics to CloudWatch.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)


class AgentMetricsCollector:
    """
    Collects and sends agent-specific metrics to CloudWatch.
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        cloudwatch_namespace: str = "HappyOS/Agents",
        enable_cloudwatch: bool = True
    ):
        """
        Initialize agent metrics collector.
        
        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type of agent (meetmind, agent_svea, felicias_finance)
            cloudwatch_namespace: CloudWatch namespace for metrics
            enable_cloudwatch: Whether to send metrics to CloudWatch
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.cloudwatch_namespace = cloudwatch_namespace
        self.enable_cloudwatch = enable_cloudwatch
        
        # Local metrics storage
        self.metrics_buffer: List[Dict[str, Any]] = []
        self.max_buffer_size = 100
        
        # CloudWatch client (lazy initialization)
        self._cloudwatch_client = None
        
        # Metric counters
        self.request_count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0
        
        logger.info(
            f"Metrics collector initialized for {agent_id} "
            f"(cloudwatch={'enabled' if enable_cloudwatch else 'disabled'})"
        )
    
    def _get_cloudwatch_client(self):
        """Lazy initialization of CloudWatch client."""
        if not self.enable_cloudwatch:
            return None
        
        if self._cloudwatch_client is None:
            try:
                import boto3
                self._cloudwatch_client = boto3.client('cloudwatch')
                logger.info(f"CloudWatch client initialized for {self.agent_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize CloudWatch client: {e}")
                self.enable_cloudwatch = False
        
        return self._cloudwatch_client
    
    async def record_request(
        self,
        endpoint: str,
        method: str = "POST",
        status_code: int = 200,
        latency_ms: float = 0.0,
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record an API request metric.
        
        Args:
            endpoint: API endpoint called
            method: HTTP method
            status_code: Response status code
            latency_ms: Request latency in milliseconds
            tenant_id: Optional tenant identifier
            metadata: Additional metadata
        """
        self.request_count += 1
        self.total_latency_ms += latency_ms
        
        if status_code >= 400:
            self.error_count += 1
        
        metric = {
            "metric_name": "RequestCount",
            "value": 1,
            "unit": "Count",
            "dimensions": {
                "AgentId": self.agent_id,
                "AgentType": self.agent_type,
                "Endpoint": endpoint,
                "Method": method,
                "StatusCode": str(status_code)
            },
            "timestamp": datetime.utcnow()
        }
        
        if tenant_id:
            metric["dimensions"]["TenantId"] = tenant_id
        
        await self._buffer_metric(metric)
        
        # Also record latency
        latency_metric = {
            "metric_name": "RequestLatency",
            "value": latency_ms,
            "unit": "Milliseconds",
            "dimensions": {
                "AgentId": self.agent_id,
                "AgentType": self.agent_type,
                "Endpoint": endpoint
            },
            "timestamp": datetime.utcnow()
        }
        
        if tenant_id:
            latency_metric["dimensions"]["TenantId"] = tenant_id
        
        await self._buffer_metric(latency_metric)
    
    async def record_error(
        self,
        error_type: str,
        error_message: str,
        endpoint: Optional[str] = None,
        tenant_id: Optional[str] = None
    ):
        """
        Record an error metric.
        
        Args:
            error_type: Type of error
            error_message: Error message
            endpoint: Optional endpoint where error occurred
            tenant_id: Optional tenant identifier
        """
        self.error_count += 1
        
        metric = {
            "metric_name": "ErrorCount",
            "value": 1,
            "unit": "Count",
            "dimensions": {
                "AgentId": self.agent_id,
                "AgentType": self.agent_type,
                "ErrorType": error_type
            },
            "timestamp": datetime.utcnow()
        }
        
        if endpoint:
            metric["dimensions"]["Endpoint"] = endpoint
        
        if tenant_id:
            metric["dimensions"]["TenantId"] = tenant_id
        
        await self._buffer_metric(metric)
    
    async def record_resource_usage(
        self,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[float] = None,
        active_connections: Optional[int] = None
    ):
        """
        Record resource usage metrics.
        
        Args:
            cpu_percent: CPU usage percentage
            memory_mb: Memory usage in MB
            active_connections: Number of active connections
        """
        if cpu_percent is not None:
            await self._buffer_metric({
                "metric_name": "CPUUtilization",
                "value": cpu_percent,
                "unit": "Percent",
                "dimensions": {
                    "AgentId": self.agent_id,
                    "AgentType": self.agent_type
                },
                "timestamp": datetime.utcnow()
            })
        
        if memory_mb is not None:
            await self._buffer_metric({
                "metric_name": "MemoryUtilization",
                "value": memory_mb,
                "unit": "Megabytes",
                "dimensions": {
                    "AgentId": self.agent_id,
                    "AgentType": self.agent_type
                },
                "timestamp": datetime.utcnow()
            })
        
        if active_connections is not None:
            await self._buffer_metric({
                "metric_name": "ActiveConnections",
                "value": active_connections,
                "unit": "Count",
                "dimensions": {
                    "AgentId": self.agent_id,
                    "AgentType": self.agent_type
                },
                "timestamp": datetime.utcnow()
            })
    
    async def record_custom_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "None",
        dimensions: Optional[Dict[str, str]] = None
    ):
        """
        Record a custom metric.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Metric unit
            dimensions: Additional dimensions
        """
        base_dimensions = {
            "AgentId": self.agent_id,
            "AgentType": self.agent_type
        }
        
        if dimensions:
            base_dimensions.update(dimensions)
        
        metric = {
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "dimensions": base_dimensions,
            "timestamp": datetime.utcnow()
        }
        
        await self._buffer_metric(metric)
    
    async def _buffer_metric(self, metric: Dict[str, Any]):
        """Buffer metric for batch sending."""
        self.metrics_buffer.append(metric)
        
        # Flush if buffer is full
        if len(self.metrics_buffer) >= self.max_buffer_size:
            await self.flush_metrics()
    
    async def flush_metrics(self):
        """Flush buffered metrics to CloudWatch."""
        if not self.metrics_buffer:
            return
        
        if not self.enable_cloudwatch:
            # Just clear buffer if CloudWatch is disabled
            logger.debug(
                f"Flushing {len(self.metrics_buffer)} metrics (CloudWatch disabled)"
            )
            self.metrics_buffer.clear()
            return
        
        client = self._get_cloudwatch_client()
        if not client:
            logger.warning("CloudWatch client not available, clearing buffer")
            self.metrics_buffer.clear()
            return
        
        try:
            # Convert metrics to CloudWatch format
            metric_data = []
            
            for metric in self.metrics_buffer:
                dimensions = [
                    {"Name": k, "Value": v}
                    for k, v in metric["dimensions"].items()
                ]
                
                metric_data.append({
                    "MetricName": metric["metric_name"],
                    "Value": metric["value"],
                    "Unit": metric["unit"],
                    "Timestamp": metric["timestamp"],
                    "Dimensions": dimensions
                })
            
            # Send to CloudWatch in batches of 20 (CloudWatch limit)
            batch_size = 20
            for i in range(0, len(metric_data), batch_size):
                batch = metric_data[i:i + batch_size]
                
                client.put_metric_data(
                    Namespace=self.cloudwatch_namespace,
                    MetricData=batch
                )
            
            logger.info(
                f"Flushed {len(self.metrics_buffer)} metrics to CloudWatch "
                f"for {self.agent_id}"
            )
            
            # Clear buffer after successful send
            self.metrics_buffer.clear()
            
        except Exception as e:
            logger.error(f"Failed to flush metrics to CloudWatch: {e}")
            # Keep metrics in buffer for retry
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics."""
        avg_latency = (
            self.total_latency_ms / self.request_count
            if self.request_count > 0
            else 0.0
        )
        
        error_rate = (
            (self.error_count / self.request_count * 100)
            if self.request_count > 0
            else 0.0
        )
        
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate_percent": error_rate,
            "average_latency_ms": avg_latency,
            "buffered_metrics": len(self.metrics_buffer),
            "cloudwatch_enabled": self.enable_cloudwatch
        }
    
    async def close(self):
        """Flush remaining metrics and cleanup."""
        await self.flush_metrics()
        logger.info(f"Metrics collector closed for {self.agent_id}")


def track_request(metrics_collector: AgentMetricsCollector, endpoint: str):
    """
    Decorator to track request metrics.
    
    Usage:
        @track_request(metrics_collector, "/api/endpoint")
        async def my_endpoint():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 200
            error = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status_code = 500
                error = e
                raise
            finally:
                latency_ms = (time.time() - start_time) * 1000
                
                await metrics_collector.record_request(
                    endpoint=endpoint,
                    status_code=status_code,
                    latency_ms=latency_ms
                )
                
                if error:
                    await metrics_collector.record_error(
                        error_type=type(error).__name__,
                        error_message=str(error),
                        endpoint=endpoint
                    )
        
        return wrapper
    return decorator
