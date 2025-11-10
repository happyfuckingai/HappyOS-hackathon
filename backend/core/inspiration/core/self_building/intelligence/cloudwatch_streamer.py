"""
CloudWatch Telemetry Streamer for Self-Building System.

Streams CloudWatch metrics, logs, and events into the LearningEngine for analysis.
Uses circuit breaker pattern for resilience with local fallback.
"""

import asyncio
import time
import logging
from typing import AsyncIterator, Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import structlog

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception

from backend.core.circuit_breaker.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from backend.core.settings import get_settings


logger = structlog.get_logger(__name__)


@dataclass
class MetricDataPoint:
    """Represents a CloudWatch metric data point."""
    metric_name: str
    value: float
    unit: str
    dimensions: Dict[str, str]
    timestamp: datetime
    tenant_id: str
    namespace: str


@dataclass
class LogEvent:
    """Represents a CloudWatch log event."""
    log_group: str
    log_stream: str
    message: str
    timestamp: datetime
    fields: Dict[str, Any]
    tenant_id: str
    severity: str


@dataclass
class CloudWatchEvent:
    """Represents a CloudWatch/EventBridge event."""
    event_type: str  # alarm, lambda_completion, custom
    source: str
    detail: Dict[str, Any]
    timestamp: datetime
    tenant_id: str


