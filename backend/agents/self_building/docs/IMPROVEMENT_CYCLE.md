# Autonomous Improvement Cycle Documentation

## Overview

The Autonomous Improvement Cycle is the core mechanism by which the Self-Building Agent continuously optimizes the HappyOS system. It analyzes telemetry data, identifies optimization opportunities, generates code improvements, deploys them, and monitors their impact with automatic rollback on degradation.

## Cycle Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Autonomous Improvement Cycle                    │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Phase 1    │───▶│   Phase 2    │───▶│   Phase 3    │      │
│  │  Telemetry   │    │  Analysis &  │    │     Code     │      │
│  │  Collection  │    │Prioritization│    │  Generation  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                    │                    │              │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Phase 6    │◀───│   Phase 5    │◀───│   Phase 4    │      │
│  │  Completion  │    │  Monitoring  │    │  Validation  │      │
│  │  & Reporting │    │  & Rollback  │    │& Deployment  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Cycle Phases

### Phase 1: Telemetry Collection

**Duration**: Continuous (background streaming)  
**Trigger**: Automatic (every 60 seconds)

The CloudWatch Telemetry Streamer continuously collects:

1. **Metrics**: Performance indicators from CloudWatch
   - Response latency
   - Error rates
   - Resource utilization
   - Request throughput

2. **Logs**: Error patterns and operational events
   - Error messages and stack traces
   - Performance warnings
   - Component interactions

3. **Events**: System state changes
   - CloudWatch alarm transitions
   - Lambda function completions
   - Deployment events

**Data Flow**:
```
CloudWatch → CloudWatchTelemetryStreamer → LearningEngine.ingest_telemetry()
```

**Configuration**:
```python
# Environment variables
CLOUDWATCH_STREAM_INTERVAL_SECONDS=60
CLOUDWATCH_LOG_SAMPLING_RATE=1.0
CLOUDWATCH_EVENT_DEDUP_WINDOW_SECONDS=300
```

---

### Phase 2: Analysis & Prioritization

**Duration**: 5-15 seconds  
**Trigger**: Scheduled (every 24 hours) or manual (via MCP)

The LearningEngine analyzes collected telemetry to identify improvement opportunities:

#### 2.1 Performance Trend Analysis

Detects performance degradation using statistical methods:

```python
# Moving average with standard deviation
baseline = mean(metrics[-7d:])
current = mean(metrics[-1h:])
std_dev = std(metrics[-7d:])

if current > baseline + (2 * std_dev):
    # Performance degradation detected
    severity = "high"
```

**Detected Patterns**:
- Latency increases (> 20% degradation)
- Error rate spikes (> 5% increase)
- Resource exhaustion (> 80% utilization)
- Throughput drops (> 30% decrease)

#### 2.2 Error Pattern Recognition

Clusters similar errors using frequency analysis:

```python
# Group errors by type and component
error_clusters = group_by(logs, ['error.type', 'component'])

for cluster in error_clusters:
    if cluster.frequency > 10 and cluster.recency < 1h:
        # Recurring error pattern detected
        opportunities.append(create_fix_opportunity(cluster))
```

**Detected Patterns**:
- Recurring exceptions (> 10 occurrences/hour)
- Timeout errors (> 5 second duration)
- Database connection failures
- API integration errors

#### 2.3 Optimization Opportunity Identification

Identifies code optimization opportunities:

```python
# Cache hit rate analysis
cache_hit_rate = cache_hits / (cache_hits + cache_misses)

if cache_hit_rate < 0.5 and request_frequency > 100/hour:
    # Low cache efficiency detected
    opportunities.append({
        'type': 'caching_optimization',
        'impact_score': calculate_impact(request_frequency, latency_reduction)
    })
```

**Detected Opportunities**:
- Low cache hit rates (< 50%)
- Inefficient database queries (N+1 problems)
- Redundant API calls
- Unoptimized algorithms

#### 2.4 Impact Scoring

Prioritizes opportunities using impact score:

```python
impact_score = (
    performance_gain_percentage * 
    affected_users_per_hour * 
    frequency_per_day
) / 100

# Example:
# - 30% latency reduction
# - 1000 affected users/hour
# - 24 occurrences/day
# Impact score = (30 * 1000 * 24) / 100 = 7200
```

