"""
CloudWatch monitoring with custom metrics and tenant-specific dashboards.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    # Mock boto3 for when AWS SDK is not available
    class MockCloudWatchClient:
        def put_metric_data(self, **kwargs): pass
        def create_dashboard(self, **kwargs): pass
        def put_dashboard(self, **kwargs): pass
        def describe_alarms(self, **kwargs): return {"MetricAlarms": []}
        def put_metric_alarm(self, **kwargs): pass
    
    def boto3_client(*args, **kwargs):
        return MockCloudWatchClient()
    
    class ClientError(Exception): pass
    class NoCredentialsError(Exception): pass

try:
    from backend.modules.config.settings import settings
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.modules.config.settings import settings

from backend.services.observability.logger import get_logger


class MetricUnit(Enum):
    """CloudWatch metric units."""
    SECONDS = "Seconds"
    MICROSECONDS = "Microseconds"
    MILLISECONDS = "Milliseconds"
    BYTES = "Bytes"
    KILOBYTES = "Kilobytes"
    MEGABYTES = "Megabytes"
    GIGABYTES = "Gigabytes"
    TERABYTES = "Terabytes"
    BITS = "Bits"
    KILOBITS = "Kilobits"
    MEGABITS = "Megabits"
    GIGABITS = "Gigabits"
    TERABITS = "Terabits"
    PERCENT = "Percent"
    COUNT = "Count"
    COUNT_PER_SECOND = "Count/Second"
    NONE = "None"


@dataclass
class MetricData:
    """Represents a CloudWatch metric data point."""
    
    metric_name: str
    value: Union[float, int]
    unit: MetricUnit = MetricUnit.COUNT
    dimensions: Dict[str, str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = {}
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    def to_cloudwatch_format(self) -> Dict[str, Any]:
        """Convert to CloudWatch API format."""
        metric_data = {
            "MetricName": self.metric_name,
            "Value": float(self.value),
            "Unit": self.unit.value,
            "Timestamp": self.timestamp
        }
        
        if self.dimensions:
            metric_data["Dimensions"] = [
                {"Name": key, "Value": value}
                for key, value in self.dimensions.items()
            ]
        
        return metric_data


class CloudWatchMonitor:
    """CloudWatch monitoring with custom metrics and dashboards."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.namespace = "MeetMind/MCPUIHub"
        self.client = None
        self._metric_buffer: List[MetricData] = []
        self._buffer_size = 20  # CloudWatch allows max 20 metrics per request
        self._setup_client()
    
    def _setup_client(self):
        """Setup CloudWatch client with proper configuration."""
        if not AWS_AVAILABLE:
            self.logger.warning("AWS SDK not available - CloudWatch metrics will be no-op")
            return
        
        try:
            # Use default credential chain (IAM roles, environment variables, etc.)
            self.client = boto3.client(
                'cloudwatch',
                region_name=getattr(settings, 'AWS_REGION', 'us-east-1')
            )
            
            # Test connection
            self.client.describe_alarms(MaxRecords=1)
            self.logger.info("CloudWatch client initialized successfully")
            
        except NoCredentialsError:
            self.logger.warning("AWS credentials not found - CloudWatch metrics disabled")
            self.client = None
        except Exception as e:
            self.logger.error(f"Failed to initialize CloudWatch client: {e}")
            self.client = None
    
    async def put_metric(
        self,
        metric_name: str,
        value: Union[float, int],
        unit: MetricUnit = MetricUnit.COUNT,
        dimensions: Dict[str, str] = None,
        tenant_id: str = None
    ):
        """Put a single metric to CloudWatch."""
        if not self.client:
            return
        
        # Add tenant dimension if provided
        if dimensions is None:
            dimensions = {}
        if tenant_id:
            dimensions["TenantId"] = tenant_id
        
        # Add environment dimension
        dimensions["Environment"] = settings.ENVIRONMENT
        
        metric = MetricData(
            metric_name=metric_name,
            value=value,
            unit=unit,
            dimensions=dimensions
        )
        
        self._metric_buffer.append(metric)
        
        # Flush buffer if full
        if len(self._metric_buffer) >= self._buffer_size:
            await self._flush_metrics()
    
    async def put_metrics_batch(self, metrics: List[MetricData]):
        """Put multiple metrics to CloudWatch in batches."""
        if not self.client:
            return
        
        # Add environment dimension to all metrics
        for metric in metrics:
            if "Environment" not in metric.dimensions:
                metric.dimensions["Environment"] = settings.ENVIRONMENT
        
        self._metric_buffer.extend(metrics)
        
        # Flush in batches
        while len(self._metric_buffer) >= self._buffer_size:
            await self._flush_metrics()
    
    async def _flush_metrics(self):
        """Flush metric buffer to CloudWatch."""
        if not self.client or not self._metric_buffer:
            return
        
        try:
            # Take up to buffer_size metrics
            batch = self._metric_buffer[:self._buffer_size]
            self._metric_buffer = self._metric_buffer[self._buffer_size:]
            
            # Convert to CloudWatch format
            metric_data = [metric.to_cloudwatch_format() for metric in batch]
            
            # Send to CloudWatch
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=metric_data
                )
            )
            
            self.logger.debug(f"Sent {len(batch)} metrics to CloudWatch")
            
        except Exception as e:
            self.logger.error(f"Failed to send metrics to CloudWatch: {e}")
    
    async def flush_all_metrics(self):
        """Flush all remaining metrics in buffer."""
        while self._metric_buffer:
            await self._flush_metrics()
    
    # Resource operation metrics
    async def record_resource_operation(
        self,
        operation: str,  # create, update, delete, get
        tenant_id: str,
        session_id: str,
        agent_id: str,
        duration_ms: float,
        success: bool = True
    ):
        """Record UI resource operation metrics."""
        dimensions = {
            "Operation": operation,
            "TenantId": tenant_id,
            "AgentId": agent_id
        }
        
        # Operation count
        await self.put_metric(
            "ResourceOperations",
            1,
            MetricUnit.COUNT,
            dimensions
        )
        
        # Operation duration
        await self.put_metric(
            "ResourceOperationDuration",
            duration_ms,
            MetricUnit.MILLISECONDS,
            dimensions
        )
        
        # Success/error rate
        status_dimensions = {**dimensions, "Status": "Success" if success else "Error"}
        await self.put_metric(
            "ResourceOperationStatus",
            1,
            MetricUnit.COUNT,
            status_dimensions
        )
    
    async def record_websocket_metrics(
        self,
        tenant_id: str,
        session_id: str,
        event_type: str,  # connect, disconnect, message
        connection_count: int = None,
        message_size_bytes: int = None
    ):
        """Record WebSocket connection and messaging metrics."""
        dimensions = {
            "TenantId": tenant_id,
            "EventType": event_type
        }
        
        # Event count
        await self.put_metric(
            "WebSocketEvents",
            1,
            MetricUnit.COUNT,
            dimensions
        )
        
        # Active connections
        if connection_count is not None:
            await self.put_metric(
                "ActiveWebSocketConnections",
                connection_count,
                MetricUnit.COUNT,
                {"TenantId": tenant_id}
            )
        
        # Message size
        if message_size_bytes is not None:
            await self.put_metric(
                "WebSocketMessageSize",
                message_size_bytes,
                MetricUnit.BYTES,
                dimensions
            )
    
    async def record_tenant_metrics(
        self,
        tenant_id: str,
        active_sessions: int,
        total_resources: int,
        active_agents: int
    ):
        """Record tenant-specific metrics."""
        tenant_dimensions = {"TenantId": tenant_id}
        
        await self.put_metrics_batch([
            MetricData("ActiveSessions", active_sessions, MetricUnit.COUNT, tenant_dimensions),
            MetricData("TotalResources", total_resources, MetricUnit.COUNT, tenant_dimensions),
            MetricData("ActiveAgents", active_agents, MetricUnit.COUNT, tenant_dimensions)
        ])
    
    async def record_performance_metrics(
        self,
        component: str,
        cpu_percent: float,
        memory_bytes: int,
        latency_ms: float = None
    ):
        """Record system performance metrics."""
        dimensions = {"Component": component}
        
        metrics = [
            MetricData("CPUUtilization", cpu_percent, MetricUnit.PERCENT, dimensions),
            MetricData("MemoryUtilization", memory_bytes, MetricUnit.BYTES, dimensions)
        ]
        
        if latency_ms is not None:
            metrics.append(
                MetricData("ResponseLatency", latency_ms, MetricUnit.MILLISECONDS, dimensions)
            )
        
        await self.put_metrics_batch(metrics)
    
    async def record_error_metrics(
        self,
        error_type: str,
        component: str,
        tenant_id: str = None,
        severity: str = "error"  # error, warning, critical
    ):
        """Record error and exception metrics."""
        dimensions = {
            "ErrorType": error_type,
            "Component": component,
            "Severity": severity
        }
        
        if tenant_id:
            dimensions["TenantId"] = tenant_id
        
        await self.put_metric(
            "Errors",
            1,
            MetricUnit.COUNT,
            dimensions
        )
    
    async def create_tenant_dashboard(self, tenant_id: str) -> bool:
        """Create CloudWatch dashboard for specific tenant."""
        if not self.client:
            return False
        
        dashboard_name = f"MeetMind-{tenant_id}-Dashboard"
        
        # Dashboard configuration
        dashboard_body = {
            "widgets": [
                {
                    "type": "metric",
                    "x": 0, "y": 0, "width": 12, "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "ResourceOperations", "TenantId", tenant_id],
                            [self.namespace, "ActiveSessions", "TenantId", tenant_id],
                            [self.namespace, "ActiveAgents", "TenantId", tenant_id]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": getattr(settings, 'AWS_REGION', 'us-east-1'),
                        "title": f"{tenant_id} - Resource Operations"
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 6, "width": 12, "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "ResourceOperationDuration", "TenantId", tenant_id],
                            [self.namespace, "WebSocketMessageSize", "TenantId", tenant_id]
                        ],
                        "period": 300,
                        "stat": "Average",
                        "region": getattr(settings, 'AWS_REGION', 'us-east-1'),
                        "title": f"{tenant_id} - Performance Metrics"
                    }
                },
                {
                    "type": "metric",
                    "x": 0, "y": 12, "width": 12, "height": 6,
                    "properties": {
                        "metrics": [
                            [self.namespace, "Errors", "TenantId", tenant_id, "Severity", "error"],
                            [self.namespace, "Errors", "TenantId", tenant_id, "Severity", "warning"],
                            [self.namespace, "Errors", "TenantId", tenant_id, "Severity", "critical"]
                        ],
                        "period": 300,
                        "stat": "Sum",
                        "region": getattr(settings, 'AWS_REGION', 'us-east-1'),
                        "title": f"{tenant_id} - Error Metrics"
                    }
                }
            ]
        }
        
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.put_dashboard(
                    DashboardName=dashboard_name,
                    DashboardBody=str(dashboard_body).replace("'", '"')
                )
            )
            
            self.logger.info(f"Created CloudWatch dashboard for tenant {tenant_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create dashboard for {tenant_id}: {e}")
            return False
    
    async def create_system_alerts(self) -> bool:
        """Create CloudWatch alarms for system health monitoring."""
        if not self.client:
            return False
        
        alarms = [
            {
                "AlarmName": "MeetMind-HighErrorRate",
                "ComparisonOperator": "GreaterThanThreshold",
                "EvaluationPeriods": 2,
                "MetricName": "Errors",
                "Namespace": self.namespace,
                "Period": 300,
                "Statistic": "Sum",
                "Threshold": 10.0,
                "ActionsEnabled": True,
                "AlarmDescription": "High error rate detected",
                "Unit": "Count"
            },
            {
                "AlarmName": "MeetMind-HighLatency",
                "ComparisonOperator": "GreaterThanThreshold",
                "EvaluationPeriods": 3,
                "MetricName": "ResourceOperationDuration",
                "Namespace": self.namespace,
                "Period": 300,
                "Statistic": "Average",
                "Threshold": 1000.0,  # 1 second
                "ActionsEnabled": True,
                "AlarmDescription": "High response latency detected",
                "Unit": "Milliseconds"
            },
            {
                "AlarmName": "MeetMind-LowResourceOperations",
                "ComparisonOperator": "LessThanThreshold",
                "EvaluationPeriods": 5,
                "MetricName": "ResourceOperations",
                "Namespace": self.namespace,
                "Period": 300,
                "Statistic": "Sum",
                "Threshold": 1.0,
                "ActionsEnabled": True,
                "AlarmDescription": "Very low resource operation activity",
                "Unit": "Count",
                "TreatMissingData": "breaching"
            }
        ]
        
        try:
            for alarm in alarms:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda a=alarm: self.client.put_metric_alarm(**a)
                )
            
            self.logger.info("Created CloudWatch alarms for system monitoring")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create CloudWatch alarms: {e}")
            return False
    
    async def get_tenant_metrics_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get metrics summary for a specific tenant."""
        # This would typically query CloudWatch for recent metrics
        # For now, return a placeholder structure
        return {
            "tenant_id": tenant_id,
            "metrics": {
                "resource_operations_1h": 0,
                "active_sessions": 0,
                "active_agents": 0,
                "avg_latency_ms": 0,
                "error_count_1h": 0
            },
            "status": "healthy",
            "last_updated": datetime.now(timezone.utc).isoformat()
        }


# Global CloudWatch monitor instance
_cloudwatch_monitor: Optional[CloudWatchMonitor] = None


def get_cloudwatch_monitor() -> CloudWatchMonitor:
    """Get or create the global CloudWatch monitor."""
    global _cloudwatch_monitor
    if _cloudwatch_monitor is None:
        _cloudwatch_monitor = CloudWatchMonitor()
    return _cloudwatch_monitor