class CloudWatchTelemetryStreamer:
    """
    Streams CloudWatch telemetry data into the LearningEngine.
    Uses circuit breaker for resilience with local fallback.
    """
    
    def __init__(self, learning_engine=None):
        """
        Initialize CloudWatch telemetry streamer.
        
        Args:
            learning_engine: LearningEngine instance to feed telemetry data
        """
        self.learning_engine = learning_engine
        self.settings = get_settings()
        
        # AWS clients
        self.cloudwatch_client = None
        self.logs_client = None
        self.events_client = None
        
        # Circuit breaker for AWS calls
        self.circuit_breaker = CircuitBreaker(
            service_name="cloudwatch",
            failure_threshold=3,
            timeout_seconds=30,
            half_open_max_calls=2
        )
        
        # Streaming state
        self._streaming_active = False
        self._stream_tasks: List[asyncio.Task] = []
        self._event_deduplication_cache: Dict[str, float] = {}
        self._deduplication_window = 300  # 5 minutes
        
        # Initialize AWS clients
        self._initialize_clients()
        
        logger.info("CloudWatch telemetry streamer initialized")
    
    def _initialize_clients(self):
        """Initialize AWS clients with circuit breaker protection."""
        if not BOTO3_AVAILABLE:
            logger.warning("boto3 not available, CloudWatch streaming will use local fallback only")
            return
        
        try:
            aws_region = getattr(self.settings, 'aws_region', 'us-east-1')
            
            self.cloudwatch_client = boto3.client('cloudwatch', region_name=aws_region)
            self.logs_client = boto3.client('logs', region_name=aws_region)
            self.events_client = boto3.client('events', region_name=aws_region)
            
            logger.info(f"AWS clients initialized for region: {aws_region}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {e}")
            self.cloudwatch_client = None
            self.logs_client = None
            self.events_client = None

    async def stream_metrics(
        self,
        namespace: str = "MeetMind/MCPUIHub",
        metric_names: List[str] = None,
        dimensions: Dict[str, str] = None,
        period_seconds: int = 300
    ) -> AsyncIterator[MetricDataPoint]:
        """
        Stream CloudWatch metrics in real-time.
        
        Args:
            namespace: CloudWatch namespace to query
            metric_names: List of metric names to stream (None for all)
            dimensions: Dimension filters (e.g., {"tenant_id": "tenant1"})
            period_seconds: Metric aggregation period
            
        Yields:
            MetricDataPoint objects as they become available
        """
        if metric_names is None:
            metric_names = [
                "ResourceOperations",
                "ResourceOperationDuration",
                "Errors",
                "CPUUtilization",
                "MemoryUtilization",
                "ResponseLatency"
            ]
        
        logger.info(f"Starting metric streaming for namespace: {namespace}")
        
        while self._streaming_active:
            try:
                # Try CloudWatch with circuit breaker protection
                if self.cloudwatch_client:
                    try:
                        metrics = await self.circuit_breaker.call(
                            self._fetch_cloudwatch_metrics,
                            namespace,
                            metric_names,
                            dimensions,
                            period_seconds
                        )
                        
                        for metric in metrics:
                            yield metric
                            
                    except CircuitBreakerOpenError:
                        logger.warning("CloudWatch circuit breaker open, falling back to local metrics")
                        # Fall back to local metrics
                        async for metric in self._fetch_local_metrics(metric_names, dimensions):
                            yield metric
                else:
                    # No CloudWatch client, use local fallback
                    async for metric in self._fetch_local_metrics(metric_names, dimensions):
                        yield metric
                
                # Wait before next poll
                await asyncio.sleep(period_seconds)
                
            except asyncio.CancelledError:
                logger.info("Metric streaming cancelled")
                break
            except Exception as e:
                logger.error(f"Error in metric streaming: {e}")
                await asyncio.sleep(period_seconds)
    
    def _fetch_cloudwatch_metrics(
        self,
        namespace: str,
        metric_names: List[str],
        dimensions: Dict[str, str],
        period_seconds: int
    ) -> List[MetricDataPoint]:
        """
        Fetch metrics from CloudWatch (sync method for circuit breaker).
        
        Args:
            namespace: CloudWatch namespace
            metric_names: List of metric names
            dimensions: Dimension filters
            period_seconds: Aggregation period
            
        Returns:
            List of MetricDataPoint objects
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(seconds=period_seconds * 2)
        
        metrics = []
        
        # Convert dimensions dict to CloudWatch format
        cw_dimensions = []
        if dimensions:
            for key, value in dimensions.items():
                cw_dimensions.append({'Name': key, 'Value': value})
        
        for metric_name in metric_names:
            try:
                response = self.cloudwatch_client.get_metric_statistics(
                    Namespace=namespace,
                    MetricName=metric_name,
                    Dimensions=cw_dimensions,
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=period_seconds,
                    Statistics=['Average', 'Sum', 'Maximum', 'Minimum']
                )
                
                for datapoint in response.get('Datapoints', []):
                    # Extract tenant_id from dimensions
                    tenant_id = dimensions.get('tenant_id', 'system') if dimensions else 'system'
                    
                    # Create metric data point for each statistic
                    for stat in ['Average', 'Sum', 'Maximum', 'Minimum']:
                        if stat in datapoint:
                            metric = MetricDataPoint(
                                metric_name=f"{metric_name}_{stat}",
                                value=datapoint[stat],
                                unit=datapoint.get('Unit', 'None'),
                                dimensions=dimensions or {},
                                timestamp=datapoint['Timestamp'],
                                tenant_id=tenant_id,
                                namespace=namespace
                            )
                            metrics.append(metric)
                
            except Exception as e:
                logger.error(f"Error fetching metric {metric_name}: {e}")
                continue
        
        logger.debug(f"Fetched {len(metrics)} metric data points from CloudWatch")
        return metrics
    
    async def _fetch_local_metrics(
        self,
        metric_names: List[str],
        dimensions: Dict[str, str]
    ) -> AsyncIterator[MetricDataPoint]:
        """
        Fetch metrics from local fallback storage.
        
        Args:
            metric_names: List of metric names
            dimensions: Dimension filters
            
        Yields:
            MetricDataPoint objects from local storage
        """
        # This is a placeholder for local metric collection
        # In a real implementation, this would read from local metric storage
        logger.debug("Using local metric fallback")
        
        # Generate synthetic metrics for demonstration
        tenant_id = dimensions.get('tenant_id', 'system') if dimensions else 'system'
        
        for metric_name in metric_names:
            metric = MetricDataPoint(
                metric_name=metric_name,
                value=0.0,  # Placeholder value
                unit='Count',
                dimensions=dimensions or {},
                timestamp=datetime.now(),
                tenant_id=tenant_id,
                namespace='Local'
            )
            yield metric
        
        await asyncio.sleep(0.1)  # Prevent tight loop

    async def stream_logs(
        self,
        log_group_pattern: str = "/aws/lambda/happyos-*",
        filter_pattern: str = None,
        start_time: datetime = None
    ) -> AsyncIterator[LogEvent]:
        """
        Stream CloudWatch Logs using Logs Insights.
        
        Args:
            log_group_pattern: Log group pattern to query
            filter_pattern: CloudWatch Logs filter pattern
            start_time: Start time for log query (defaults to 1 hour ago)
            
        Yields:
            LogEvent objects as they become available
        """
        if start_time is None:
            start_time = datetime.now() - timedelta(hours=1)
        
        logger.info(f"Starting log streaming for pattern: {log_group_pattern}")
        
        # Track last query time to avoid duplicate logs
        last_query_time = start_time
        
        while self._streaming_active:
            try:
                # Try CloudWatch Logs with circuit breaker protection
                if self.logs_client:
                    try:
                        logs = await self.circuit_breaker.call(
                            self._fetch_cloudwatch_logs,
                            log_group_pattern,
                            filter_pattern,
                            last_query_time
                        )
                        
                        for log in logs:
                            # Apply sampling for high-volume logs
                            if self._should_sample_log(log):
                                yield log
                                last_query_time = max(last_query_time, log.timestamp)
                        
                    except CircuitBreakerOpenError:
                        logger.warning("CloudWatch Logs circuit breaker open, falling back to local logs")
                        # Fall back to local logs
                        async for log in self._fetch_local_logs(filter_pattern):
                            yield log
                else:
                    # No CloudWatch Logs client, use local fallback
                    async for log in self._fetch_local_logs(filter_pattern):
                        yield log
                
                # Wait before next poll
                await asyncio.sleep(60)  # Poll every minute
                
            except asyncio.CancelledError:
                logger.info("Log streaming cancelled")
                break
            except Exception as e:
                logger.error(f"Error in log streaming: {e}")
                await asyncio.sleep(60)
    
    def _fetch_cloudwatch_logs(
        self,
        log_group_pattern: str,
        filter_pattern: str,
        start_time: datetime
    ) -> List[LogEvent]:
        """
        Fetch logs from CloudWatch Logs (sync method for circuit breaker).
        
        Args:
            log_group_pattern: Log group pattern
            filter_pattern: Filter pattern
            start_time: Start time for query
            
        Returns:
            List of LogEvent objects
        """
        logs = []
        
        try:
            # Get log groups matching pattern
            log_groups_response = self.logs_client.describe_log_groups(
                logGroupNamePrefix=log_group_pattern.replace('*', '')
            )
            
            log_groups = [lg['logGroupName'] for lg in log_groups_response.get('logGroups', [])]
            
            if not log_groups:
                logger.debug(f"No log groups found matching pattern: {log_group_pattern}")
                return logs
            
            # Query each log group
            for log_group in log_groups[:5]:  # Limit to 5 log groups to avoid rate limits
                try:
                    # Use filter_log_events for streaming
                    kwargs = {
                        'logGroupName': log_group,
                        'startTime': int(start_time.timestamp() * 1000),
                        'endTime': int(datetime.now().timestamp() * 1000),
                        'limit': 100  # Limit results per group
                    }
                    
                    if filter_pattern:
                        kwargs['filterPattern'] = filter_pattern
                    
                    response = self.logs_client.filter_log_events(**kwargs)
                    
                    for event in response.get('events', []):
                        # Parse log event
                        log_event = self._parse_log_event(log_group, event)
                        if log_event:
                            logs.append(log_event)
                    
                except Exception as e:
                    logger.error(f"Error querying log group {log_group}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error fetching CloudWatch logs: {e}")
        
        logger.debug(f"Fetched {len(logs)} log events from CloudWatch Logs")
        return logs
    
    def _parse_log_event(self, log_group: str, event: Dict[str, Any]) -> Optional[LogEvent]:
        """
        Parse a CloudWatch log event into a LogEvent object.
        
        Args:
            log_group: Log group name
            event: Raw CloudWatch log event
            
        Returns:
            LogEvent object or None if parsing fails
        """
        try:
            message = event.get('message', '')
            timestamp = datetime.fromtimestamp(event.get('timestamp', 0) / 1000)
            
            # Extract fields from message (simple JSON parsing)
            fields = {}
            tenant_id = 'system'
            severity = 'INFO'
            
            # Try to parse JSON log messages
            if message.strip().startswith('{'):
                try:
                    import json
                    fields = json.loads(message)
                    tenant_id = fields.get('tenant_id', 'system')
                    severity = fields.get('level', fields.get('severity', 'INFO'))
                except:
                    pass
            else:
                # Extract severity from message
                if 'ERROR' in message.upper():
                    severity = 'ERROR'
                elif 'WARN' in message.upper():
                    severity = 'WARNING'
                elif 'DEBUG' in message.upper():
                    severity = 'DEBUG'
            
            return LogEvent(
                log_group=log_group,
                log_stream=event.get('logStreamName', ''),
                message=message,
                timestamp=timestamp,
                fields=fields,
                tenant_id=tenant_id,
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Error parsing log event: {e}")
            return None
    
    def _should_sample_log(self, log: LogEvent) -> bool:
        """
        Determine if a log should be sampled (for high-volume logs).
        
        Args:
            log: LogEvent to check
            
        Returns:
            True if log should be included, False to skip
        """
        # Always include ERROR and WARNING logs
        if log.severity in ['ERROR', 'WARNING']:
            return True
        
        # Sample INFO and DEBUG logs (keep 10%)
        import random
        return random.random() < 0.1
    
    async def _fetch_local_logs(
        self,
        filter_pattern: str
    ) -> AsyncIterator[LogEvent]:
        """
        Fetch logs from local fallback storage.
        
        Args:
            filter_pattern: Filter pattern for logs
            
        Yields:
            LogEvent objects from local storage
        """
        # This is a placeholder for local log collection
        logger.debug("Using local log fallback")
        
        # In a real implementation, this would read from local log files
        # For now, yield empty to prevent blocking
        await asyncio.sleep(0.1)
        return
        yield  # Make this a generator

    async def subscribe_to_events(
        self,
        event_pattern: Dict[str, Any] = None
    ) -> AsyncIterator[CloudWatchEvent]:
        """
        Subscribe to CloudWatch Events via EventBridge.
        
        Args:
            event_pattern: EventBridge event pattern to filter events
                          (e.g., {"source": ["aws.cloudwatch"], "detail-type": ["CloudWatch Alarm State Change"]})
            
        Yields:
            CloudWatchEvent objects as they arrive
        """
        if event_pattern is None:
            # Default pattern: CloudWatch alarms and Lambda completions
            event_pattern = {
                "source": ["aws.cloudwatch", "aws.lambda"],
                "detail-type": [
                    "CloudWatch Alarm State Change",
                    "Lambda Function Execution State Change"
                ]
            }
        
        logger.info(f"Starting event subscription with pattern: {event_pattern}")
        
        while self._streaming_active:
            try:
                # Try EventBridge with circuit breaker protection
                if self.events_client:
                    try:
                        events = await self.circuit_breaker.call(
                            self._fetch_eventbridge_events,
                            event_pattern
                        )
                        
                        for event in events:
                            # Deduplicate events
                            if not self._is_duplicate_event(event):
                                yield event
                                self._mark_event_seen(event)
                        
                    except CircuitBreakerOpenError:
                        logger.warning("EventBridge circuit breaker open, falling back to polling")
                        # Fall back to polling CloudWatch alarms
                        async for event in self._poll_alarm_events():
                            yield event
                else:
                    # No EventBridge client, use polling fallback
                    async for event in self._poll_alarm_events():
                        yield event
                
                # Wait before next poll
                await asyncio.sleep(30)  # Poll every 30 seconds
                
            except asyncio.CancelledError:
                logger.info("Event subscription cancelled")
                break
            except Exception as e:
                logger.error(f"Error in event subscription: {e}")
                await asyncio.sleep(30)
    
    def _fetch_eventbridge_events(
        self,
        event_pattern: Dict[str, Any]
    ) -> List[CloudWatchEvent]:
        """
        Fetch events from EventBridge (sync method for circuit breaker).
        
        Note: EventBridge doesn't have a direct "fetch" API. In production,
        you would set up an EventBridge rule that targets an SQS queue or Lambda,
        and then poll that queue. For this implementation, we'll use alarm polling.
        
        Args:
            event_pattern: Event pattern to match
            
        Returns:
            List of CloudWatchEvent objects
        """
        # EventBridge is event-driven, not poll-based
        # In a real implementation, you would:
        # 1. Create an EventBridge rule with the pattern
        # 2. Target an SQS queue or Lambda function
        # 3. Poll the queue or process Lambda invocations
        
        # For now, fall back to polling alarms
        return []
    
    async def _poll_alarm_events(self) -> AsyncIterator[CloudWatchEvent]:
        """
        Poll CloudWatch alarms for state changes (fallback when EventBridge unavailable).
        
        Yields:
            CloudWatchEvent objects for alarm state changes
        """
        try:
            alarm_states = await self.get_alarm_state()
            
            for alarm_name, state in alarm_states.items():
                # Only yield ALARM state events
                if state == 'ALARM':
                    event = CloudWatchEvent(
                        event_type='alarm',
                        source='aws.cloudwatch',
                        detail={
                            'alarmName': alarm_name,
                            'state': state,
                            'previousState': 'OK'  # We don't track previous state in polling
                        },
                        timestamp=datetime.now(),
                        tenant_id='system'
                    )
                    yield event
        
        except Exception as e:
            logger.error(f"Error polling alarm events: {e}")
    
    def _is_duplicate_event(self, event: CloudWatchEvent) -> bool:
        """
        Check if an event is a duplicate within the deduplication window.
        
        Args:
            event: CloudWatchEvent to check
            
        Returns:
            True if event is a duplicate, False otherwise
        """
        # Create event key for deduplication
        event_key = f"{event.event_type}:{event.source}:{event.detail.get('alarmName', '')}"
        
        current_time = time.time()
        
        # Clean up old entries
        expired_keys = [
            k for k, t in self._event_deduplication_cache.items()
            if current_time - t > self._deduplication_window
        ]
        for k in expired_keys:
            del self._event_deduplication_cache[k]
        
        # Check if event was seen recently
        if event_key in self._event_deduplication_cache:
            last_seen = self._event_deduplication_cache[event_key]
            if current_time - last_seen < self._deduplication_window:
                return True
        
        return False
    
    def _mark_event_seen(self, event: CloudWatchEvent):
        """
        Mark an event as seen for deduplication.
        
        Args:
            event: CloudWatchEvent to mark
        """
        event_key = f"{event.event_type}:{event.source}:{event.detail.get('alarmName', '')}"
        self._event_deduplication_cache[event_key] = time.time()

    async def get_alarm_state(
        self,
        alarm_names: List[str] = None
    ) -> Dict[str, str]:
        """
        Get current state of CloudWatch alarms.
        
        Args:
            alarm_names: List of alarm names to query (None for all)
            
        Returns:
            Dictionary mapping alarm names to states (OK, ALARM, INSUFFICIENT_DATA)
        """
        try:
            # Try CloudWatch with circuit breaker protection
            if self.cloudwatch_client:
                try:
                    alarm_states = await self.circuit_breaker.call(
                        self._fetch_alarm_states,
                        alarm_names
                    )
                    return alarm_states
                    
                except CircuitBreakerOpenError:
                    logger.warning("CloudWatch circuit breaker open for alarm state query")
                    return {}
            else:
                logger.debug("No CloudWatch client available for alarm state query")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting alarm states: {e}")
            return {}
    
    def _fetch_alarm_states(
        self,
        alarm_names: List[str] = None
    ) -> Dict[str, str]:
        """
        Fetch alarm states from CloudWatch (sync method for circuit breaker).
        
        Args:
            alarm_names: List of alarm names to query
            
        Returns:
            Dictionary mapping alarm names to states
        """
        alarm_states = {}
        
        try:
            kwargs = {}
            if alarm_names:
                kwargs['AlarmNames'] = alarm_names
            
            # Use paginator for large result sets
            paginator = self.cloudwatch_client.get_paginator('describe_alarms')
            
            for page in paginator.paginate(**kwargs):
                for alarm in page.get('MetricAlarms', []):
                    alarm_name = alarm['AlarmName']
                    state = alarm['StateValue']
                    alarm_states[alarm_name] = state
                
                # Also check composite alarms
                for alarm in page.get('CompositeAlarms', []):
                    alarm_name = alarm['AlarmName']
                    state = alarm['StateValue']
                    alarm_states[alarm_name] = state
            
            logger.debug(f"Fetched states for {len(alarm_states)} alarms")
            
        except Exception as e:
            logger.error(f"Error fetching alarm states: {e}")
        
        return alarm_states

    async def start_streaming(
        self,
        namespace: str = "MeetMind/MCPUIHub",
        log_group_pattern: str = "/aws/lambda/happyos-*",
        event_pattern: Dict[str, Any] = None
    ):
        """
        Start all telemetry streams and feed into LearningEngine.
        
        Args:
            namespace: CloudWatch namespace for metrics
            log_group_pattern: Log group pattern for logs
            event_pattern: EventBridge event pattern for events
        """
        if self._streaming_active:
            logger.warning("Streaming already active")
            return
        
        self._streaming_active = True
        logger.info("Starting CloudWatch telemetry streaming")
        
        # Start metric streaming task
        metrics_task = asyncio.create_task(
            self._stream_metrics_to_learning_engine(namespace)
        )
        self._stream_tasks.append(metrics_task)
        
        # Start log streaming task
        logs_task = asyncio.create_task(
            self._stream_logs_to_learning_engine(log_group_pattern)
        )
        self._stream_tasks.append(logs_task)
        
        # Start event streaming task
        events_task = asyncio.create_task(
            self._stream_events_to_learning_engine(event_pattern)
        )
        self._stream_tasks.append(events_task)
        
        logger.info(f"Started {len(self._stream_tasks)} streaming tasks")
    
    async def _stream_metrics_to_learning_engine(self, namespace: str):
        """
        Stream metrics and feed them into LearningEngine.
        
        Args:
            namespace: CloudWatch namespace
        """
        try:
            async for metric in self.stream_metrics(namespace=namespace):
                if self.learning_engine:
                    try:
                        await self.learning_engine.ingest_telemetry(
                            telemetry_data={
                                'metric_name': metric.metric_name,
                                'value': metric.value,
                                'unit': metric.unit,
                                'dimensions': metric.dimensions,
                                'timestamp': metric.timestamp.isoformat(),
                                'tenant_id': metric.tenant_id,
                                'namespace': metric.namespace
                            },
                            source='metrics'
                        )
                    except Exception as e:
                        logger.error(f"Error ingesting metric into LearningEngine: {e}")
                
        except asyncio.CancelledError:
            logger.info("Metric streaming task cancelled")
        except Exception as e:
            logger.error(f"Error in metric streaming task: {e}")
            # Attempt reconnection after delay
            if self._streaming_active:
                await asyncio.sleep(60)
                if self._streaming_active:
                    logger.info("Attempting to reconnect metric streaming")
                    await self._stream_metrics_to_learning_engine(namespace)
    
    async def _stream_logs_to_learning_engine(self, log_group_pattern: str):
        """
        Stream logs and feed them into LearningEngine.
        
        Args:
            log_group_pattern: Log group pattern
        """
        try:
            async for log in self.stream_logs(log_group_pattern=log_group_pattern):
                if self.learning_engine:
                    try:
                        await self.learning_engine.ingest_telemetry(
                            telemetry_data={
                                'log_group': log.log_group,
                                'log_stream': log.log_stream,
                                'message': log.message,
                                'timestamp': log.timestamp.isoformat(),
                                'fields': log.fields,
                                'tenant_id': log.tenant_id,
                                'severity': log.severity
                            },
                            source='logs'
                        )
                    except Exception as e:
                        logger.error(f"Error ingesting log into LearningEngine: {e}")
                
        except asyncio.CancelledError:
            logger.info("Log streaming task cancelled")
        except Exception as e:
            logger.error(f"Error in log streaming task: {e}")
            # Attempt reconnection after delay
            if self._streaming_active:
                await asyncio.sleep(60)
                if self._streaming_active:
                    logger.info("Attempting to reconnect log streaming")
                    await self._stream_logs_to_learning_engine(log_group_pattern)
    
    async def _stream_events_to_learning_engine(self, event_pattern: Dict[str, Any]):
        """
        Stream events and feed them into LearningEngine.
        
        Args:
            event_pattern: EventBridge event pattern
        """
        try:
            async for event in self.subscribe_to_events(event_pattern=event_pattern):
                if self.learning_engine:
                    try:
                        await self.learning_engine.ingest_telemetry(
                            telemetry_data={
                                'event_type': event.event_type,
                                'source': event.source,
                                'detail': event.detail,
                                'timestamp': event.timestamp.isoformat(),
                                'tenant_id': event.tenant_id
                            },
                            source='events'
                        )
                    except Exception as e:
                        logger.error(f"Error ingesting event into LearningEngine: {e}")
                
        except asyncio.CancelledError:
            logger.info("Event streaming task cancelled")
        except Exception as e:
            logger.error(f"Error in event streaming task: {e}")
            # Attempt reconnection after delay
            if self._streaming_active:
                await asyncio.sleep(60)
                if self._streaming_active:
                    logger.info("Attempting to reconnect event streaming")
                    await self._stream_events_to_learning_engine(event_pattern)
    
    async def stop_streaming(self):
        """
        Stop all telemetry streams gracefully.
        """
        if not self._streaming_active:
            logger.warning("Streaming not active")
            return
        
        logger.info("Stopping CloudWatch telemetry streaming")
        self._streaming_active = False
        
        # Cancel all streaming tasks
        for task in self._stream_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for all tasks to complete
        if self._stream_tasks:
            await asyncio.gather(*self._stream_tasks, return_exceptions=True)
        
        self._stream_tasks.clear()
        
        logger.info("CloudWatch telemetry streaming stopped")
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """
        Get current streaming status.
        
        Returns:
            Dictionary with streaming status information
        """
        return {
            'streaming_active': self._streaming_active,
            'active_tasks': len([t for t in self._stream_tasks if not t.done()]),
            'total_tasks': len(self._stream_tasks),
            'circuit_breaker_state': self.circuit_breaker.get_state().value,
            'cloudwatch_available': self.cloudwatch_client is not None,
            'logs_available': self.logs_client is not None,
            'events_available': self.events_client is not None,
            'deduplication_cache_size': len(self._event_deduplication_cache)
        }