**Priority Levels**:
- **Critical** (score > 5000): Deploy immediately
- **High** (score > 1000): Deploy in next cycle
- **Medium** (score > 100): Deploy when capacity available
- **Low** (score < 100): Queue for future consideration

**Output**: Sorted list of `ImprovementOpportunity` objects

---

### Phase 3: Code Generation

**Duration**: 30-60 seconds per improvement  
**Trigger**: Automatic (after prioritization)

The LLMCodeGenerator creates production-ready code improvements:

#### 3.1 Prompt Construction

Builds comprehensive prompt with context:

```python
prompt = f"""
System Architecture:
{architecture_overview}

Existing Code Pattern:
{existing_code_sample}

Improvement Requirement:
{opportunity.description}

Telemetry Evidence:
{opportunity.telemetry_evidence}

Optimization Goals:
- Reduce latency by {opportunity.target_improvement}%
- Maintain test coverage > 85%
- Follow existing code patterns
- Ensure backward compatibility

Generate improved code that addresses the requirement while meeting all goals.
"""
```

#### 3.2 LLM Generation

Calls LLM service with circuit breaker protection:

```python
response = await llm_circuit_breaker.call_with_protection(
    llm_service.generate_text,
    prompt=prompt,
    max_tokens=4000,
    temperature=0.1,  # Low temperature for deterministic code
    model="anthropic.claude-v2"
)
```

**Retry Strategy**:
- Max retries: 3
- Backoff: Exponential (2^attempt seconds)
- Timeout: 60 seconds per attempt

#### 3.3 Code Parsing

Extracts code files from LLM response:

```python
# Expected format:
# ```python:path/to/file.py
# <code>
# ```

code_files = parse_code_blocks(response)
# Returns: {'path/to/file.py': '<code>'}
```

**Output**: Dictionary mapping file paths to generated code

---

### Phase 4: Validation & Deployment

**Duration**: 10-20 seconds  
**Trigger**: Automatic (after code generation)

#### 4.1 Code Validation

Validates generated code before deployment:

```python
validation_checks = [
    check_syntax(),           # AST parsing
    check_imports(),          # Import resolution
    check_type_hints(),       # Type checking (if present)
    check_security(),         # Security vulnerability scan
    check_complexity(),       # Cyclomatic complexity
    check_test_coverage()     # Test coverage estimation
]

if all(validation_checks):
    proceed_to_deployment()
else:
    mark_as_failed(validation_errors)
```

**Validation Criteria**:
- Syntax valid (no AST errors)
- All imports resolvable
- Type hints valid (if present)
- No security vulnerabilities (SQL injection, XSS, etc.)
- Complexity < 10 per function
- Estimated test coverage > 80%

#### 4.2 Deployment

Deploys validated code using hot reload:

```python
# Store previous version for rollback
previous_version = backup_component(component_path)

# Write new code
write_code_files(code_files)

# Hot reload component
await hot_reload_manager.reload_component(component_name)

# Record deployment
audit_logger.log_deployment(
    improvement_id=improvement_id,
    component=component_name,
    previous_version=previous_version,
    new_version=code_hash
)
```

**Deployment Strategy**:
- **Tenant-scoped**: Deploy only to specified tenant
- **System-wide**: Requires meta-orchestrator approval
- **Canary**: Deploy to 10% of traffic first (future enhancement)

**Output**: Deployment confirmation with timestamp

---

### Phase 5: Monitoring & Rollback

**Duration**: 1 hour (configurable)  
**Trigger**: Automatic (after deployment)

#### 5.1 Baseline Collection

Collects baseline metrics before deployment:

```python
baseline_metrics = {
    'latency_p50': get_metric('ResponseLatency', percentile=50),
    'latency_p95': get_metric('ResponseLatency', percentile=95),
    'latency_p99': get_metric('ResponseLatency', percentile=99),
    'error_rate': get_metric('ErrorRate'),
    'throughput': get_metric('RequestCount')
}
```

#### 5.2 Continuous Monitoring

Monitors metrics during monitoring period:

```python
monitoring_duration = 3600  # 1 hour
check_interval = 60         # 1 minute

for elapsed in range(0, monitoring_duration, check_interval):
    await asyncio.sleep(check_interval)
    
    current_metrics = collect_current_metrics()
    degradation = calculate_degradation(baseline_metrics, current_metrics)
    
    if degradation > ROLLBACK_THRESHOLD:
        await trigger_rollback()
        break
