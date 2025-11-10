# Self-Building Agent MCP API Documentation

## Overview

The Self-Building Agent exposes its capabilities through the Model Context Protocol (MCP), allowing other HappyOS agents to trigger autonomous improvements, generate components, query system status, and access telemetry insights.

**Base URL**: `http://localhost:8004/mcp`  
**Authentication**: Bearer token (MCP_API_KEY)  
**Protocol**: MCP over HTTP with JSON-RPC 2.0

## Authentication

All MCP tool calls require Bearer token authentication:

```http
Authorization: Bearer <MCP_API_KEY>
```

The API key is configured via the `SELF_BUILDING_MCP_API_KEY` environment variable.

### Authentication Error Response

```json
{
  "error": {
    "code": 401,
    "message": "Unauthorized: Invalid or missing API key"
  }
}
```

## MCP Tools

### 1. trigger_improvement_cycle

Initiates an autonomous improvement cycle that analyzes telemetry data, identifies optimization opportunities, generates code improvements, and deploys them with monitoring.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `analysis_window_hours` | integer | No | 24 | Hours of telemetry data to analyze |
| `max_improvements` | integer | No | 3 | Maximum concurrent improvements to deploy |
| `tenant_id` | string | No | null | Scope improvements to specific tenant (null = system-wide) |

#### Request Example

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "trigger_improvement_cycle",
    "arguments": {
      "analysis_window_hours": 24,
      "max_improvements": 3,
      "tenant_id": "meetmind-prod"
    }
  },
  "id": 1
}
```

#### Response Example

```json
{
  "jsonrpc": "2.0",
  "result": {
    "cycle_id": "cycle_20250110_143022",
    "status": "completed",
    "analysis_summary": {
      "telemetry_events_analyzed": 15420,
      "insights_generated": 12,
      "opportunities_identified": 5
    },
    "improvements": [
      {
        "improvement_id": "imp_001",
        "title": "Optimize database query in meeting_service",
        "impact_score": 85.5,
        "status": "deployed",
        "affected_components": ["backend.agents.meetmind.services.meeting_service"],
        "metrics": {
          "baseline_latency_ms": 245,
          "current_latency_ms": 180,
          "improvement_percentage": 26.5
        }
      },
      {
        "improvement_id": "imp_002",
        "title": "Cache frequently accessed user preferences",
        "impact_score": 72.3,
        "status": "monitoring",
        "affected_components": ["backend.modules.auth.authentication"]
      }
    ],
    "execution_time_seconds": 127.5,
    "tenant_id": "meetmind-prod"
  },
  "id": 1
}
```

#### Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 400 | Invalid parameters | Parameters validation failed |
| 403 | Tenant access denied | Requester lacks access to specified tenant |
| 409 | Cycle already running | Another improvement cycle is in progress |
| 500 | Cycle execution failed | Internal error during cycle execution |
| 503 | Service unavailable | Self-building system is disabled or unhealthy |

---

### 2. generate_component

Generates a new system component (skill, agent, service) based on requirements and context. Uses LLM-powered code generation with validation.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `component_type` | string | Yes | - | Type of component: "skill", "agent", "service", "mcp_tool" |
| `requirements` | object | Yes | - | Component requirements and specifications |
| `context` | object | No | {} | Additional context for generation (architecture, patterns, constraints) |

#### Requirements Object Structure

```json
{
  "name": "string",
  "description": "string",
  "capabilities": ["string"],
  "dependencies": ["string"],
  "integration_points": ["string"],
  "quality_requirements": {
    "test_coverage": 0.8,
    "max_complexity": 10,
    "performance_target_ms": 100
  }
}
```

#### Request Example

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "generate_component",
    "arguments": {
      "component_type": "service",
      "requirements": {
        "name": "notification_service",
        "description": "Send notifications via email, SMS, and push",
        "capabilities": [
          "send_email",
          "send_sms",
          "send_push_notification",
          "batch_notifications"
        ],
        "dependencies": ["boto3", "twilio"],
        "integration_points": ["backend.services.agents"],
        "quality_requirements": {
          "test_coverage": 0.85,
          "max_complexity": 8
        }
      },
      "context": {
        "architecture_pattern": "service_facade",
        "use_circuit_breaker": true,
        "tenant_aware": true
      }
    }
  },
  "id": 2
}
```

#### Response Example

```json
{
  "jsonrpc": "2.0",
  "result": {
    "component_id": "comp_notification_service_20250110",
    "status": "generated",
    "files_generated": [
      {
        "path": "backend/services/notification_service.py",
        "lines_of_code": 245,
        "complexity_score": 7.2
      },
      {
        "path": "backend/tests/test_notification_service.py",
        "lines_of_code": 180,
        "test_coverage": 0.87
      }
    ],
    "registration": {
      "registered": true,
      "registry_path": "backend.core.registry.services",
      "component_name": "notification_service"
    },
    "validation": {
      "syntax_valid": true,
      "imports_resolved": true,
      "type_check_passed": true,
      "security_scan_passed": true
    },
    "next_steps": [
      "Review generated code in backend/services/notification_service.py",
      "Configure environment variables for Twilio integration",
      "Run tests: pytest backend/tests/test_notification_service.py",
      "Deploy component using hot reload"
    ]
  },
  "id": 2
}
```

#### Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 400 | Invalid component type | Unsupported component_type value |
| 400 | Missing requirements | Required fields missing in requirements object |
| 422 | Generation failed | LLM generation failed or timed out |
| 422 | Validation failed | Generated code failed validation checks |
| 429 | Rate limit exceeded | Too many generation requests |
| 500 | Internal error | Unexpected error during generation |

---

### 3. get_system_status

Retrieves comprehensive status of the self-building system including component health, active improvements, evolution metrics, and system capabilities.

#### Parameters

None

#### Request Example

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_system_status",
    "arguments": {}
  },
  "id": 3
}
```

#### Response Example

```json
{
  "jsonrpc": "2.0",
  "result": {
    "system_health": "healthy",
    "uptime_seconds": 2847392,
    "evolution_level": 3,
    "components": {
      "sbo1_orchestrator": {
        "status": "active",
        "health": "healthy",
        "registered_components": 47,
        "last_health_check": "2025-01-10T14:30:15Z"
      },
      "sbo2_ultimate": {
        "status": "active",
        "health": "healthy",
        "active_improvements": 2,
        "last_cycle": "2025-01-10T14:00:00Z"
      },
      "learning_engine": {
        "status": "active",
        "health": "healthy",
        "insights_cached": 156,
        "telemetry_buffer_size": 3420
      },
      "cloudwatch_streamer": {
        "status": "active",
        "health": "healthy",
        "streams_active": 3,
        "events_processed_last_hour": 8945
      },
      "llm_code_generator": {
        "status": "active",
        "health": "healthy",
        "circuit_breaker_state": "closed",
        "generations_today": 12
      }
    },
    "active_improvements": [
      {
        "improvement_id": "imp_002",
        "title": "Cache frequently accessed user preferences",
        "status": "monitoring",
        "deployed_at": "2025-01-10T14:15:30Z",
        "monitoring_until": "2025-01-10T15:15:30Z"
      },
      {
        "improvement_id": "imp_003",
        "title": "Optimize JSON serialization in API responses",
        "status": "deploying",
        "started_at": "2025-01-10T14:28:45Z"
      }
    ],
    "metrics": {
      "total_improvements_deployed": 247,
      "improvements_rolled_back": 18,
      "success_rate": 0.927,
      "avg_improvement_impact": 15.3,
      "components_generated": 34,
      "avg_generation_time_seconds": 45.2
    },
    "capabilities": [
      "autonomous_improvement",
      "code_generation",
      "system_optimization",
      "telemetry_analysis",
      "component_generation",
      "self_healing"
    ],
    "feature_flags": {
      "enable_self_building": true,
      "enable_cloudwatch_streaming": true,
      "enable_autonomous_improvements": true,
      "enable_component_generation": true,
      "enable_improvement_rollback": true
    }
  },
  "id": 3
}
```

#### Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 500 | Status retrieval failed | Unable to retrieve system status |
| 503 | Service unavailable | Self-building system is not initialized |

---

### 4. query_telemetry_insights

Queries analyzed telemetry insights from the LearningEngine. Returns performance trends, error patterns, and optimization recommendations based on CloudWatch data.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `metric_name` | string | No | null | Filter by specific metric (null = all metrics) |
| `time_range_hours` | integer | No | 1 | Hours of insights to retrieve |
| `tenant_id` | string | No | null | Filter by tenant (null = all tenants) |

#### Request Example

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "query_telemetry_insights",
    "arguments": {
      "metric_name": "ResponseLatency",
      "time_range_hours": 6,
      "tenant_id": "meetmind-prod"
    }
  },
  "id": 4
}
```

#### Response Example

