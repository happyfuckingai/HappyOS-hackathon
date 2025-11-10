# LLM Monitoring and Observability Implementation

This document summarizes the monitoring and observability implementation for the LLM service.

## Overview

Complete monitoring solution for LLM operations including:
- Prometheus metrics collection
- Cost tracking with budget alerts
- Grafana dashboard for visualization

## Components Implemented

### 1. Prometheus Metrics (`backend/core/llm/metrics.py`)

Comprehensive metrics collection for LLM operations:

#### Counters
- `llm_requests_total` - Total requests by agent, model, provider, status
- `llm_tokens_used_total` - Token usage by agent, model, provider, token type
- `llm_cache_hits_total` - Cache hits by agent, model
- `llm_cache_misses_total` - Cache misses by agent, model
- `llm_errors_total` - Errors by agent, model, provider, error type
- `llm_cost_total` - Costs in USD by agent, model, provider

#### Histograms
- `llm_request_duration_seconds` - Request latency distribution

#### Gauges
- `llm_active_requests` - Current active requests by agent, provider
- `llm_cache_size` - Cache size by tenant

#### Usage Example
```python
from backend.core.llm import get_llm_metrics

metrics = get_llm_metrics()

# Record a complete request
metrics.record_request(
    agent_id="meetmind.coordinator",
    model="gpt-4",
    provider="openai",
    status="success",
    duration_seconds=2.5,
    prompt_tokens=100,
    completion_tokens=200,
    cached=False,
    cost=0.015
)

# Record an error
metrics.record_error(
    agent_id="agent.svea.pm",
    model="gpt-4",
    provider="openai",
    error_type="rate_limit"
)

# Track active requests
with metrics.track_request("agent.id", "gpt-4", "openai"):
    # Make LLM call
    pass
```

### 2. Cost Tracking (`backend/core/llm/cost_calculator.py`)

Enhanced cost calculator with tracking and aggregation:

#### Features
- Token-to-cost mapping for GPT-4, Claude, Gemini models
- Daily cost aggregation
- Weekly and monthly summaries
- Budget alert threshold checking
- Cost history management

#### New Classes
- `CostEntry` - Single cost record
- `DailyCostSummary` - Daily aggregated costs
- `CostTracker` - Main tracking class

#### Usage Example
```python
from backend.core.llm import get_cost_tracker

# Initialize with daily budget
tracker = get_cost_tracker(daily_budget=100.0)

# Record a cost
cost = tracker.record_cost(
    agent_id="meetmind.coordinator",
    model="gpt-4",
    provider="openai",
    prompt_tokens=100,
    completion_tokens=200
)

# Get daily summary
summary = tracker.get_daily_summary()
print(f"Today's cost: ${summary.total_cost}")
print(f"Requests: {summary.total_requests}")
print(f"Cost by agent: {summary.cost_by_agent}")

# Check budget threshold
status = tracker.check_budget_threshold(threshold_percent=80.0)
if status["is_over_threshold"]:
    print(f"Warning: {status['percent_used']}% of budget used")

# Get weekly summary
weekly = tracker.get_weekly_summary()
print(f"Week cost: ${weekly['total_cost']}")

# Get monthly summary
monthly = tracker.get_monthly_summary()
print(f"Month cost: ${monthly['total_cost']}")
```

### 3. Grafana Dashboard (`backend/modules/observability/dashboards/llm_usage_dashboard.json`)

Comprehensive dashboard with 13 panels:

#### Overview Panels
1. Total LLM Requests (stat)
2. Total Cost 24h (stat with thresholds)
3. Cache Hit Rate (gauge)
4. Error Rate (stat with thresholds)

#### Detailed Analysis
5. Requests per Agent (time series)
6. Cost per Team (pie chart)
7. Request Latency Distribution (p50, p90, p99)
8. Token Usage by Model (stacked time series)
9. Cache Performance (hits vs misses)
10. Error Rate by Provider (time series)
11. Cost Breakdown by Model (bar gauge)
12. Active Requests (time series)
13. Request Success Rate (time series)

#### Template Variables
- `agent_id` - Filter by agent
- `model` - Filter by model
- `provider` - Filter by provider

#### Annotations
- Deployments
- Budget alerts

## Integration with LLM Service

The monitoring components integrate seamlessly with the LLM service:

