# CloudWatch Integration Guide

## Overview

The Self-Building Agent integrates with AWS CloudWatch to stream real-time telemetry data (metrics, logs, and events) into the LearningEngine for autonomous system optimization. This guide covers setup, configuration, and troubleshooting.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS CloudWatch                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Metrics    │  │     Logs     │  │  Events/Alarms   │  │
│  │  (CW Metrics)│  │ (CW Logs)    │  │  (EventBridge)   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼──────────────────┼───────────────────┼────────────┘
          │                  │                   │
          │ GetMetricStats   │ Logs Insights     │ Event Stream
          │                  │                   │
          ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│         CloudWatchTelemetryStreamer                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Circuit Breaker Protection                          │  │
│  │  - Automatic failover to local metrics               │  │
│  │  - 3 failures → open circuit                         │  │
│  │  - 60 second recovery timeout                        │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Async Streaming                                     │  │
│  │  - stream_metrics()                                  │  │
│  │  - stream_logs()                                     │  │
│  │  - subscribe_to_events()                             │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  LearningEngine                              │
│  - Telemetry ingestion and buffering                        │
│  - Performance trend analysis                               │
│  - Error pattern recognition                                │
│  - Improvement opportunity identification                   │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

### AWS Account Setup

1. **AWS Account** with CloudWatch enabled
2. **IAM User or Role** with appropriate permissions (see IAM Permissions section)
3. **AWS CLI** configured with credentials

### Environment Variables

Add to `.env` or export in shell:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>

# CloudWatch Configuration
CLOUDWATCH_NAMESPACE=MeetMind/MCPUIHub
CLOUDWATCH_METRICS_PERIOD=300
CLOUDWATCH_LOG_GROUP_PATTERN=/aws/lambda/happyos-*
CLOUDWATCH_ALARM_PREFIX=HappyOS

# Streaming Configuration
CLOUDWATCH_STREAM_INTERVAL_SECONDS=60
CLOUDWATCH_LOG_SAMPLING_RATE=1.0
CLOUDWATCH_EVENT_DEDUP_WINDOW_SECONDS=300
```

## IAM Permissions

### Required IAM Policy

Create an IAM policy with the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudWatchMetricsRead",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:GetMetricData",
        "cloudwatch:ListMetrics",
        "cloudwatch:DescribeAlarms",
        "cloudwatch:DescribeAlarmsForMetric"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogsRead",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents",
        "logs:GetLogEvents",
        "logs:StartQuery",
        "logs:GetQueryResults"
      ],
      "Resource": [
        "arn:aws:logs:*:*:log-group:/aws/lambda/happyos-*",
        "arn:aws:logs:*:*:log-group:/aws/lambda/happyos-*:*"
      ]
    },
    {
      "Sid": "EventBridgeRead",
      "Effect": "Allow",
      "Action": [
        "events:DescribeRule",
        "events:ListRules",
        "events:ListTargetsByRule",
        "events:PutRule",
        "events:PutTargets",
        "events:DeleteRule",
        "events:RemoveTargets"
      ],
      "Resource": [
        "arn:aws:events:*:*:rule/happyos-*"
      ]
    }
  ]
}
```

### Attach Policy to IAM User/Role

```bash
# Create policy
aws iam create-policy \
  --policy-name HappyOS-SelfBuilding-CloudWatch \
  --policy-document file://cloudwatch-policy.json

# Attach to user
aws iam attach-user-policy \
  --user-name happyos-self-building \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/HappyOS-SelfBuilding-CloudWatch

# Or attach to role (for EC2/Lambda)
aws iam attach-role-policy \
  --role-name happyos-self-building-role \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/HappyOS-SelfBuilding-CloudWatch
```

## Metric Namespaces and Dimensions

### Standard Metric Namespaces

The self-building agent monitors metrics from these namespaces:

| Namespace | Description | Key Metrics |
|-----------|-------------|-------------|
| `MeetMind/MCPUIHub` | MCP UI Hub metrics | ResourceOperations, ResourceOperationDuration, Errors |
| `AWS/Lambda` | Lambda function metrics | Invocations, Duration, Errors, Throttles |
| `AWS/DynamoDB` | DynamoDB table metrics | ConsumedReadCapacityUnits, ConsumedWriteCapacityUnits, UserErrors |
| `AWS/ElastiCache` | Redis cache metrics | CacheHits, CacheMisses, CPUUtilization, NetworkBytesIn |
| `HappyOS/Agents` | Custom agent metrics | RequestLatency, ErrorRate, CircuitBreakerState |

