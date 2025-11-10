# HappyOS Agent Shared Utilities

This module provides shared utilities for integrating HappyOS agents with the self-building system.

## Components

### 1. Self-Building Agent Discovery (`self_building_discovery.py`)

Enables agents to discover and communicate with the self-building agent.

**Features:**
- Automatic discovery of self-building agent from agent registry
- Health checking of self-building agent
- MCP tool invocation (trigger_improvement_cycle, query_telemetry_insights, get_system_status)
- Connection management

**Usage:**
```python
from shared.self_building_discovery import SelfBuildingAgentDiscovery

# Initialize
discovery = SelfBuildingAgentDiscovery(
    agent_id="my_agent",
    agent_registry_url="http://localhost:8000"
)

# Discover self-building agent
await discovery.discover_self_building_agent()

# Trigger improvement cycle
result = await discovery.trigger_improvement_cycle(
    analysis_window_hours=24,
    max_improvements=3,
    tenant_id="tenant_123"
)

# Query telemetry insights
insights = await discovery.query_telemetry_insights(
    metric_name="RequestLatency",
    time_range_hours=1
)
```

### 2. Agent Metrics Collector (`metrics_collector.py`)

Collects and sends agent-specific metrics to CloudWatch.

**Features:**
- Request tracking (latency, status codes, error rates)
- Error tracking with categorization
- Resource usage monitoring (CPU, memory, connections)
- Custom metric support
- Automatic batching and flushing to CloudWatch
- Local buffering when CloudWatch unavailable

**Usage:**
```python
from shared.metrics_collector import AgentMetricsCollector, track_request

# Initialize
metrics = AgentMetricsCollector(
    agent_id="my_agent",
    agent_type="my_agent_type",
    cloudwatch_namespace="HappyOS/Agents",
    enable_cloudwatch=True
)

# Record request
await metrics.record_request(
    endpoint="/api/endpoint",
    method="POST",
    status_code=200,
    latency_ms=150.5,
    tenant_id="tenant_123"
)

# Record error
await metrics.record_error(
    error_type="ValidationError",
    error_message="Invalid input",
    endpoint="/api/endpoint"
)

# Record resource usage
await metrics.record_resource_usage(
    cpu_percent=45.2,
    memory_mb=512.0,
    active_connections=10
)

# Get summary
summary = metrics.get_summary()

# Flush metrics to CloudWatch
await metrics.flush_metrics()
```

**Decorator Usage:**
```python
@track_request(metrics_collector, "/api/my-endpoint")
async def my_endpoint():
    # Automatically tracks latency and errors
    return {"status": "ok"}
```

### 3. Improvement Coordinator (`improvement_coordinator.py`)

Coordinates improvement deployments with agent availability and traffic patterns.

**Features:**
- Deployment scheduling during low-traffic windows
- Deployment readiness checking
- Improvement request management
- Deployment monitoring
- Traffic pattern analysis

**Usage:**
```python
from shared.improvement_coordinator import ImprovementCoordinator

# Initialize
coordinator = ImprovementCoordinator(
    agent_id="my_agent",
    self_building_discovery=discovery,
    metrics_collector=metrics
)

# Schedule improvement deployment
result = await coordinator.schedule_improvement_deployment(
    improvement_id="imp_123",
    deployment_window_hours=24,
    prefer_low_traffic=True,
    tenant_id="tenant_123"
)

# Check deployment readiness
readiness = await coordinator.check_deployment_readiness()

# Request improvement deployment
result = await coordinator.request_improvement_deployment(
    improvement_type="performance",
    target_components=["api_handler", "database_client"],
    priority="high"
)

# Monitor deployment
monitoring_result = await coordinator.monitor_deployment(
    improvement_id="imp_123",
    monitoring_duration_seconds=300
)
```

### 4. Improvement Notifier (`improvement_notifier.py`)

Manages improvement deployment notifications across agents.

**Features:**
- Broadcasting improvements to dependent agents
- Receiving and processing notifications
- Notification history tracking
- Handler registration for custom processing
- Breaking change alerts
- Migration guide distribution

