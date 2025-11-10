# Self-Building Agent Documentation

Welcome to the Self-Building Agent documentation. This agent enables autonomous system optimization through continuous telemetry analysis, code generation, and intelligent deployment.

## Documentation Index

### Getting Started

1. **[MCP API Documentation](MCP_API.md)** - Complete reference for all MCP tools
   - Authentication and authorization
   - Tool parameters and responses
   - Usage examples in Python and cURL
   - Error codes and handling
   - Rate limiting

2. **[CloudWatch Integration Guide](CLOUDWATCH_INTEGRATION.md)** - AWS CloudWatch setup and configuration
   - IAM permissions and setup
   - Metric namespaces and dimensions
   - Log group patterns and queries
   - Event patterns and subscriptions
   - Testing with LocalStack
   - Troubleshooting

3. **[Improvement Cycle Documentation](IMPROVEMENT_CYCLE.md)** - How autonomous improvements work
   - Cycle phases and timing
   - Prioritization algorithm
   - Monitoring and rollback logic
   - Configuration examples
   - Best practices

4. **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Production deployment procedures
   - Phased rollout strategy (7 phases)
   - Feature flag configuration
   - Monitoring setup
   - Rollback procedures
   - Post-deployment validation

5. **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Solutions to common issues
   - Authentication and authorization
   - CloudWatch integration problems
   - LLM code generation issues
   - Improvement cycle problems
   - Performance optimization
   - Deployment troubleshooting
   - Monitoring and alerting
   - Circuit breaker issues

6. **[Quick Reference](QUICK_REFERENCE.md)** - Essential commands and quick fixes
   - Common commands
   - Configuration reference
   - Troubleshooting quick fixes
   - Key metrics
   - Important files

## Quick Start

### Local Development

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your configuration

# 3. Start LocalStack (for testing)
docker-compose up -d localstack

# 4. Start self-building agent
cd backend
python -m agents.self_building.self_building_mcp_server

# 5. Verify health
curl http://localhost:8004/health
```

### First Improvement Cycle

```bash
# Trigger a test improvement cycle
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "trigger_improvement_cycle",
      "arguments": {
        "analysis_window_hours": 1,
        "max_improvements": 1
      }
    },
    "id": 1
  }'
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    HappyOS Agents                            │
│  (MeetMind, Agent Svea, Felicia's Finance)                  │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP Protocol
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Self-Building MCP Server                        │
│  - trigger_improvement_cycle                                 │
│  - generate_component                                        │
│  - get_system_status                                         │
│  - query_telemetry_insights                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  CloudWatch  │  │   Learning   │  │     LLM      │
│   Streamer   │  │    Engine    │  │  Generator   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                │                │
        └────────────────┴────────────────┘
                         │
                         ▼
              Autonomous Improvements
```

## Key Features

### 1. Autonomous Improvement Cycle
- Continuous telemetry analysis
- Automatic opportunity identification
- LLM-powered code generation
- Intelligent deployment with monitoring
- Automatic rollback on degradation

### 2. CloudWatch Integration
- Real-time metric streaming
- Log analysis and pattern recognition
- Event-driven improvement triggers
- Circuit breaker protection with local fallback

### 3. Multi-Tenant Isolation
- Tenant-scoped improvements
- Isolated telemetry analysis
- Configurable per-tenant settings
- System-wide improvement approval flow

### 4. MCP-Based Communication
- Standard protocol for agent communication
- Bearer token authentication
- Rate limiting and security
- Comprehensive error handling

## Configuration

### Environment Variables

```bash
# Self-Building MCP Server
SELF_BUILDING_MCP_PORT=8004
SELF_BUILDING_MCP_API_KEY=<secret>

# CloudWatch Integration
AWS_REGION=us-east-1
CLOUDWATCH_NAMESPACE=MeetMind/MCPUIHub
CLOUDWATCH_METRICS_PERIOD=300

# Improvement Cycle
IMPROVEMENT_CYCLE_INTERVAL_HOURS=24
MAX_CONCURRENT_IMPROVEMENTS=3
MONITORING_DURATION_SECONDS=3600
ROLLBACK_DEGRADATION_THRESHOLD=0.10

# Feature Flags
ENABLE_SELF_BUILDING=true
ENABLE_CLOUDWATCH_STREAMING=true
ENABLE_AUTONOMOUS_IMPROVEMENTS=false  # Start disabled
ENABLE_COMPONENT_GENERATION=true
ENABLE_IMPROVEMENT_ROLLBACK=true
```

### Feature Flags

Control system behavior with feature flags:

- `ENABLE_SELF_BUILDING`: Master switch for entire system
- `ENABLE_CLOUDWATCH_STREAMING`: Enable CloudWatch telemetry
- `ENABLE_AUTONOMOUS_IMPROVEMENTS`: Enable automatic improvements
- `ENABLE_COMPONENT_GENERATION`: Enable component generation
- `ENABLE_IMPROVEMENT_ROLLBACK`: Enable automatic rollback

## Monitoring

### CloudWatch Dashboards

- **SelfBuilding/System**: Overall system health and metrics
- **SelfBuilding/ImprovementCycle**: Improvement cycle performance
- **SelfBuilding/CloudWatch**: CloudWatch integration health

### Key Metrics

- `improvement_cycles_started`: Count of cycles initiated
- `improvements_deployed`: Count of successful deployments
- `improvements_rolled_back`: Count of rollbacks
- `cycle_duration_seconds`: Time to complete cycle
- `impact_score_total`: Total impact of improvements

### Alarms

- **HighFailureRate**: Alert when success rate < 70%
- **HighRollbackRate**: Alert when rollback rate > 20%
- **CircuitBreakerOpen**: Alert when circuit breaker stays open
- **LongCycleDuration**: Alert when cycle takes > 5 minutes

## Common Tasks

### Check System Status

```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}'
```

### Query Telemetry Insights

```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{
      "name":"query_telemetry_insights",
      "arguments":{"time_range_hours":6}
    },
    "id":1
  }'