### Metric Dimensions

Metrics are filtered by these dimensions for multi-tenant analysis:

```python
dimensions = {
    "tenant_id": "meetmind-prod",      # Tenant identifier
    "component": "meeting_service",     # Component name
    "agent_id": "meetmind",            # Agent identifier
    "environment": "production"         # Environment
}
```

### Custom Metrics

Publish custom metrics to CloudWatch:

```python
import boto3
from datetime import datetime

cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_data(
    Namespace='HappyOS/Agents',
    MetricData=[
        {
            'MetricName': 'RequestLatency',
            'Value': 245.5,
            'Unit': 'Milliseconds',
            'Timestamp': datetime.utcnow(),
            'Dimensions': [
                {'Name': 'tenant_id', 'Value': 'meetmind-prod'},
                {'Name': 'component', 'Value': 'meeting_service'},
                {'Name': 'operation', 'Value': 'get_meeting_summary'}
            ]
        }
    ]
)
```

## Log Group Patterns

### Standard Log Groups

The self-building agent streams logs from these log groups:

| Log Group Pattern | Description | Key Fields |
|-------------------|-------------|------------|
| `/aws/lambda/happyos-*` | Lambda function logs | timestamp, message, level, tenant_id |
| `/aws/ecs/happyos-*` | ECS container logs | timestamp, message, container_name, tenant_id |
| `/happyos/agents/*` | Agent-specific logs | timestamp, message, agent_id, tenant_id, severity |
| `/happyos/mcp/*` | MCP communication logs | timestamp, message, source_agent, target_agent |

### Log Event Structure

Logs should be structured JSON for optimal parsing:

```json
{
  "timestamp": "2025-01-10T14:30:15.123Z",
  "level": "ERROR",
  "message": "Database query timeout",
  "tenant_id": "meetmind-prod",
  "component": "meeting_service",
  "operation": "get_meeting_summary",
  "error": {
    "type": "TimeoutError",
    "message": "Query exceeded 5 second timeout",
    "stack_trace": "..."
  },
  "context": {
    "meeting_id": "mtg_12345",
    "user_id": "usr_67890",
    "query_duration_ms": 5234
  }
}
```

### CloudWatch Logs Insights Queries

The streamer uses these queries to extract insights:

```sql
-- Error pattern analysis
fields @timestamp, message, tenant_id, component, error.type
| filter level = "ERROR"
| stats count() by error.type, component
| sort count desc

-- Performance degradation detection
fields @timestamp, component, operation, context.query_duration_ms
| filter context.query_duration_ms > 1000
| stats avg(context.query_duration_ms) as avg_duration by component, operation
| sort avg_duration desc

-- Tenant-specific error rates
fields @timestamp, tenant_id, level
| filter level in ["ERROR", "CRITICAL"]
| stats count() as error_count by tenant_id, bin(5m)
```

## Event Patterns

### CloudWatch Alarms

The self-building agent subscribes to alarm state changes:

```json
{
  "source": ["aws.cloudwatch"],
  "detail-type": ["CloudWatch Alarm State Change"],
  "detail": {
    "alarmName": [{"prefix": "HappyOS-"}],
    "state": {
      "value": ["ALARM"]
    }
  }
}
```

### Lambda Completion Events

Subscribe to Lambda function completions:

```json
{
  "source": ["aws.lambda"],
  "detail-type": ["Lambda Function Execution State Change"],
  "detail": {
    "functionName": [{"prefix": "happyos-"}],
    "status": ["Succeeded", "Failed"]
  }
}
```

### Custom Events

Publish custom events to EventBridge:

```python
import boto3
from datetime import datetime

events = boto3.client('events')

events.put_events(
    Entries=[
        {
            'Time': datetime.utcnow(),
            'Source': 'happyos.self-building',
            'DetailType': 'Improvement Deployed',
            'Detail': json.dumps({
                'improvement_id': 'imp_001',
                'component': 'meeting_service',
                'tenant_id': 'meetmind-prod',
                'impact_score': 85.5
            })
        }
    ]
)
```

## Configuration

### CloudWatchTelemetryStreamer Configuration