```

#### 5.3 Degradation Calculation

Calculates performance degradation:

```python
def calculate_degradation(baseline, current):
    """
    Returns degradation percentage (0.0 to 1.0+)
    Positive values indicate degradation
    """
    degradations = []
    
    # Latency degradation (higher is worse)
    if current['latency_p95'] > baseline['latency_p95']:
        lat_deg = (current['latency_p95'] - baseline['latency_p95']) / baseline['latency_p95']
        degradations.append(lat_deg)
    
    # Error rate degradation (higher is worse)
    if current['error_rate'] > baseline['error_rate']:
        err_deg = (current['error_rate'] - baseline['error_rate']) / max(baseline['error_rate'], 0.01)
        degradations.append(err_deg)
    
    # Throughput degradation (lower is worse)
    if current['throughput'] < baseline['throughput']:
        thr_deg = (baseline['throughput'] - current['throughput']) / baseline['throughput']
        degradations.append(thr_deg)
    
    return max(degradations) if degradations else 0.0
```

**Rollback Threshold**: 10% degradation (configurable)

#### 5.4 Automatic Rollback

Rolls back improvement if degradation detected:

```python
async def trigger_rollback(improvement_id):
    logger.warning(f"Triggering rollback for {improvement_id}")
    
    # Restore previous version
    previous_version = get_previous_version(improvement_id)
    write_code_files(previous_version.files)
    
    # Hot reload component
    await hot_reload_manager.reload_component(component_name)
    
    # Record rollback
    audit_logger.log_rollback(
        improvement_id=improvement_id,
        reason="performance_degradation",
        degradation_percentage=degradation * 100
    )
    
    # Alert team
    await send_alert(
        severity="high",
        message=f"Improvement {improvement_id} rolled back due to {degradation*100}% degradation"
    )
```

**Output**: Monitoring report with rollback decision

---

### Phase 6: Completion & Reporting

**Duration**: 1-2 seconds  
**Trigger**: Automatic (after monitoring period)

#### 6.1 Impact Assessment

Assesses actual improvement impact:

```python
impact_assessment = {
    'improvement_id': improvement_id,
    'status': 'completed' if not rolled_back else 'rolled_back',
    'metrics': {
        'baseline': baseline_metrics,
        'final': final_metrics,
        'improvement': {
            'latency_reduction_ms': baseline['latency_p95'] - final['latency_p95'],
            'latency_reduction_pct': ((baseline['latency_p95'] - final['latency_p95']) / baseline['latency_p95']) * 100,
            'error_rate_change': final['error_rate'] - baseline['error_rate'],
            'throughput_change': final['throughput'] - baseline['throughput']
        }
    },
    'execution_time_seconds': total_execution_time,
    'cost': {
        'llm_tokens': llm_tokens_used,
        'llm_cost_usd': llm_cost,
        'cloudwatch_api_calls': cloudwatch_calls
    }
}
```

#### 6.2 Learning Update

Updates LearningEngine with cycle results:

```python
await learning_engine.record_improvement_outcome(
    opportunity=opportunity,
    generated_code=code_files,
    deployment_result=deployment_result,
    monitoring_result=monitoring_result,
    final_impact=impact_assessment
)

# Learning engine uses this data to:
# - Improve future opportunity identification
# - Refine impact score calculations
# - Optimize prompt engineering
# - Adjust rollback thresholds
```

#### 6.3 Reporting

Generates cycle report:

```python
cycle_report = {
    'cycle_id': cycle_id,
    'start_time': start_time,
    'end_time': end_time,
    'duration_seconds': duration,
    'telemetry_analyzed': {
        'metrics': metric_count,
        'logs': log_count,
        'events': event_count
    },
    'opportunities_identified': len(opportunities),
    'improvements_attempted': len(improvements),
    'improvements_deployed': len([i for i in improvements if i.status == 'deployed']),
    'improvements_rolled_back': len([i for i in improvements if i.status == 'rolled_back']),
    'total_impact': sum([i.impact_score for i in improvements if i.status == 'deployed']),
    'improvements': [impact_assessment for improvement in improvements]
}

