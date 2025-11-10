# LLM Usage Dashboard

This directory contains Grafana dashboard configurations for monitoring LLM usage across the HappyOS platform.

## Dashboard: llm_usage_dashboard.json

A comprehensive dashboard for monitoring LLM operations including costs, performance, and errors.

### Features

#### Overview Panels
- **Total LLM Requests**: Real-time request rate across all agents
- **Total Cost (24h)**: Daily cost tracking with threshold alerts
- **Cache Hit Rate**: Percentage of requests served from cache
- **Error Rate**: Real-time error monitoring

#### Detailed Metrics
- **Requests per Agent**: Time series showing request volume by agent
- **Cost per Team**: Pie chart breakdown of costs by team/agent
- **Request Latency Distribution**: p50, p90, p99 latency percentiles
- **Token Usage by Model**: Stacked time series of token consumption
- **Cache Performance**: Cache hits vs misses over time
- **Error Rate by Provider**: Errors broken down by provider and type
- **Cost Breakdown by Model**: Bar chart of costs per model
- **Active Requests**: Current in-flight requests by provider
- **Request Success Rate**: Overall success rate percentage

### Installation

#### 1. Import Dashboard to Grafana

```bash
# Using Grafana API
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d @llm_usage_dashboard.json

# Or manually:
# 1. Open Grafana UI
# 2. Go to Dashboards > Import
# 3. Upload llm_usage_dashboard.json
```

#### 2. Configure Prometheus Data Source

Ensure Prometheus is configured as a data source in Grafana:

```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

#### 3. Verify Metrics Collection

Check that LLM metrics are being collected:

```bash
# Query Prometheus directly
curl http://localhost:9090/api/v1/query?query=llm_requests_total

# Or check in Prometheus UI
# http://localhost:9090/graph
```

### Dashboard Variables

The dashboard includes template variables for filtering:

- **agent_id**: Filter by specific agent(s)
- **model**: Filter by LLM model(s)
- **provider**: Filter by provider (openai, bedrock, genai)

### Alerts

The dashboard supports annotations for:

- **Deployments**: Mark deployment events
- **Budget Alerts**: Highlight when budget thresholds are exceeded

### Metrics Reference

All metrics are collected by the `backend/core/llm/metrics.py` module:

#### Counters
- `llm_requests_total{agent_id, model, provider, status}` - Total requests
- `llm_tokens_used_total{agent_id, model, provider, token_type}` - Token usage
- `llm_cache_hits_total{agent_id, model}` - Cache hits
- `llm_cache_misses_total{agent_id, model}` - Cache misses
- `llm_errors_total{agent_id, model, provider, error_type}` - Errors
- `llm_cost_total{agent_id, model, provider}` - Costs in USD

#### Histograms
- `llm_request_duration_seconds{agent_id, model, provider}` - Request latency

#### Gauges
- `llm_active_requests{agent_id, provider}` - Active requests
- `llm_cache_size{tenant_id}` - Cache size

### Cost Tracking

Cost metrics are calculated using the `backend/core/llm/cost_calculator.py` module:

- Pricing data for GPT-4, Claude, Gemini models
- Automatic cost calculation based on token usage
- Daily/weekly/monthly aggregation
- Budget threshold alerts

### Usage Examples

#### View Cost by Agent
```promql
sum(increase(llm_cost_total[24h])) by (agent_id)
```

#### Calculate Cache Hit Rate
```promql
sum(rate(llm_cache_hits_total[5m])) / 
(sum(rate(llm_cache_hits_total[5m])) + sum(rate(llm_cache_misses_total[5m]))) * 100
```

#### Monitor Error Rate
```promql
sum(rate(llm_errors_total[5m])) by (provider, error_type)
```

#### Track Latency Percentiles
```promql
histogram_quantile(0.99, sum(rate(llm_request_duration_seconds_bucket[5m])) by (le))
```

### Troubleshooting

#### No Data Showing

1. Verify Prometheus is scraping metrics:
   ```bash
   curl http://localhost:9090/api/v1/targets
   ```

2. Check that LLM service is recording metrics:
   ```python
   from backend.core.llm import get_llm_metrics
   metrics = get_llm_metrics()
   # Metrics should be initialized
   ```

3. Ensure prometheus_client is installed:
   ```bash
   pip install prometheus-client
   ```

#### High Costs

1. Check cost breakdown by model panel
2. Review requests per agent panel
3. Consider:
   - Switching to cheaper models (GPT-3.5, Claude Haiku, Gemini Flash)
   - Increasing cache TTL
   - Implementing request throttling
   - Setting daily budget limits

#### Low Cache Hit Rate

1. Review cache configuration in `backend/core/llm/cache_manager.py`
2. Increase cache TTL for stable queries
3. Check cache size limits
4. Monitor cache eviction patterns

### Best Practices

1. **Set Budget Alerts**: Configure daily budget thresholds
2. **Monitor Error Rates**: Set up alerts for error rate > 1%
3. **Track Latency**: Alert on p99 latency > 10s
4. **Review Costs Daily**: Check cost breakdown panel daily
5. **Optimize Cache**: Aim for >30% cache hit rate
6. **Balance Models**: Use cheaper models for simple tasks

### Related Documentation

- [LLM Service Documentation](../../../core/llm/README.md)
- [Cost Calculator](../../../core/llm/cost_calculator.py)
- [Metrics Module](../../../core/llm/metrics.py)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