```python
from backend.core.self_building.intelligence.cloudwatch_streamer import CloudWatchTelemetryStreamer
from backend.core.self_building.intelligence.learning_engine import LearningEngine

# Initialize components
learning_engine = LearningEngine()
streamer = CloudWatchTelemetryStreamer(learning_engine)

# Configure streaming
await streamer.start_streaming(
    metric_namespaces=['MeetMind/MCPUIHub', 'HappyOS/Agents'],
    log_group_pattern='/aws/lambda/happyos-*',
    event_patterns=[
        {
            'source': ['aws.cloudwatch'],
            'detail-type': ['CloudWatch Alarm State Change']
        }
    ],
    stream_interval_seconds=60,
    log_sampling_rate=1.0
)
```

### Circuit Breaker Configuration

```python
from backend.core.circuit_breaker.circuit_breaker import CircuitBreaker

# CloudWatch circuit breaker
cloudwatch_circuit_breaker = CircuitBreaker(
    failure_threshold=3,        # Open after 3 consecutive failures
    recovery_timeout=60,        # Try recovery after 60 seconds
    expected_exception=(ClientError, NoCredentialsError)
)

# Use with protection
async def get_metrics_with_protection():
    try:
        return await cloudwatch_circuit_breaker.call_with_protection(
            cloudwatch_client.get_metric_statistics,
            Namespace='MeetMind/MCPUIHub',
            MetricName='ResponseLatency',
            StartTime=datetime.now() - timedelta(hours=1),
            EndTime=datetime.now(),
            Period=300,
            Statistics=['Average']
        )
    except CircuitBreakerOpen:
        # Fallback to local metrics
        return await local_metrics_service.get_metrics('ResponseLatency')
```

## Testing with LocalStack

For local development and testing, use LocalStack to simulate CloudWatch:

### Install LocalStack

```bash
pip install localstack localstack-client awscli-local
```

### Start LocalStack

```bash
# Start LocalStack with CloudWatch services
localstack start -d

# Or use Docker Compose
docker-compose up -d localstack
```

### Configure for LocalStack

```bash
# Set LocalStack endpoint
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

### Create Test Metrics

```bash
# Put test metric
awslocal cloudwatch put-metric-data \
  --namespace MeetMind/MCPUIHub \
  --metric-name ResponseLatency \
  --value 245.5 \
  --unit Milliseconds \
  --dimensions tenant_id=test,component=meeting_service

# Create test log group
awslocal logs create-log-group \
  --log-group-name /aws/lambda/happyos-test

# Put test log event
awslocal logs put-log-events \
  --log-group-name /aws/lambda/happyos-test \
  --log-stream-name test-stream \
  --log-events timestamp=$(date +%s000),message='{"level":"ERROR","message":"Test error"}'
```

## Monitoring and Observability

### Streamer Metrics

The CloudWatch streamer publishes its own metrics:

```python
# Metrics published by streamer
metrics = {
    'cloudwatch.api_calls': 'Count of CloudWatch API calls',
    'cloudwatch.api_errors': 'Count of API errors',
    'cloudwatch.circuit_breaker_opens': 'Count of circuit breaker opens',
    'cloudwatch.events_processed': 'Count of events processed',
    'cloudwatch.events_deduplicated': 'Count of duplicate events filtered',
    'cloudwatch.stream_lag_seconds': 'Lag between event time and processing time'
}
```

### Health Checks

Check streamer health:

```python
# Get streamer status
status = await streamer.get_status()