```python
from backend.core.llm import get_llm_metrics, get_cost_tracker, LLMCostCalculator

class MyLLMService:
    def __init__(self):
        self.metrics = get_llm_metrics()
        self.cost_tracker = get_cost_tracker(daily_budget=100.0)
    
    async def generate_completion(self, prompt, agent_id, model, provider):
        start_time = time.time()
        
        try:
            # Track active request
            self.metrics.increment_active_requests(agent_id, provider)
            
            # Make LLM call
            response = await self._call_llm(prompt, model, provider)
            
            # Calculate metrics
            duration = time.time() - start_time
            cost = LLMCostCalculator.calculate_cost(
                model,
                response.prompt_tokens,
                response.completion_tokens
            )
            
            # Record metrics
            self.metrics.record_request(
                agent_id=agent_id,
                model=model,
                provider=provider,
                status="success",
                duration_seconds=duration,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                cached=False,
                cost=cost
            )
            
            # Track cost
            self.cost_tracker.record_cost(
                agent_id=agent_id,
                model=model,
                provider=provider,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens
            )
            
            return response
            
        except Exception as e:
            # Record error
            self.metrics.record_error(
                agent_id=agent_id,
                model=model,
                provider=provider,
                error_type=type(e).__name__
            )
            raise
        
        finally:
            # Decrement active requests
            self.metrics.decrement_active_requests(agent_id, provider)
```

## Deployment

### 1. Install Dependencies

```bash
pip install prometheus-client
```

### 2. Expose Metrics Endpoint

Add to FastAPI app:

```python
from backend.core.llm import get_llm_metrics
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@app.get("/metrics")
async def metrics():
    metrics = get_llm_metrics()
    return Response(
        content=metrics.get_metrics(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### 3. Configure Prometheus

Add scrape config:

```yaml
scrape_configs:
  - job_name: 'happyos-backend'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### 4. Import Grafana Dashboard

```bash
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d @backend/modules/observability/dashboards/llm_usage_dashboard.json
```

## Monitoring Best Practices

### 1. Set Budget Alerts
```python
tracker = get_cost_tracker(daily_budget=100.0)
```

### 2. Monitor Key Metrics
- Request success rate > 99%
- Cache hit rate > 30%
- p99 latency < 10s
- Error rate < 1%

### 3. Cost Optimization
- Use cheaper models for simple tasks
- Increase cache TTL for stable queries
- Implement request throttling
- Review daily cost breakdown

### 4. Regular Reviews
- Check daily cost summary
- Review error patterns
- Analyze latency trends
- Optimize cache performance

## Files Created/Modified

### New Files
- `backend/core/llm/metrics.py` - Prometheus metrics
- `backend/modules/observability/dashboards/llm_usage_dashboard.json` - Grafana dashboard
- `backend/modules/observability/dashboards/README.md` - Dashboard documentation

### Modified Files
- `backend/core/llm/cost_calculator.py` - Added CostTracker, daily aggregation, budget alerts
- `backend/core/llm/__init__.py` - Exported new classes

## Testing

### Test Metrics Collection
```python
from backend.core.llm import get_llm_metrics

metrics = get_llm_metrics()
metrics.record_request(
    agent_id="test.agent",
    model="gpt-4",
    provider="openai",
    status="success",
    duration_seconds=1.5,
    prompt_tokens=100,
    completion_tokens=200,
    cached=False,
    cost=0.015
)

# Verify metrics are recorded
# Check Prometheus endpoint: http://localhost:8000/metrics
```

### Test Cost Tracking
```python
from backend.core.llm import get_cost_tracker

tracker = get_cost_tracker(daily_budget=100.0)
cost = tracker.record_cost(
    agent_id="test.agent",
    model="gpt-4",
    provider="openai",
    prompt_tokens=100,
    completion_tokens=200
)

summary = tracker.get_daily_summary()
assert summary.total_cost > 0
assert summary.total_requests == 1

status = tracker.check_budget_threshold()
print(f"Budget status: {status}")
```

## Requirements Met

✅ **5.8** - Monitoring och Observability
- ✅ Prometheus metrics för LLM (counters, histograms, gauges)
- ✅ Cost tracking med daily/weekly/monthly aggregation
- ✅ Budget alert threshold checking
- ✅ Grafana dashboard med 13 panels
- ✅ Cache hit rate monitoring
- ✅ Error tracking by type
- ✅ Latency distribution tracking
- ✅ Cost breakdown by agent/model/provider

## Next Steps

1. Integrate metrics into AWS LLM Adapter
2. Integrate metrics into Local LLM Service
3. Add metrics to all agent LLM calls
4. Set up Prometheus in production
5. Configure Grafana alerts
6. Set production budget limits
7. Monitor and optimize based on metrics
