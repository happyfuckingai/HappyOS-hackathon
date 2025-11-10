# Self-Building Agent Troubleshooting Guide

## Overview

This guide provides solutions to common issues encountered when operating the Self-Building Agent. Issues are organized by category with symptoms, root causes, and step-by-step solutions.

## Table of Contents

1. [Authentication and Authorization](#authentication-and-authorization)
2. [CloudWatch Integration](#cloudwatch-integration)
3. [LLM Code Generation](#llm-code-generation)
4. [Improvement Cycle Issues](#improvement-cycle-issues)
5. [Performance Problems](#performance-problems)
6. [Deployment Issues](#deployment-issues)
7. [Monitoring and Alerting](#monitoring-and-alerting)
8. [Circuit Breaker Issues](#circuit-breaker-issues)

---

## Authentication and Authorization

### Issue: 401 Unauthorized Error

**Symptoms**:
```json
{
  "error": {
    "code": 401,
    "message": "Unauthorized: Invalid or missing API key"
  }
}
```

**Root Causes**:
- Missing or incorrect `SELF_BUILDING_MCP_API_KEY`
- API key not included in request headers
- API key expired or rotated

**Solutions**:

1. Verify API key is set:
```bash
echo $SELF_BUILDING_MCP_API_KEY
```

2. Check environment file:
```bash
grep SELF_BUILDING_MCP_API_KEY .env
```

3. Test with correct header:
```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}'
```

4. Rotate API key if compromised:
```bash
python backend/scripts/rotate_api_key.py --service self-building
```

---

### Issue: 403 Tenant Access Denied

**Symptoms**:
```json
{
  "error": {
    "code": 403,
    "message": "Tenant access denied"
  }
}
```

**Root Causes**:
- Requester lacks access to specified tenant
- Tenant ID doesn't exist
- Tenant configuration missing

**Solutions**:

1. Verify tenant exists:
```bash
python backend/scripts/list_tenants.py
```

2. Check requester permissions:
```bash
python backend/scripts/check_permissions.py \
  --requester <requester_id> \
  --tenant <tenant_id>
```

3. Grant access if needed:
```bash
python backend/scripts/grant_tenant_access.py \
  --requester <requester_id> \
  --tenant <tenant_id>
```

---

## CloudWatch Integration

### Issue: NoCredentialsError

**Symptoms**:
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**Root Causes**:
- AWS credentials not configured
- IAM role not attached (EC2/Lambda)
- Credentials expired

**Solutions**:

1. Verify AWS credentials:
```bash
aws sts get-caller-identity
```

2. Configure credentials:
```bash
aws configure
# Enter: Access Key ID, Secret Access Key, Region
```

3. For EC2/Lambda, verify IAM role:
```bash
aws iam get-role --role-name happyos-self-building-role
```

4. Test CloudWatch access:
```bash
aws cloudwatch list-metrics --namespace MeetMind/MCPUIHub --max-items 1
```

---

### Issue: Circuit Breaker Stays Open

**Symptoms**:
- Logs show "Circuit breaker open, using fallback"
- CloudWatch metrics not updating
- `circuit_breaker_state` = "open" in system status

**Root Causes**:
- CloudWatch service unavailable
- Network connectivity issues
- IAM permission errors
- Rate limiting (429 errors)

**Solutions**:

1. Check CloudWatch service health:
```bash
aws cloudwatch describe-alarms --max-records 1
```

2. Verify network connectivity:
```bash
ping cloudwatch.us-east-1.amazonaws.com
```

3. Check for rate limiting in logs:
```bash
grep "429" backend/logs/cloudwatch_streamer.log
```

4. Increase recovery timeout:
```python
# backend/core/settings.py
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=120  # Increase from 60 to 120 seconds
```

5. Manually close circuit breaker:
```bash
python backend/scripts/reset_circuit_breaker.py --service cloudwatch
```

---

### Issue: No Metrics Received

**Symptoms**:
- `telemetry_buffer_size` stays at 0
- No insights generated
- Empty telemetry queries

**Root Causes**:
- Metrics don't exist in CloudWatch
- Incorrect namespace or dimensions
- Time range too old (>15 days)
- Metric period too short

**Solutions**:

1. Verify metrics exist:
```bash
aws cloudwatch list-metrics --namespace MeetMind/MCPUIHub
```

2. Check metric configuration:
```bash
grep CLOUDWATCH_NAMESPACE .env
grep CLOUDWATCH_METRICS_PERIOD .env
```

3. Test metric query:
```bash
aws cloudwatch get-metric-statistics \
  --namespace MeetMind/MCPUIHub \
  --metric-name ResponseLatency \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

4. Adjust metric period:
```bash
# .env
CLOUDWATCH_METRICS_PERIOD=300  # Minimum 60 seconds
```

---

### Issue: Log Streaming Slow

**Symptoms**:
- High `stream_lag_seconds` metric
- Delayed insight generation
- High memory usage

**Root Causes**:
- High log volume
- Inefficient log queries
- Insufficient sampling

**Solutions**:

1. Enable log sampling:
```bash
# .env
CLOUDWATCH_LOG_SAMPLING_RATE=0.5  # Sample 50% of logs
```

2. Increase stream interval:
```bash
# .env
CLOUDWATCH_STREAM_INTERVAL_SECONDS=120  # Increase from 60
```

3. Use more specific log patterns:
```bash
# .env
CLOUDWATCH_LOG_GROUP_PATTERN=/aws/lambda/happyos-meetmind-*  # More specific
```

4. Optimize CloudWatch Logs Insights query:
```sql
-- Instead of:
fields @timestamp, @message

-- Use:
fields @timestamp, level, component, error.type
| filter level = "ERROR"
| limit 1000
```

---

## LLM Code Generation

### Issue: Generation Timeout

**Symptoms**:
```json
{
  "error": {
    "code": 422,
    "message": "Generation failed: Timeout after 60 seconds"
  }
}
```

**Root Causes**:
- Complex component requirements
- LLM service slow or unavailable
- Network latency
- Token limit too high

**Solutions**:

1. Reduce token limit:
```bash
# .env
LLM_MAX_TOKENS=2000  # Reduce from 4000
```

2. Simplify requirements:
```python
# Reduce complexity in requirements
requirements = {
    "name": "simple_service",
    "description": "Simple service",  # Keep description concise
    "capabilities": ["single_capability"]  # Limit capabilities
}
```

3. Check LLM service health:
```bash
python backend/scripts/test_llm_service.py
```

4. Increase timeout:
```python
# backend/core/self_building/generators/llm_code_generator.py
GENERATION_TIMEOUT_SECONDS=120  # Increase from 60
```

---

### Issue: Code Validation Failed

**Symptoms**:
```json
{
  "error": {
    "code": 422,
    "message": "Validation failed: Syntax error on line 42"
  }
}
```

**Root Causes**:
- LLM generated invalid syntax
- Import resolution failed
- Type checking errors
- Security vulnerabilities detected

**Solutions**:

1. Review validation errors:
```bash
grep "Validation failed" backend/logs/llm_code_generator.log | tail -20
```

2. Adjust generation temperature:
```bash
# .env
LLM_TEMPERATURE=0.05  # Lower temperature for more deterministic code
```

3. Improve prompt engineering:
```python
# Add more specific constraints to prompt
prompt += """
Requirements:
- Use only standard library imports
- Follow PEP 8 style guide
- Include type hints
- No security vulnerabilities
"""
```

4. Retry with different model:
```bash
# .env
LLM_MODEL=anthropic.claude-v3  # Try different model
```

---

### Issue: Circuit Breaker Open for LLM

**Symptoms**:
- All generation requests fail
- Logs show "LLM circuit breaker open"
- `llm_circuit_breaker_state` = "open"

**Root Causes**:
- LLM service unavailable
- Rate limiting
- Authentication errors
- Network issues

**Solutions**:

1. Check LLM service status:
```bash
aws bedrock list-foundation-models --region us-east-1
```

2. Verify LLM credentials:
```bash
python backend/scripts/test_llm_auth.py
```

3. Check for rate limiting:
```bash
grep "RateLimitError" backend/logs/llm_code_generator.log
```

4. Manually reset circuit breaker:
```bash
python backend/scripts/reset_circuit_breaker.py --service llm
```

5. Use fallback provider:
```bash
# .env
LLM_PROVIDER=openai  # Fallback from bedrock to openai
```

---

## Improvement Cycle Issues

### Issue: Cycle Stuck in Progress

**Symptoms**:
- Cycle status remains "in_progress" for hours
- No new improvements deployed
- System status shows active cycle but no activity

**Root Causes**:
- Process crashed during cycle
- Deadlock in async operations
- Resource exhaustion

**Solutions**:

1. Check process status:
```bash
ps aux | grep self_building_mcp_server
```

2. Review logs for errors:
```bash
tail -100 backend/logs/improvement_cycle.log
```

3. Cancel stuck cycle:
```bash
python backend/scripts/cancel_improvement_cycle.py --cycle-id <cycle_id>
```

4. Restart service:
```bash
make restart-service SERVICE=self-building
```

---

### Issue: High Rollback Rate

**Symptoms**:
- >30% of improvements rolled back
- Frequent rollback alerts
- Metrics show degradation after deployments

**Root Causes**:
- Rollback threshold too strict
- Insufficient monitoring duration
- Poor code generation quality
- Incorrect baseline metrics

**Solutions**:

1. Review rollback reasons:
```bash
python backend/scripts/analyze_rollbacks.py --days 7
```

2. Adjust rollback threshold:
```bash
# .env
ROLLBACK_DEGRADATION_THRESHOLD=0.15  # Increase from 0.10 (10% to 15%)
```

3. Increase monitoring duration:
```bash
# .env
MONITORING_DURATION_SECONDS=7200  # Increase from 3600 (1h to 2h)
```

4. Improve generation quality:
```bash
# .env
IMPROVEMENT_QUALITY_THRESHOLD=0.95  # Increase from 0.85
```

5. Review baseline collection:
```bash
python backend/scripts/validate_baseline_metrics.py
```

---

### Issue: No Opportunities Identified

**Symptoms**:
- Cycle completes but finds 0 opportunities
- `opportunities_identified` metric = 0
- Telemetry data exists but no insights

**Root Causes**:
- Thresholds too strict
- Insufficient telemetry data
- Analysis algorithms not tuned
- All opportunities already addressed

**Solutions**:

1. Check telemetry buffer:
```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}' \
  | jq '.result.components.learning_engine.telemetry_buffer_size'
```

2. Review analysis thresholds:
```python
# backend/core/self_building/intelligence/learning_engine.py
PERFORMANCE_DEGRADATION_THRESHOLD=0.15  # Lower from 0.20
ERROR_FREQUENCY_THRESHOLD=5  # Lower from 10
```

3. Increase analysis window:
```bash
# Trigger cycle with longer window
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{
    "jsonrpc":"2.0",
    "method":"tools/call",
    "params":{
      "name":"trigger_improvement_cycle",
      "arguments":{"analysis_window_hours":168}
    },
    "id":1
  }'
```

4. Verify telemetry quality:
```bash
python backend/scripts/validate_telemetry.py --hours 24
```

---

## Performance Problems

### Issue: High Memory Usage

**Symptoms**:
- Memory usage >80%
- OOM (Out of Memory) errors
- Slow response times
- Process killed by OS

**Root Causes**:
- Large telemetry buffer
- Memory leaks
- Too many concurrent improvements
- Insufficient resources

**Solutions**:

1. Check memory usage:
```bash
ps aux | grep self_building_mcp_server | awk '{print $4}'
```

2. Reduce telemetry buffer size:
```python
# backend/core/self_building/intelligence/learning_engine.py
MAX_TELEMETRY_BUFFER_SIZE=5000  # Reduce from 10000
```

3. Limit concurrent improvements:
```bash
# .env
MAX_CONCURRENT_IMPROVEMENTS=1  # Reduce from 3
```

4. Enable log sampling:
```bash
# .env
CLOUDWATCH_LOG_SAMPLING_RATE=0.3  # Sample only 30%
```

5. Increase available memory:
```bash
# For Docker
docker update --memory 4g self-building-agent

# For systemd service
# Edit /etc/systemd/system/self-building.service
MemoryLimit=4G
```

---

### Issue: High CPU Usage

**Symptoms**:
- CPU usage >90%
- Slow cycle execution
- Timeouts
- System unresponsive

**Root Causes**:
- Inefficient analysis algorithms
- Too many concurrent operations
- Infinite loops
- Resource contention

**Solutions**:

1. Check CPU usage:
```bash
top -p $(pgrep -f self_building_mcp_server)
```

2. Profile code:
```bash
python -m cProfile -o profile.stats backend/agents/self_building/self_building_mcp_server.py
python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative'); p.print_stats(20)"
```

3. Reduce concurrent operations:
```bash
# .env
MAX_CONCURRENT_IMPROVEMENTS=1
CLOUDWATCH_STREAM_INTERVAL_SECONDS=120
```

4. Optimize analysis:
```python
# Use sampling for large datasets
if len(telemetry_data) > 10000:
    telemetry_data = random.sample(telemetry_data, 10000)
```

---

### Issue: Slow Cycle Execution

**Symptoms**:
- Cycle takes >5 minutes
- `cycle_duration_seconds` metric high
- Timeout alerts

**Root Causes**:
- Large analysis window
- Slow LLM generation
- Network latency
- Inefficient queries

**Solutions**:

1. Reduce analysis window:
```bash
# .env
IMPROVEMENT_CYCLE_ANALYSIS_WINDOW_HOURS=12  # Reduce from 24
```

2. Optimize CloudWatch queries:
```sql
-- Add time filters and limits
fields @timestamp, message
| filter @timestamp > ago(1h)
| limit 1000
```

3. Use parallel processing:
```python
# Process opportunities in parallel
import asyncio
results = await asyncio.gather(*[
    process_opportunity(opp) for opp in opportunities
])
```

4. Cache frequently accessed data:
```python
# Add caching for system status
@lru_cache(maxsize=100, ttl=300)
async def get_system_status():
    # ...
```

---

## Deployment Issues

### Issue: Service Won't Start

**Symptoms**:
- Service fails to start
- Health check returns 503
- Process exits immediately

**Root Causes**:
- Missing dependencies
- Configuration errors
- Port already in use
- Permission issues

**Solutions**:

1. Check logs:
```bash
tail -50 backend/logs/self_building_mcp_server.log
```

2. Verify dependencies:
```bash
pip install -r backend/requirements.txt
python -c "import fastapi, boto3, structlog"
```

3. Check port availability:
```bash
netstat -an | grep 8004
# If port in use:
lsof -ti:8004 | xargs kill -9
```

4. Verify configuration:
```bash
python backend/scripts/validate_config.py
```

5. Check permissions:
```bash
ls -la backend/agents/self_building/
chmod +x backend/agents/self_building/self_building_mcp_server.py
```

---

### Issue: Deployment Rollback Failed

**Symptoms**:
- Rollback command fails
- System in inconsistent state
- Old and new code mixed

**Root Causes**:
- Backup missing or corrupted
- File permissions
- Hot reload failure
- Concurrent modifications

**Solutions**:

1. Verify backup exists:
```bash
ls -la backend/backups/
```

2. Manual rollback:
```bash
# Stop service
make stop-service SERVICE=self-building

# Restore from backup
tar -xzf backend/backups/backup_20250110_020000.tar.gz -C backend/

# Restart service
make start-service SERVICE=self-building
```

3. Clear hot reload cache:
```bash
python backend/scripts/clear_hot_reload_cache.py
```

4. Verify system state:
```bash
python backend/scripts/verify_system_state.py
```

---

## Monitoring and Alerting

### Issue: Metrics Not Publishing

**Symptoms**:
- CloudWatch dashboard empty
- No metrics in namespace
- Alarms in INSUFFICIENT_DATA state

**Root Causes**:
- Metrics not being published
- Wrong namespace
- IAM permission issues
- Network issues

**Solutions**:

1. Verify metric publishing:
```bash
grep "put_metric_data" backend/logs/self_building_mcp_server.log
```

2. Check namespace:
```bash
aws cloudwatch list-metrics --namespace SelfBuilding
```

3. Test metric publishing:
```bash
python backend/scripts/test_metric_publishing.py
```

4. Verify IAM permissions:
```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/happyos-self-building \
  --action-names cloudwatch:PutMetricData \
  --resource-arns "*"
```

---

### Issue: Alarms Not Triggering

**Symptoms**:
- Known issues not alerting
- Alarm state stuck in OK
- No notifications received

**Root Causes**:
- Alarm misconfigured
- Threshold too high
- Evaluation period too long
- SNS topic issues

**Solutions**:

1. Check alarm configuration:
```bash
aws cloudwatch describe-alarms --alarm-names SelfBuilding-HighFailureRate-Production
```

2. Test alarm:
```bash
# Manually set alarm state
aws cloudwatch set-alarm-state \
  --alarm-name SelfBuilding-HighFailureRate-Production \
  --state-value ALARM \
  --state-reason "Testing alarm"
```

3. Verify SNS topic:
```bash
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:pagerduty-critical
```

4. Adjust threshold:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name SelfBuilding-HighFailureRate-Production \
  --threshold 2  # Lower from 3
```

---

## Circuit Breaker Issues

### Issue: Circuit Breaker Flapping

**Symptoms**:
- Circuit breaker rapidly opening and closing
- Inconsistent behavior
- High error rate

**Root Causes**:
- Threshold too low
- Recovery timeout too short
- Intermittent service issues
- Network instability

**Solutions**:

1. Increase failure threshold:
```python
# backend/core/circuit_breaker/circuit_breaker.py
CircuitBreaker(
    failure_threshold=5,  # Increase from 3
    recovery_timeout=120,  # Increase from 60
    expected_exception=Exception
)
```

2. Add exponential backoff:
```python
# Increase recovery timeout on repeated failures
if circuit_breaker.failure_count > 5:
    circuit_breaker.recovery_timeout *= 2
```

3. Monitor network stability:
```bash
ping -c 100 cloudwatch.us-east-1.amazonaws.com | tail -5
```

4. Use half-open state:
```python
# Test with single request before fully closing
if circuit_breaker.state == "half_open":
    result = await test_single_request()
    if result.success:
        circuit_breaker.close()
```

---

## Getting Help

### Diagnostic Information to Collect

When reporting issues, collect:

1. **System Status**:
```bash
curl -X POST http://localhost:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}' \
  > system_status.json
```

2. **Recent Logs**:
```bash
tail -500 backend/logs/self_building_mcp_server.log > recent_logs.txt
tail -500 backend/logs/improvement_cycle.log >> recent_logs.txt
tail -500 backend/logs/cloudwatch_streamer.log >> recent_logs.txt
```

3. **Configuration**:
```bash
env | grep -E "(SELF_BUILDING|CLOUDWATCH|IMPROVEMENT|LLM)" > config.txt
```

4. **Metrics**:
```bash
python backend/scripts/export_metrics.py --hours 24 > metrics.json
```

### Support Channels

- **Documentation**: `backend/agents/self_building/docs/`
- **Logs**: `backend/logs/`
- **Metrics**: CloudWatch dashboard "SelfBuilding/System"
- **Slack**: #happyos-self-building
- **Email**: platform-team@happyos.com
- **On-Call**: PagerDuty escalation

### Useful Commands

```bash
# Quick health check
make health-check SERVICE=self-building

# View logs
make logs SERVICE=self-building TAIL=100

# Restart service
make restart SERVICE=self-building

# Run diagnostics
python backend/scripts/run_diagnostics.py

# Export debug bundle
python backend/scripts/export_debug_bundle.py
```

## Appendix

### Log Levels

- `DEBUG`: Detailed diagnostic information
- `INFO`: Normal operations
- `WARNING`: Recoverable issues
- `ERROR`: Errors requiring attention
- `CRITICAL`: System-threatening issues

### Common Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 400 | Bad Request | Check request parameters |
| 401 | Unauthorized | Verify API key |
| 403 | Forbidden | Check permissions |
| 404 | Not Found | Verify resource exists |
| 409 | Conflict | Check for concurrent operations |
| 422 | Validation Failed | Review validation errors |
| 429 | Rate Limited | Reduce request rate |
| 500 | Internal Error | Check logs |
| 503 | Service Unavailable | Check service health |

### Performance Benchmarks

Expected performance metrics:

- Cycle duration: 60-180 seconds
- Generation time: 20-60 seconds
- Validation time: 5-15 seconds
- Deployment time: 5-10 seconds
- Memory usage: 500MB-2GB
- CPU usage: 10-30%
- Telemetry lag: <30 seconds