# Publish report
await publish_cycle_report(cycle_report)
```

**Output**: Comprehensive cycle report

---

## Cycle Timing

### Scheduled Cycles

Default schedule: Every 24 hours

```python
# Configuration
IMPROVEMENT_CYCLE_INTERVAL_HOURS=24
IMPROVEMENT_CYCLE_START_TIME="02:00"  # 2 AM UTC (low traffic)
```

### Manual Cycles

Triggered via MCP tool:

```python
# Trigger immediate cycle
result = await self_building_client.trigger_improvement_cycle(
    analysis_window_hours=24,
    max_improvements=3,
    tenant_id="meetmind-prod"
)
```

### Emergency Cycles

Triggered by critical CloudWatch alarms:

```python
# Automatic trigger on alarm
if alarm.state == "ALARM" and alarm.severity == "critical":
    await trigger_emergency_cycle(
        analysis_window_hours=1,  # Analyze last hour only
        max_improvements=1,        # Single focused improvement
        priority="emergency"
    )
```

**Emergency Cycle Timing**:
- Trigger delay: < 30 seconds after alarm
- Analysis: 5-10 seconds
- Generation: 20-30 seconds
- Deployment: 5-10 seconds
- Total: < 2 minutes to deployment

---

## Prioritization Algorithm

### Impact Score Calculation

```python
def calculate_impact_score(opportunity):
    """
    Calculate impact score for prioritization.
    
    Formula:
    impact_score = (performance_gain × affected_users × frequency) / 100
    
    Adjustments:
    - Multiply by 2 for critical severity
    - Multiply by 1.5 for high severity
    - Multiply by 0.5 for low confidence (< 0.7)
    """
    base_score = (
        opportunity.performance_gain_percentage *
        opportunity.affected_users_per_hour *
        opportunity.frequency_per_day
    ) / 100
    
    # Severity multiplier
    severity_multipliers = {
        'critical': 2.0,
        'high': 1.5,
        'medium': 1.0,
        'low': 0.5
    }
    base_score *= severity_multipliers[opportunity.severity]
    
    # Confidence adjustment
    if opportunity.confidence_score < 0.7:
        base_score *= 0.5
    
    # Risk penalty
    risk_penalties = {
        'high': 0.5,    # Reduce score by 50% for high risk
        'medium': 0.8,  # Reduce score by 20% for medium risk
        'low': 1.0      # No penalty for low risk
    }
    base_score *= risk_penalties[opportunity.risk_level]
    
    return base_score
```

### Prioritization Rules

1. **Critical Severity**: Always prioritize first
2. **High Impact Score**: Sort by impact score (descending)
3. **Low Risk**: Prefer low-risk improvements when scores are similar
4. **High Confidence**: Prefer high-confidence opportunities
5. **Tenant Priority**: System-wide improvements require approval

### Concurrent Improvement Limits

```python
# Configuration
MAX_CONCURRENT_IMPROVEMENTS=3

# Enforcement
active_improvements = get_active_improvements()
if len(active_improvements) >= MAX_CONCURRENT_IMPROVEMENTS:
    logger.info("Max concurrent improvements reached, queuing opportunity")
    queue_opportunity(opportunity)
else:
    execute_improvement(opportunity)
