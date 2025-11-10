# Monitoring and Observability Auditor - Quick Start Guide

## Overview

The Monitoring and Observability Auditor evaluates your system's monitoring infrastructure to ensure production readiness. It checks CloudWatch dashboards, Prometheus metrics, alarm configuration, and structured logging.

## Quick Start

### Running the Auditor

```python
from backend.core.production_audit import MonitoringObservabilityAuditor

# Create auditor instance
auditor = MonitoringObservabilityAuditor(workspace_root="/path/to/workspace")

# Run audit
result = await auditor.audit()

# Check score
print(f"Score: {result.score}/100")
print(f"Status: {'Production Ready' if result.score >= 80 else 'Needs Work'}")
```

### Using the Test Script

```bash
# Run from workspace root
python3 backend/core/production_audit/test_monitoring_auditor.py
```

## What Gets Checked

### 1. CloudWatch Dashboards (25% of score)

**Checks for**:
- Dashboard configuration files (`.json`)
- CloudWatch implementation
- Dashboard creation functionality
- LLM usage dashboard
- Agent health dashboard

**Files examined**:
- `backend/modules/observability/dashboards/*.json`
- `backend/modules/observability/cloudwatch.py`

### 2. Prometheus Metrics (25% of score)

**Checks for**:
- Prometheus client usage
- Metric types (Counter, Histogram, Gauge)
- HTTP metrics
- AI/LLM metrics
- Database metrics
- Error metrics
- Cost tracking

**Files examined**:
- `backend/services/observability/metrics.py`

### 3. Alarm Configuration (25% of score)

**Checks for**:
- Alarm creation functionality
- Error rate alarms
- Latency alarms
- Cost alarms
- Circuit breaker monitoring

**Files examined**:
- `backend/modules/observability/cloudwatch.py`
- `backend/infrastructure/aws/iac/*alarm*.py`
- `backend/core/circuit_breaker/*.py`

### 4. Structured Logging (25% of score)

**Checks for**:
- JSON formatting
- Trace IDs / Request IDs
- Tenant ID logging
- Cost logging
- Latency logging
- AI-specific logging

**Files examined**:
- `backend/services/observability/logger.py`

## Understanding Results

### Score Interpretation

- **90-100**: Excellent - Production ready
- **80-89**: Good - Production ready with minor improvements
- **60-79**: Fair - Almost ready, some fixes needed
- **Below 60**: Poor - Significant work required

### Gap Severity Levels

- **CRITICAL**: Must fix before production
- **HIGH**: Should fix before production
- **MEDIUM**: Can fix after launch
- **LOW**: Nice-to-have improvements

## Example Output

```
Category: Monitoring and Observability
Score: 91.88/100
Weight: 0.12

Checks (4):
✓ PASS CloudWatch Dashboards: 100.00/100
   Details: CloudWatch: 1 dashboard files found, implementation present, LLM dashboard exists
   Evidence: 2 files

✓ PASS Prometheus Metrics: 100.00/100
   Details: Prometheus metrics: HTTP, AI/LLM, Database, Errors with cost tracking
   Evidence: 1 files

✓ PASS Alarm Configuration: 80.00/100
   Details: Alarms: error rate, latency, circuit breaker
   Evidence: 2 files

✓ PASS Structured Logging: 87.50/100
   Details: Structured logging: JSON formatting, trace IDs, cost tracking, AI logging
   Evidence: 1 files

Gaps (0):

Recommendations:
• Monitoring and observability infrastructure is production-ready

Overall Assessment: 91.88/100
Status: ✓ Production Ready
```

## Common Issues and Solutions

### Issue: "Dashboards directory not found"

**Solution**: Create the dashboards directory and add dashboard configurations:
```bash
mkdir -p backend/modules/observability/dashboards
```

### Issue: "Prometheus client not available"

**Solution**: Install prometheus_client:
```bash
pip install prometheus-client
```

### Issue: "Missing alarm configuration"

**Solution**: Implement alarm creation in CloudWatch module:
```python
async def create_system_alerts(self):
    # Create alarms for error rate, latency, etc.
    pass
```

### Issue: "Incomplete structured logging"

**Solution**: Add context variables for trace IDs:
```python
from contextvars import ContextVar

request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
```

## Integration with Full Audit

The Monitoring and Observability Auditor is part of the complete production readiness audit:

```python
from backend.core.production_audit import (
    LLMIntegrationAuditor,
    InfrastructureResilienceAuditor,
    MonitoringObservabilityAuditor,
    ScoringEngine
)

# Run all auditors
llm_result = await LLMIntegrationAuditor().audit()
infra_result = await InfrastructureResilienceAuditor().audit()
monitoring_result = await MonitoringObservabilityAuditor().audit()

# Calculate overall score
scoring_engine = ScoringEngine()
overall_score = scoring_engine.calculate_overall_score([
    llm_result,
    infra_result,
    monitoring_result
])
```

## Requirements Coverage

This auditor covers Requirements 4.1-4.5:

- ✅ 4.1: CloudWatch dashboards for LLM usage
- ✅ 4.2: Prometheus metrics for critical operations
- ✅ 4.3: Alarms for errors, costs, and circuit breakers
- ✅ 4.4: LLM call logging with tenant_id, agent_id, cost, latency
- ✅ 4.5: Structured logging with trace IDs

## Next Steps

After running the auditor:

1. Review the gaps identified
2. Prioritize fixes based on severity
3. Implement recommendations
4. Re-run audit to verify improvements
5. Proceed to next auditor (Security and Compliance)

## Support

For issues or questions:
- Check the implementation: `backend/core/production_audit/monitoring_observability_auditor.py`
- Review test script: `backend/core/production_audit/test_monitoring_auditor.py`
- See requirements: `.kiro/specs/production-readiness-audit/requirements.md`