```json
{
  "jsonrpc": "2.0",
  "result": {
    "query_parameters": {
      "metric_name": "ResponseLatency",
      "time_range_hours": 6,
      "tenant_id": "meetmind-prod"
    },
    "insights": [
      {
        "insight_id": "ins_001",
        "insight_type": "performance_degradation",
        "severity": "high",
        "affected_component": "backend.agents.meetmind.services.meeting_service",
        "affected_tenants": ["meetmind-prod"],
        "metrics": {
          "baseline_latency_ms": 180,
          "current_latency_ms": 245,
          "degradation_percentage": 36.1,
          "affected_requests_per_hour": 1250
        },
        "description": "Response latency increased by 36% in the last 6 hours for meeting_service.get_meeting_summary",
        "recommended_action": "Optimize database query or add caching layer",
        "confidence_score": 0.92,
        "timestamp": "2025-01-10T14:25:00Z"
      },
      {
        "insight_id": "ins_002",
        "insight_type": "optimization_opportunity",
        "severity": "medium",
        "affected_component": "backend.agents.meetmind.services.meeting_service",
        "affected_tenants": ["meetmind-prod"],
        "metrics": {
          "cache_hit_rate": 0.45,
          "potential_cache_hit_rate": 0.85,
          "estimated_latency_reduction_ms": 120
        },
        "description": "Low cache hit rate detected. 85% of queries could be cached",
        "recommended_action": "Implement Redis caching for frequently accessed meeting summaries",
        "confidence_score": 0.88,
        "timestamp": "2025-01-10T14:20:00Z"
      }
    ],
    "summary": {
      "total_insights": 2,
      "by_severity": {
        "critical": 0,
        "high": 1,
        "medium": 1,
        "low": 0
      },
      "by_type": {
        "performance_degradation": 1,
        "error_pattern": 0,
        "optimization_opportunity": 1
      },
      "avg_confidence_score": 0.90
    },
    "recommendations": [
      "Address high-severity performance degradation in meeting_service",
      "Consider implementing caching to improve response times",
      "Monitor ResponseLatency metric for next 2 hours to confirm trend"
    ]
  },
  "id": 4
}
```

#### Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 400 | Invalid time range | time_range_hours must be between 1 and 168 |
| 403 | Tenant access denied | Requester lacks access to specified tenant |
| 404 | Metric not found | Specified metric_name does not exist |
| 500 | Query failed | Error retrieving insights from LearningEngine |

---

## Usage Examples

### Python Client Example

```python
import httpx
import os

class SelfBuildingClient:
    def __init__(self, base_url="http://localhost:8004", api_key=None):
        self.base_url = base_url
        self.api_key = api_key or os.getenv("SELF_BUILDING_MCP_API_KEY")
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
    
    async def trigger_improvement_cycle(
        self,
        analysis_window_hours=24,
        max_improvements=3,
        tenant_id=None
    ):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "trigger_improvement_cycle",
                        "arguments": {
                            "analysis_window_hours": analysis_window_hours,
                            "max_improvements": max_improvements,
                            "tenant_id": tenant_id
                        }
                    },
                    "id": 1
                },
                headers=self.headers
            )
            return response.json()["result"]
    
    async def get_system_status(self):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "get_system_status",
                        "arguments": {}
                    },
                    "id": 2
                },
                headers=self.headers
            )
            return response.json()["result"]

# Usage
client = SelfBuildingClient()
status = await client.get_system_status()
print(f"System health: {status['system_health']}")
print(f"Evolution level: {status['evolution_level']}")
```

### cURL Example

```bash
# Trigger improvement cycle
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "trigger_improvement_cycle",
      "arguments": {
        "analysis_window_hours": 24,
        "max_improvements": 3
      }
    },
    "id": 1
  }'

# Get system status
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_system_status",
      "arguments": {}
    },
    "id": 2
  }'
```

## Rate Limiting

The Self-Building Agent implements rate limiting to prevent resource exhaustion:

- **trigger_improvement_cycle**: 10 requests per hour per tenant
- **generate_component**: 20 requests per hour per tenant
- **get_system_status**: 100 requests per hour per tenant
- **query_telemetry_insights**: 50 requests per hour per tenant

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1704902400
```

## Health Check

The self-building agent exposes a health check endpoint:

```bash
curl http://localhost:8004/health
```

Response:

```json
{
  "status": "healthy",
  "agent": "self-building",
  "version": "1.0.0",
  "uptime_seconds": 2847392,
  "components": {
    "mcp_server": "healthy",
    "sbo1": "healthy",
    "sbo2": "healthy",
    "learning_engine": "healthy",
    "cloudwatch_streamer": "healthy",
    "llm_generator": "healthy"
  }
}
```

## Error Handling Best Practices

1. **Always check for errors** in the JSON-RPC response
2. **Implement exponential backoff** for retries on 429 and 503 errors
3. **Log error details** including error code and message
4. **Handle circuit breaker states** - LLM generation may fail if circuit is open
5. **Validate tenant_id** before making requests to avoid 403 errors

## Security Considerations

- **API Key Rotation**: Rotate `SELF_BUILDING_MCP_API_KEY` regularly
- **Tenant Isolation**: Always specify `tenant_id` for tenant-scoped operations
- **Audit Logging**: All MCP tool calls are logged with requester identity
- **Input Validation**: All parameters are validated before processing
- **Rate Limiting**: Respect rate limits to avoid service degradation

## Support

For issues or questions:
- Check logs: `backend/logs/self_building_mcp_server.log`
- Review metrics: CloudWatch dashboard "SelfBuilding/System"
- Contact: HappyOS Platform Team
