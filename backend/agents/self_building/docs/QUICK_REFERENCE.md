# Self-Building Agent Quick Reference

## Essential Commands

### Health Check
```bash
curl http://localhost:8004/health
```

### Get System Status
```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}'
```

### Trigger Improvement Cycle
```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{
      "name":"trigger_improvement_cycle",
      "arguments":{
        "analysis_window_hours":24,
        "max_improvements":3
      }
    },
    "id":1
  }'
```

### Query Telemetry Insights
```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
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

## Configuration Quick Reference

### Environment Variables
```bash
# Server
SELF_BUILDING_MCP_PORT=8004
SELF_BUILDING_MCP_API_KEY=<secret>

# CloudWatch
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
ENABLE_AUTONOMOUS_IMPROVEMENTS=false
ENABLE_COMPONENT_GENERATION=true
ENABLE_IMPROVEMENT_ROLLBACK=true
```

## Common Operations

### Start Service
```bash
cd backend
python -m agents.self_building.self_building_mcp_server
```

### View Logs
```bash
tail -f backend/logs/self_building_mcp_server.log
```

### Check Metrics
```bash
aws cloudwatch get-metric-statistics \
  --namespace SelfBuilding \
  --metric-name improvements_deployed \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### Emergency Disable
```bash
python backend/scripts/emergency_disable.py --all
```

## Troubleshooting Quick Fixes

### Authentication Error
```bash
# Verify API key
echo $SELF_BUILDING_MCP_API_KEY

# Test with correct header
curl -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  http://localhost:8004/health
```

### Circuit Breaker Open
```bash
# Check status
curl http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}' \
  | jq '.result.components.cloudwatch_streamer.circuit_breaker_state'

# Reset circuit breaker
python backend/scripts/reset_circuit_breaker.py --service cloudwatch
```

### High Rollback Rate
```bash
# Analyze rollbacks
python backend/scripts/analyze_rollbacks.py --days 7

# Adjust threshold
# Edit .env:
ROLLBACK_DEGRADATION_THRESHOLD=0.15
```

## Key Metrics

| Metric | Description | Good Value |
|--------|-------------|------------|
| `improvements_deployed` | Successful deployments | >0 per day |
| `improvements_rolled_back` | Rollbacks | <20% of deployed |
| `cycle_duration_seconds` | Cycle execution time | 60-180s |
| `impact_score_total` | Total impact | Increasing trend |
| `circuit_breaker_opens` | Circuit breaker opens | <5 per day |

## Important Files

| File | Purpose |
|------|---------|
| `backend/logs/self_building_mcp_server.log` | Main service logs |
| `backend/logs/improvement_cycle.log` | Cycle execution logs |
| `backend/logs/cloudwatch_streamer.log` | CloudWatch integration logs |
| `.env` | Configuration |
| `backend/core/settings.py` | Feature flags |

## Support

- **Docs**: `backend/agents/self_building/docs/`
- **Slack**: #happyos-self-building
- **Email**: platform-team@happyos.com
- **On-Call**: PagerDuty
