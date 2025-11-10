# Self-Building Agent Deployment Guide

## Overview

This guide covers the deployment of the Self-Building Agent to production environments using a phased rollout strategy. The deployment ensures zero downtime, maintains system stability, and provides rollback capabilities at each phase.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Phased Rollout Strategy](#phased-rollout-strategy)
4. [Feature Flag Configuration](#feature-flag-configuration)
5. [Monitoring Setup](#monitoring-setup)
6. [Rollback Procedures](#rollback-procedures)
7. [Post-Deployment Validation](#post-deployment-validation)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Infrastructure Requirements

- **AWS Account** with appropriate permissions
- **IAM Role** with CloudWatch, Lambda, DynamoDB access
- **Python 3.10+** runtime environment
- **Redis** for caching (ElastiCache or local)
- **PostgreSQL** for persistent storage (optional)

### Software Requirements

```bash
# Python dependencies
pip install -r backend/requirements.txt

# AWS CLI
aws --version  # Should be 2.x

# Docker (for local testing)
docker --version
docker-compose --version
```

### Access Requirements

- AWS Console access
- CloudWatch dashboard access
- Deployment pipeline access (CI/CD)
- PagerDuty/alerting system access

### Environment Setup

```bash
# Clone repository
git clone https://github.com/your-org/happyos.git
cd happyos

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Copy environment template
cp .env.example .env

# Configure environment variables (see Configuration section)
nano .env
```

## Pre-Deployment Checklist

### Code Review

- [ ] All code reviewed and approved
- [ ] Unit tests passing (>85% coverage)
- [ ] Integration tests passing
- [ ] Security scan completed (no critical vulnerabilities)
- [ ] Performance tests completed
- [ ] Documentation updated

### Configuration Review

- [ ] Environment variables configured
- [ ] Feature flags set appropriately
- [ ] IAM permissions verified
- [ ] CloudWatch alarms configured
- [ ] Monitoring dashboards created
- [ ] Audit logging enabled

### Infrastructure Validation

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Verify CloudWatch access
aws cloudwatch list-metrics --namespace MeetMind/MCPUIHub --max-items 1

# Verify IAM permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/happyos-self-building \
  --action-names cloudwatch:GetMetricStatistics logs:FilterLogEvents \
  --resource-arns "*"

# Test LLM service connectivity
python -c "from backend.core.llm.llm_service import LLMService; import asyncio; asyncio.run(LLMService().generate_text('test'))"
```

### Backup Procedures

```bash
# Backup current system state
python backend/scripts/backup_system_state.py \
  --output backup_$(date +%Y%m%d_%H%M%S).tar.gz

# Backup database (if applicable)
pg_dump happyos_db > backup_db_$(date +%Y%m%d_%H%M%S).sql

# Backup configuration
cp -r backend/core/self_building backup_self_building_$(date +%Y%m%d_%H%M%S)
```

## Phased Rollout Strategy

### Phase 0: Local Testing (Day 0)

**Objective**: Validate functionality in local environment

**Steps**:

1. Start LocalStack for AWS simulation:
```bash
docker-compose up -d localstack
export AWS_ENDPOINT_URL=http://localhost:4566
```

2. Start self-building agent locally:
```bash
cd backend
python -m agents.self_building.self_building_mcp_server
```

3. Run integration tests:
```bash
pytest backend/tests/test_self_building_mcp_server.py -v
pytest backend/tests/test_improvement_cycle_e2e.py -v
```

4. Trigger test improvement cycle:
```bash
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

**Success Criteria**:
- All tests pass
- Test cycle completes successfully
- No errors in logs
- Metrics published to LocalStack

**Duration**: 1-2 days

---

### Phase 1: Development Environment (Days 1-3)

**Objective**: Deploy to development environment with full functionality enabled

**Configuration**:
```bash
# .env.development
ENVIRONMENT=development
ENABLE_SELF_BUILDING=true
ENABLE_CLOUDWATCH_STREAMING=true
ENABLE_AUTONOMOUS_IMPROVEMENTS=true
ENABLE_COMPONENT_GENERATION=true
ENABLE_IMPROVEMENT_ROLLBACK=true

# Conservative settings
IMPROVEMENT_CYCLE_INTERVAL_HOURS=6
MAX_CONCURRENT_IMPROVEMENTS=2
IMPROVEMENT_QUALITY_THRESHOLD=0.85
MONITORING_DURATION_SECONDS=1800
ROLLBACK_DEGRADATION_THRESHOLD=0.10
```

**Deployment**:
```bash
# Deploy to development
make deploy ENV=development REGION=us-east-1

# Verify deployment
curl http://dev.happyos.internal:8004/health

# Register agent
python backend/scripts/register_self_building_agent.py --env development
```

**Monitoring**:
- Watch CloudWatch dashboard: "SelfBuilding/Development"
- Monitor logs: `tail -f backend/logs/self_building_mcp_server.log`
- Check metrics every hour

**Success Criteria**:
- Agent starts successfully
- CloudWatch streaming active
- First improvement cycle completes
- No critical errors
- Metrics within expected ranges

**Duration**: 3 days

---

### Phase 2: Staging Environment - Observation Mode (Days 4-7)

**Objective**: Deploy to staging with autonomous improvements disabled (observation only)

**Configuration**:
```bash
# .env.staging
ENVIRONMENT=staging
ENABLE_SELF_BUILDING=true
ENABLE_CLOUDWATCH_STREAMING=true
ENABLE_AUTONOMOUS_IMPROVEMENTS=false  # Observation mode
ENABLE_COMPONENT_GENERATION=false
ENABLE_IMPROVEMENT_ROLLBACK=true

IMPROVEMENT_CYCLE_INTERVAL_HOURS=24
```

**Deployment**:
```bash
# Deploy to staging
make deploy ENV=staging REGION=us-east-1

# Verify deployment
curl http://staging.happyos.internal:8004/health

# Start observation
python backend/scripts/start_observation_mode.py --env staging
```

**Observation Tasks**:
1. Monitor telemetry collection (metrics, logs, events)
2. Review identified improvement opportunities
3. Validate impact score calculations
4. Check for false positives
5. Tune thresholds based on observations

**Success Criteria**:
- Telemetry streaming stable for 3 days
- Opportunities identified match manual analysis
- No performance impact on staging environment
- Team comfortable with identified opportunities

**Duration**: 4 days

---

### Phase 3: Staging Environment - Manual Improvements (Days 8-14)

**Objective**: Enable manual improvement triggering in staging

**Configuration**:
```bash
# .env.staging (updated)
ENABLE_AUTONOMOUS_IMPROVEMENTS=false  # Still manual
ENABLE_COMPONENT_GENERATION=true      # Enable generation

# More conservative settings
IMPROVEMENT_QUALITY_THRESHOLD=0.90
MONITORING_DURATION_SECONDS=3600
ROLLBACK_DEGRADATION_THRESHOLD=0.08
```

**Manual Improvement Process**:

1. Review opportunities:
```bash
curl -X POST http://staging.happyos.internal:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "query_telemetry_insights",
      "arguments": {"time_range_hours": 24}
    },
    "id": 1
  }'
```

2. Select low-risk opportunity

3. Trigger improvement:
```bash
curl -X POST http://staging.happyos.internal:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "trigger_improvement_cycle",
      "arguments": {
        "analysis_window_hours": 24,
        "max_improvements": 1
      }
    },
    "id": 1
  }'
```

4. Monitor for 1 hour

5. Review results and rollback if needed

**Success Criteria**:
- 5+ manual improvements deployed successfully
- <20% rollback rate
- Actual impact matches predicted impact
- No incidents caused by improvements
- Team confident in improvement quality

**Duration**: 7 days

---

### Phase 4: Production - Observation Mode (Days 15-21)

**Objective**: Deploy to production in observation-only mode

**Configuration**:
```bash
# .env.production
ENVIRONMENT=production
ENABLE_SELF_BUILDING=true
ENABLE_CLOUDWATCH_STREAMING=true
ENABLE_AUTONOMOUS_IMPROVEMENTS=false  # Observation only
ENABLE_COMPONENT_GENERATION=false
ENABLE_IMPROVEMENT_ROLLBACK=true

# Production settings
IMPROVEMENT_CYCLE_INTERVAL_HOURS=24
CLOUDWATCH_LOG_SAMPLING_RATE=0.5  # Sample 50% of logs
```

**Deployment**:
```bash
# Deploy to production (requires approval)
make deploy ENV=production REGION=us-east-1 APPROVAL=required

# Verify deployment
curl https://api.happyos.com:8004/health

# Enable monitoring
python backend/scripts/enable_production_monitoring.py
```

**Observation Focus**:
- Production traffic patterns
- Real-world performance characteristics
- Opportunity identification accuracy
- Impact score calibration
- False positive rate

**Success Criteria**:
- Stable operation for 7 days
- No performance impact (<1% overhead)
- Opportunities align with engineering team's observations
- Stakeholder approval to proceed

**Duration**: 7 days

---

### Phase 5: Production - Tenant-Scoped Improvements (Days 22-35)

**Objective**: Enable autonomous improvements for single tenant

**Configuration**:
```bash
# .env.production (updated)
ENABLE_AUTONOMOUS_IMPROVEMENTS=true
ENABLE_COMPONENT_GENERATION=false  # Still disabled

# Very conservative settings
IMPROVEMENT_CYCLE_INTERVAL_HOURS=168  # Weekly
MAX_CONCURRENT_IMPROVEMENTS=1
IMPROVEMENT_QUALITY_THRESHOLD=0.95
IMPROVEMENT_RISK_TOLERANCE=0.05
MONITORING_DURATION_SECONDS=7200  # 2 hours
ROLLBACK_DEGRADATION_THRESHOLD=0.05  # 5% threshold

# Tenant-specific configuration
TENANT_IMPROVEMENT_CONFIGS='{"meetmind-dev": {"enabled": true}}'
```

**Deployment**:
```bash
# Update configuration
make update-config ENV=production

# Restart service
make restart-service SERVICE=self-building ENV=production

# Verify tenant configuration
curl https://api.happyos.com:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}'
```

**Monitoring**:
- 24/7 on-call rotation
- Real-time alerts to PagerDuty
- Daily review of improvements
- Weekly stakeholder reports

**Success Criteria**:
- 10+ improvements deployed successfully
- <10% rollback rate
- No production incidents
- Positive impact on tenant metrics
- Stakeholder approval to expand

**Duration**: 14 days

---

### Phase 6: Production - Multi-Tenant Rollout (Days 36-50)

**Objective**: Gradually enable for all production tenants

**Rollout Schedule**:

**Week 1** (Days 36-42):
```bash
# Enable for 3 tenants
TENANT_IMPROVEMENT_CONFIGS='{
  "meetmind-dev": {"enabled": true},
  "agent-svea-dev": {"enabled": true},
  "felicias-finance-dev": {"enabled": true}
}'
```

**Week 2** (Days 43-50):
```bash
# Enable for all tenants
TENANT_IMPROVEMENT_CONFIGS='{
  "meetmind-prod": {"enabled": true, "max_concurrent": 2},
  "agent-svea-prod": {"enabled": true, "max_concurrent": 1},
  "felicias-finance-prod": {"enabled": true, "max_concurrent": 2}
}'
```

**Success Criteria**:
- All tenants stable
- Consistent improvement quality across tenants
- No tenant-specific issues
- Positive feedback from all teams

**Duration**: 15 days

---

### Phase 7: Production - Full Functionality (Days 51+)

**Objective**: Enable all features including component generation

**Configuration**:
```bash
# .env.production (final)
ENABLE_AUTONOMOUS_IMPROVEMENTS=true
ENABLE_COMPONENT_GENERATION=true  # Now enabled

# Gradually relax settings
IMPROVEMENT_CYCLE_INTERVAL_HOURS=24  # Daily
MAX_CONCURRENT_IMPROVEMENTS=3
IMPROVEMENT_QUALITY_THRESHOLD=0.90
MONITORING_DURATION_SECONDS=3600  # 1 hour
ROLLBACK_DEGRADATION_THRESHOLD=0.08
```

**Deployment**:
```bash
# Enable component generation
make update-config ENV=production FEATURE=component_generation

# Restart service
make restart-service SERVICE=self-building ENV=production
```

**Ongoing Operations**:
- Weekly review of improvement metrics
- Monthly tuning of thresholds
- Quarterly review of generated components
- Continuous monitoring and optimization

**Success Criteria**:
- System operating autonomously
- Consistent positive impact
- Team confidence in system
- Reduced manual intervention needed

---

## Feature Flag Configuration

### Feature Flag System

Feature flags are managed in `backend/core/settings.py`:

```python
class Settings(BaseSettings):
    # Self-building feature flags
    enable_self_building: bool = Field(default=True, env="ENABLE_SELF_BUILDING")
    enable_cloudwatch_streaming: bool = Field(default=True, env="ENABLE_CLOUDWATCH_STREAMING")
    enable_autonomous_improvements: bool = Field(default=False, env="ENABLE_AUTONOMOUS_IMPROVEMENTS")
    enable_component_generation: bool = Field(default=False, env="ENABLE_COMPONENT_GENERATION")
    enable_improvement_rollback: bool = Field(default=True, env="ENABLE_IMPROVEMENT_ROLLBACK")
```

### Runtime Flag Updates

Update flags without restarting:

```python
# Update via API
curl -X POST https://api.happyos.com/admin/feature-flags \
  -H "Authorization: Bearer ${ADMIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "enable_autonomous_improvements": true
  }'

# Update via CLI
python backend/scripts/update_feature_flag.py \
  --flag enable_autonomous_improvements \
  --value true \
  --env production
```

### Flag Monitoring

Monitor flag states:

```bash
# Get current flags
curl https://api.happyos.com:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}' \
  | jq '.result.feature_flags'
```

### Emergency Flag Disable

Quickly disable features in emergency:

```bash
# Disable all autonomous features
python backend/scripts/emergency_disable.py --all

# Disable specific feature
python backend/scripts/emergency_disable.py --feature autonomous_improvements
```

## Monitoring Setup

### CloudWatch Dashboards

Create monitoring dashboards:

```bash
# Create self-building dashboard
aws cloudwatch put-dashboard \
  --dashboard-name SelfBuilding-Production \
  --dashboard-body file://backend/infrastructure/aws/dashboards/self_building.json

# Create alarm dashboard
aws cloudwatch put-dashboard \
  --dashboard-name SelfBuilding-Alarms \
  --dashboard-body file://backend/infrastructure/aws/dashboards/alarms.json
```

### CloudWatch Alarms

Configure critical alarms:

```bash
# High failure rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name SelfBuilding-HighFailureRate-Production \
  --alarm-description "Alert when improvement failure rate > 30%" \
  --metric-name improvement_cycles_failed \
  --namespace SelfBuilding \
  --statistic Sum \
  --period 3600 \
  --evaluation-periods 1 \
  --threshold 3 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:pagerduty-critical

# High rollback rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name SelfBuilding-HighRollbackRate-Production \
  --metric-name improvements_rolled_back \
  --namespace SelfBuilding \
  --statistic Sum \
  --period 3600 \
  --threshold 2 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:pagerduty-high

# Circuit breaker open alarm
aws cloudwatch put-metric-alarm \
  --alarm-name SelfBuilding-CircuitBreakerOpen-Production \
  --metric-name circuit_breaker_opens \
  --namespace SelfBuilding \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:pagerduty-high
```

### Log Aggregation

Configure log aggregation:

```bash
# Create log group
aws logs create-log-group \
  --log-group-name /happyos/self-building/production

# Set retention
aws logs put-retention-policy \
  --log-group-name /happyos/self-building/production \
  --retention-in-days 30

# Create metric filter for errors
aws logs put-metric-filter \
  --log-group-name /happyos/self-building/production \
  --filter-name ErrorCount \
  --filter-pattern '[timestamp, level=ERROR*, ...]' \
  --metric-transformations \
    metricName=ErrorCount,metricNamespace=SelfBuilding,metricValue=1
```

### Grafana Dashboards (Optional)

If using Grafana:

```bash
# Import dashboard
curl -X POST http://grafana.happyos.internal/api/dashboards/db \
  -H "Authorization: Bearer ${GRAFANA_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @backend/infrastructure/grafana/self_building_dashboard.json
```

## Rollback Procedures

### Automatic Rollback

Automatic rollback is built into the improvement cycle (see IMPROVEMENT_CYCLE.md).

### Manual Rollback

#### Rollback Single Improvement

```bash
# List recent improvements
python backend/scripts/list_improvements.py --env production --hours 24

# Rollback specific improvement
python backend/scripts/rollback_improvement.py \
  --improvement-id imp_001 \
  --reason "manual_rollback" \
  --env production
```

#### Rollback All Recent Improvements

```bash
# Rollback all improvements from last 24 hours
python backend/scripts/rollback_improvements.py \
  --hours 24 \
  --env production \
  --confirm
```

#### Disable Self-Building Agent

```bash
# Emergency disable
python backend/scripts/emergency_disable.py --all --env production

# Or via feature flag
curl -X POST https://api.happyos.com/admin/feature-flags \
  -H "Authorization: Bearer ${ADMIN_API_KEY}" \
  -d '{"enable_self_building": false}'
```

#### Full System Rollback

```bash
# Stop self-building service
make stop-service SERVICE=self-building ENV=production

# Restore from backup
python backend/scripts/restore_system_state.py \
  --backup backup_20250110_020000.tar.gz \
  --env production

# Restart service
make start-service SERVICE=self-building ENV=production

# Verify rollback
curl https://api.happyos.com:8004/health
```

### Rollback Verification

```bash
# Verify system state
python backend/scripts/verify_system_state.py --env production

# Check metrics
aws cloudwatch get-metric-statistics \
  --namespace SelfBuilding \
  --metric-name improvements_rolled_back \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Review logs
aws logs tail /happyos/self-building/production --follow
```

## Post-Deployment Validation

### Health Checks

```bash
# Service health
curl https://api.happyos.com:8004/health

# Component health
curl https://api.happyos.com:8004/mcp \
  -H "Authorization: Bearer ${SELF_BUILDING_MCP_API_KEY}" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_system_status"},"id":1}' \
  | jq '.result.components'
```

### Smoke Tests

```bash
# Run smoke tests
pytest backend/tests/smoke/test_self_building_smoke.py -v

# Test MCP tools
python backend/scripts/test_mcp_tools.py --env production
```

### Performance Validation

```bash
# Check latency
python backend/scripts/measure_latency.py \
  --endpoint https://api.happyos.com:8004/mcp \
  --iterations 100

# Check resource usage
python backend/scripts/check_resource_usage.py --env production
```

### Metrics Validation

```bash
# Verify metrics are being published
aws cloudwatch list-metrics --namespace SelfBuilding

# Check metric values
python backend/scripts/validate_metrics.py --env production --hours 1
```

## Troubleshooting

### Deployment Fails

**Issue**: Deployment script fails

**Solutions**:
1. Check AWS credentials: `aws sts get-caller-identity`
2. Verify IAM permissions
3. Check CloudFormation stack status
4. Review deployment logs
5. Rollback to previous version

### Service Won't Start

**Issue**: Self-building agent fails to start

**Solutions**:
1. Check logs: `tail -f backend/logs/self_building_mcp_server.log`
2. Verify environment variables
3. Test dependencies: `python -c "import boto3; import fastapi"`
4. Check port availability: `netstat -an | grep 8004`
5. Verify AWS connectivity

### High Error Rate

**Issue**: High error rate after deployment

**Solutions**:
1. Check CloudWatch alarms
2. Review error logs
3. Verify configuration
4. Check circuit breaker state
5. Consider rollback if errors persist

### Performance Degradation

**Issue**: System performance degraded after deployment

**Solutions**:
1. Check resource utilization
2. Review improvement deployments
3. Trigger manual rollback if needed
4. Analyze CloudWatch metrics
5. Adjust configuration parameters

## Support

For deployment issues:
- **On-Call**: PagerDuty escalation
- **Slack**: #happyos-deployments
- **Email**: platform-team@happyos.com
- **Documentation**: https://docs.happyos.com/self-building

## Appendix

### Deployment Checklist

```markdown
## Pre-Deployment
- [ ] Code reviewed and approved
- [ ] Tests passing
- [ ] Security scan completed
- [ ] Configuration reviewed
- [ ] Backup created
- [ ] Stakeholders notified

## Deployment
- [ ] Feature flags configured
- [ ] Service deployed
- [ ] Health checks passing
- [ ] Monitoring enabled
- [ ] Alarms configured

## Post-Deployment
- [ ] Smoke tests passing
- [ ] Metrics validated
- [ ] Performance acceptable
- [ ] No critical errors
- [ ] Team notified

## Rollback Plan
- [ ] Rollback procedure documented
- [ ] Backup verified
- [ ] Rollback tested
- [ ] Team trained on rollback
```

### Configuration Templates

See `backend/agents/self_building/config/` for environment-specific templates.

### Useful Commands

```bash
# Quick status check
make status SERVICE=self-building ENV=production

# View logs
make logs SERVICE=self-building ENV=production TAIL=100

# Restart service
make restart SERVICE=self-building ENV=production

# Run health check
make health-check SERVICE=self-building ENV=production
```