**Usage:**
```python
from shared.improvement_notifier import ImprovementNotifier

# Initialize
notifier = ImprovementNotifier(
    agent_id="my_agent",
    self_building_discovery=discovery
)

# Register dependent agents
notifier.register_dependent_agent("agent_svea")
notifier.register_dependent_agent("felicias_finance")

# Register notification handler
async def handle_notification(notification):
    print(f"Received: {notification.improvement_id}")
    if notification.breaking_changes:
        print("WARNING: Breaking changes!")

notifier.register_notification_handler(handle_notification)

# Broadcast improvement
result = await notifier.broadcast_improvement(
    improvement_id="imp_123",
    improvement_type="performance",
    affected_components=["api_handler"],
    change_summary="Optimized request handling",
    migration_guide="No migration required",
    breaking_changes=False
)

# Receive notification
await notifier.receive_notification(notification_data)

# Get notification history
received = notifier.get_received_notifications(limit=10)
sent = notifier.get_sent_notifications(limit=10)
```

## Integration Example

Complete integration example for a new agent:

```python
import os
from shared import (
    SelfBuildingAgentDiscovery,
    AgentMetricsCollector,
    ImprovementCoordinator,
    ImprovementNotifier
)

# Initialize all components
discovery = SelfBuildingAgentDiscovery(
    agent_id="my_agent",
    agent_registry_url=os.getenv("AGENT_REGISTRY_URL", "http://localhost:8000")
)

metrics = AgentMetricsCollector(
    agent_id="my_agent",
    agent_type="my_agent_type",
    enable_cloudwatch=os.getenv("ENABLE_CLOUDWATCH_METRICS", "true").lower() == "true"
)

coordinator = ImprovementCoordinator(
    agent_id="my_agent",
    self_building_discovery=discovery,
    metrics_collector=metrics
)

notifier = ImprovementNotifier(
    agent_id="my_agent",
    self_building_discovery=discovery
)

# Discover self-building agent on startup
async def startup():
    await discovery.discover_self_building_agent()

# Cleanup on shutdown
async def shutdown():
    await metrics.close()
    await discovery.close()
```

## Environment Variables

- `AGENT_REGISTRY_URL`: URL of the agent registry service (default: `http://localhost:8000`)
- `ENABLE_CLOUDWATCH_METRICS`: Enable CloudWatch metrics collection (default: `true`)

## CloudWatch Metrics

All agents send metrics to CloudWatch namespace `HappyOS/Agents` with dimensions:
- `AgentId`: Unique agent identifier
- `AgentType`: Type of agent
- `Endpoint`: API endpoint (for request metrics)
- `TenantId`: Tenant identifier (when applicable)

**Standard Metrics:**
- `RequestCount`: Number of requests
- `RequestLatency`: Request latency in milliseconds
- `ErrorCount`: Number of errors
- `CPUUtilization`: CPU usage percentage
- `MemoryUtilization`: Memory usage in MB
- `ActiveConnections`: Number of active connections

## Requirements

- Python 3.8+
- `httpx` for HTTP client
- `boto3` for CloudWatch integration (optional)
- `asyncio` for async operations

## Testing

Each module includes comprehensive error handling and logging. Test by:

1. Running agent with self-building integration enabled
2. Checking logs for discovery and initialization messages
3. Verifying metrics in CloudWatch console
4. Testing improvement coordination endpoints
5. Monitoring notification broadcasts

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HappyOS Agent                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Agent Application                                      │ │
│  │  - Business Logic                                       │ │
│  │  - API Endpoints                                        │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│  ┌────────────────┴───────────────────────────────────────┐ │
│  │  Self-Building Integration Layer                       │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │  Discovery   │  │   Metrics    │  │ Coordinator  │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  │  ┌──────────────┐                                      │ │
│  │  │  Notifier    │                                      │ │
│  │  └──────────────┘                                      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Self-Building Agent                             │
│  - Telemetry Analysis                                        │
│  - Code Generation                                           │
│  - Improvement Deployment                                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              CloudWatch                                      │
│  - Metrics Storage                                           │
│  - Log Aggregation                                           │
│  - Alarm Management                                          │
└─────────────────────────────────────────────────────────────┘
```

## Support

For issues or questions, contact the HappyOS development team.