```

---

## Configuration Examples

### Basic Configuration

```bash
# .env file
IMPROVEMENT_CYCLE_INTERVAL_HOURS=24
MAX_CONCURRENT_IMPROVEMENTS=3
IMPROVEMENT_QUALITY_THRESHOLD=0.85
IMPROVEMENT_RISK_TOLERANCE=0.1
MONITORING_DURATION_SECONDS=3600
ROLLBACK_DEGRADATION_THRESHOLD=0.10
```

### Conservative Configuration

For production environments with low risk tolerance:

```bash
IMPROVEMENT_CYCLE_INTERVAL_HOURS=168  # Weekly
MAX_CONCURRENT_IMPROVEMENTS=1
IMPROVEMENT_QUALITY_THRESHOLD=0.95
IMPROVEMENT_RISK_TOLERANCE=0.05
MONITORING_DURATION_SECONDS=7200      # 2 hours
ROLLBACK_DEGRADATION_THRESHOLD=0.05   # 5% threshold
```

### Aggressive Configuration

For development environments with high improvement velocity:

```bash
IMPROVEMENT_CYCLE_INTERVAL_HOURS=6    # Every 6 hours
MAX_CONCURRENT_IMPROVEMENTS=5
IMPROVEMENT_QUALITY_THRESHOLD=0.75
IMPROVEMENT_RISK_TOLERANCE=0.2
MONITORING_DURATION_SECONDS=1800      # 30 minutes
ROLLBACK_DEGRADATION_THRESHOLD=0.15   # 15% threshold
```

### Tenant-Specific Configuration

```python
# backend/core/settings.py
TENANT_IMPROVEMENT_CONFIGS = {
    'meetmind-prod': {
        'enabled': True,
        'max_concurrent': 2,
        'risk_tolerance': 0.05,
        'monitoring_duration': 7200
    },
    'agent-svea-prod': {
        'enabled': True,
        'max_concurrent': 1,
        'risk_tolerance': 0.03,  # Very conservative
        'monitoring_duration': 10800  # 3 hours
    },
    'felicias-finance-dev': {
        'enabled': True,
        'max_concurrent': 5,
        'risk_tolerance': 0.2,
        'monitoring_duration': 1800
    }
}
```

---

## Monitoring and Observability

### Cycle Metrics

```python
# Published metrics
metrics = {
    'improvement_cycles_started': 'Count of cycles started',
    'improvement_cycles_completed': 'Count of cycles completed',
    'improvement_cycles_failed': 'Count of cycles failed',
    'improvements_deployed': 'Count of improvements deployed',
    'improvements_rolled_back': 'Count of improvements rolled back',
    'cycle_duration_seconds': 'Duration of complete cycle',
    'opportunities_identified': 'Count of opportunities per cycle',
    'impact_score_total': 'Sum of impact scores deployed',
    'llm_tokens_used': 'LLM tokens consumed per cycle',
    'cloudwatch_api_calls': 'CloudWatch API calls per cycle'
}
```

### CloudWatch Dashboard

Create dashboard to monitor cycles:

```python
# Dashboard widgets
widgets = [
    {
        'type': 'metric',
        'title': 'Improvement Success Rate',
        'metrics': [
            ['SelfBuilding', 'improvements_deployed'],
            ['.', 'improvements_rolled_back']
        ],
        'stat': 'Sum',
        'period': 3600
    },
    {
        'type': 'metric',
        'title': 'Cycle Duration',
        'metrics': [
            ['SelfBuilding', 'cycle_duration_seconds']
        ],
        'stat': 'Average',
        'period': 3600
    },
    {
        'type': 'metric',
        'title': 'Impact Score Trend',
        'metrics': [
            ['SelfBuilding', 'impact_score_total']
        ],
        'stat': 'Sum',
        'period': 86400  # Daily
    }
]
```

### Alerts

```python
# CloudWatch alarms
alarms = [
    {
        'name': 'SelfBuilding-HighFailureRate',
        'metric': 'improvement_cycles_failed',
        'threshold': 3,
        'period': 3600,
        'evaluation_periods': 1,
        'comparison': 'GreaterThanThreshold'
    },
    {
        'name': 'SelfBuilding-HighRollbackRate',
        'metric': 'improvements_rolled_back',
        'threshold': 2,
        'period': 3600,
        'evaluation_periods': 1,
        'comparison': 'GreaterThanThreshold'
    },
    {
        'name': 'SelfBuilding-LongCycleDuration',
        'metric': 'cycle_duration_seconds',
        'threshold': 300,  # 5 minutes
        'period': 300,
        'evaluation_periods': 1,
        'comparison': 'GreaterThanThreshold'
    }
]
```

---

## Best Practices

1. **Start Conservative**: Begin with conservative configuration and gradually increase aggressiveness
2. **Monitor Closely**: Watch first few cycles closely to tune thresholds
3. **Test Locally**: Always test improvement cycle with LocalStack before production
4. **Use Tenant Scoping**: Start with tenant-scoped improvements before system-wide
5. **Review Rollbacks**: Investigate all rollbacks to improve generation quality
6. **Tune Impact Scoring**: Adjust impact score formula based on actual results
7. **Set Appropriate Monitoring Duration**: Balance between fast feedback and statistical significance
8. **Enable Audit Logging**: Always enable audit logging for compliance
9. **Use Feature Flags**: Control cycle execution with feature flags
10. **Document Custom Metrics**: Document any custom metrics used for analysis

## Troubleshooting

See the main troubleshooting guide for common issues and solutions.

## Support

For issues or questions:
- Check logs: `backend/logs/improvement_cycle.log`
- Review metrics: CloudWatch dashboard "SelfBuilding/ImprovementCycle"
- Contact: HappyOS Platform Team