print(f"Streams active: {status['streams_active']}")
print(f"Circuit breaker state: {status['circuit_breaker_state']}")
print(f"Events processed (last hour): {status['events_processed_last_hour']}")
print(f"Last error: {status['last_error']}")
```

### Logging

Streamer logs are written to:

```
backend/logs/cloudwatch_streamer.log
```

Log levels:
- `INFO`: Normal operations (stream start/stop, events processed)
- `WARNING`: Recoverable errors (API throttling, circuit breaker open)
- `ERROR`: Unrecoverable errors (authentication failure, invalid configuration)

## Troubleshooting

### Issue: Authentication Errors

**Symptoms**: `NoCredentialsError` or `InvalidClientTokenId`

**Solutions**:
1. Verify AWS credentials are configured:
   ```bash
   aws sts get-caller-identity
   ```
2. Check environment variables:
   ```bash
   echo $AWS_ACCESS_KEY_ID
   echo $AWS_SECRET_ACCESS_KEY
   ```
3. Verify IAM permissions (see IAM Permissions section)

### Issue: Circuit Breaker Stays Open

**Symptoms**: Streamer falls back to local metrics continuously

**Solutions**:
1. Check CloudWatch service health:
   ```bash
   aws cloudwatch describe-alarms --max-records 1
   ```
2. Verify network connectivity to AWS
3. Check for rate limiting (429 errors in logs)
4. Increase `recovery_timeout` in circuit breaker configuration

### Issue: No Metrics Received

**Symptoms**: `telemetry_buffer_size` stays at 0

**Solutions**:
1. Verify metrics exist in CloudWatch:
   ```bash
   aws cloudwatch list-metrics --namespace MeetMind/MCPUIHub
   ```
2. Check metric namespace and dimensions match configuration
3. Verify time range (metrics older than 15 days are not available)
4. Check `CLOUDWATCH_METRICS_PERIOD` is appropriate (minimum 60 seconds)

### Issue: Log Streaming Slow

**Symptoms**: High `stream_lag_seconds` metric

**Solutions**:
1. Reduce `log_sampling_rate` to sample logs (e.g., 0.5 for 50%)
2. Increase `CLOUDWATCH_STREAM_INTERVAL_SECONDS`
3. Use more specific log group patterns to reduce volume
4. Optimize CloudWatch Logs Insights queries

### Issue: Event Deduplication Not Working

**Symptoms**: Duplicate improvement cycles triggered

**Solutions**:
1. Verify `CLOUDWATCH_EVENT_DEDUP_WINDOW_SECONDS` is set (default: 300)
2. Check event IDs are unique and consistent
3. Review event patterns to ensure they're not too broad
4. Check system clock synchronization (NTP)

### Issue: High AWS Costs

**Symptoms**: Unexpected CloudWatch charges

**Solutions**:
1. Reduce metric resolution (increase `CLOUDWATCH_METRICS_PERIOD`)
2. Implement log sampling (`CLOUDWATCH_LOG_SAMPLING_RATE < 1.0`)
3. Use metric filters instead of streaming all logs
4. Set up CloudWatch Logs retention policies
5. Use CloudWatch Logs Insights queries instead of FilterLogEvents

## Best Practices

1. **Use Structured Logging**: Always log JSON for easier parsing
2. **Add Tenant Dimensions**: Include `tenant_id` in all metrics and logs
3. **Implement Sampling**: Use sampling for high-volume logs
4. **Monitor Circuit Breaker**: Alert when circuit breaker stays open > 5 minutes
5. **Set Retention Policies**: Configure log retention to control costs
6. **Use Metric Filters**: Create metric filters for common patterns
7. **Test with LocalStack**: Always test locally before deploying
8. **Rotate Credentials**: Rotate AWS credentials regularly
9. **Use IAM Roles**: Prefer IAM roles over access keys when possible
10. **Monitor Costs**: Set up billing alerts for CloudWatch usage

## Performance Tuning

### Optimize Metric Streaming

```python
# Batch metric requests
await streamer.stream_metrics(
    namespace='MeetMind/MCPUIHub',
    metric_names=['ResponseLatency', 'ErrorRate', 'RequestCount'],
    period_seconds=300,  # 5-minute aggregation
    batch_size=100       # Request 100 data points at once
)
```

### Optimize Log Streaming

```python
# Use sampling for high-volume logs
await streamer.stream_logs(
    log_group_pattern='/aws/lambda/happyos-*',
    filter_pattern='{ $.level = "ERROR" }',  # Only stream errors
    sampling_rate=0.5,                        # Sample 50% of logs
    max_events_per_batch=1000
)
```

### Optimize Event Subscription

```python
# Use specific event patterns
await streamer.subscribe_to_events(
    event_pattern={
        'source': ['aws.cloudwatch'],
        'detail-type': ['CloudWatch Alarm State Change'],
        'detail': {
            'alarmName': [{'prefix': 'HappyOS-Critical-'}],  # Only critical alarms
            'state': {'value': ['ALARM']}
        }
    }
)
```

## Security Considerations

1. **Least Privilege**: Grant only required CloudWatch permissions
2. **Credential Rotation**: Rotate AWS credentials every 90 days
3. **Audit Logging**: Enable CloudTrail for CloudWatch API calls
4. **Encryption**: Use encryption at rest for CloudWatch Logs
5. **VPC Endpoints**: Use VPC endpoints for CloudWatch in production
6. **Resource Policies**: Use resource policies to restrict log group access

## Support

For issues or questions:
- Check logs: `backend/logs/cloudwatch_streamer.log`
- Review metrics: CloudWatch dashboard "SelfBuilding/CloudWatch"
- AWS Documentation: https://docs.aws.amazon.com/cloudwatch/
- Contact: HappyOS Platform Team