```

### Generate Component

```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{
      "name":"generate_component",
      "arguments":{
        "component_type":"service",
        "requirements":{
          "name":"example_service",
          "description":"Example service",
          "capabilities":["example_capability"]
        }
      }
    },
    "id":1
  }'
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify `SELF_BUILDING_MCP_API_KEY` is set
   - Check Bearer token in request headers

2. **CloudWatch Connection Issues**
   - Verify AWS credentials
   - Check IAM permissions
   - Test with `aws cloudwatch list-metrics`

3. **Circuit Breaker Open**
   - Check CloudWatch service health
   - Review error logs
   - Verify network connectivity

4. **High Rollback Rate**
   - Review improvement quality threshold
   - Check monitoring duration
   - Analyze rollback reasons in logs

### Getting Help

- **Logs**: `backend/logs/self_building_mcp_server.log`
- **Metrics**: CloudWatch dashboard "SelfBuilding/System"
- **Documentation**: This directory
- **Support**: HappyOS Platform Team

## Testing

### Unit Tests

```bash
# Run all self-building tests
pytest backend/tests/test_self_building_*.py -v

# Run specific test suite
pytest backend/tests/test_improvement_cycle_e2e.py -v
```

### Integration Tests

```bash
# Start LocalStack
docker-compose up -d localstack

# Run integration tests
pytest backend/tests/test_cloudwatch_integration.py -v
pytest backend/tests/test_llm_code_generation.py -v
```

### Smoke Tests

```bash
# Run smoke tests against running service
pytest backend/tests/smoke/test_self_building_smoke.py -v
```

## Development

### Project Structure

```
backend/agents/self_building/
├── docs/                          # Documentation (you are here)
│   ├── README.md
│   ├── MCP_API.md
│   ├── CLOUDWATCH_INTEGRATION.md
│   ├── IMPROVEMENT_CYCLE.md
│   └── DEPLOYMENT_GUIDE.md
├── self_building_mcp_server.py    # MCP server implementation
├── registry.py                    # Agent registration
└── __init__.py

backend/core/self_building/
├── intelligence/
│   ├── learning_engine.py         # Telemetry analysis
│   └── cloudwatch_streamer.py     # CloudWatch integration
├── generators/
│   └── llm_code_generator.py      # LLM-powered generation
├── self_building_orchestrator.py  # SBO1 - Core orchestrator
└── ultimate_self_building.py      # SBO2 - Decision making
```

### Contributing

1. Read the design document: `.kiro/specs/self-building-mcp-integration/design.md`
2. Review requirements: `.kiro/specs/self-building-mcp-integration/requirements.md`
3. Check tasks: `.kiro/specs/self-building-mcp-integration/tasks.md`
4. Write tests for new features
5. Update documentation
6. Submit pull request

## Security

### Authentication
- All MCP calls require Bearer token
- API keys stored in AWS Secrets Manager
- Regular key rotation (90 days)

### Authorization
- Tenant-scoped improvements require tenant validation
- System-wide improvements require meta-orchestrator approval
- Component generation requests validated against requester capabilities

### Audit Logging
- All improvement cycles logged
- Code generation requests logged with requester
- Deployment and rollback events logged
- CloudWatch access logged for compliance

## Performance

### Optimization Tips

1. **Reduce CloudWatch API Calls**
   - Increase `CLOUDWATCH_METRICS_PERIOD`
   - Use log sampling for high-volume logs
   - Batch metric requests

2. **Improve Generation Speed**
   - Use lower temperature for faster generation
   - Reduce `max_tokens` for simpler components
   - Cache common patterns

3. **Optimize Monitoring**
   - Adjust `MONITORING_DURATION_SECONDS` based on traffic
   - Use appropriate `ROLLBACK_DEGRADATION_THRESHOLD`
   - Sample metrics instead of full collection

## Roadmap

### Planned Features

- **Canary Deployments**: Deploy to subset of traffic first
- **A/B Testing**: Compare multiple improvement approaches
- **ML Model Integration**: Use trained models for pattern recognition
- **Cross-Agent Learning**: Share insights across agents
- **Predictive Improvements**: Anticipate issues before they occur

## License

Copyright © 2025 HappyOS. All rights reserved.

## Support

For questions or issues:
- **Documentation**: This directory
- **Logs**: `backend/logs/self_building_mcp_server.log`
- **Metrics**: CloudWatch dashboard "SelfBuilding/System"
- **Contact**: HappyOS Platform Team
