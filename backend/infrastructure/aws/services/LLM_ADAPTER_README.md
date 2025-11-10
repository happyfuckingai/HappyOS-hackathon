# AWS LLM Adapter

AWS implementation of the LLM service with Bedrock + OpenAI fallback, ElastiCache caching, and DynamoDB usage tracking.

## Overview

The AWS LLM Adapter provides a production-ready LLM service implementation with:

- **Primary Provider**: AWS Bedrock (Claude models)
- **Fallback Provider**: OpenAI (GPT models)
- **Caching**: ElastiCache (Redis) for response caching
- **Resilience**: Circuit breaker pattern for automatic failover
- **Monitoring**: DynamoDB usage logging with cost tracking
- **Tenant Isolation**: Multi-tenant support with isolated cache keys

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AWSLLMAdapter                             │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Bedrock    │  │   OpenAI     │  │ ElastiCache  │      │
│  │   Provider   │  │   Provider   │  │   (Cache)    │      │
│  │  (Primary)   │  │  (Fallback)  │  │              │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         │                  │                  │              │
│  ┌──────▼──────────────────▼──────────────────▼───────┐    │
│  │         Circuit Breaker + Failover Logic           │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│                  ┌────────▼────────┐                        │
│                  │   DynamoDB      │                        │
│                  │  Usage Logs     │                        │
│                  └─────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Features

### 1. Multi-Provider Support

- **AWS Bedrock**: Claude 3 Sonnet, Haiku, Opus, Claude 3.5 Sonnet
- **OpenAI**: GPT-4, GPT-4 Turbo, GPT-3.5 Turbo
- **Automatic Fallback**: Seamlessly switches to OpenAI if Bedrock fails

### 2. Caching

- **ElastiCache Integration**: Redis-based caching for LLM responses
- **Tenant Isolation**: Cache keys scoped by tenant ID
- **Configurable TTL**: Default 1 hour, customizable per request
- **Cache Hit Tracking**: Metrics for cache effectiveness

### 3. Circuit Breaker

- **Automatic Failover**: Switches to fallback provider on repeated failures
- **Self-Healing**: Automatically attempts recovery after timeout
- **Configurable Thresholds**: Customizable failure thresholds and timeouts

### 4. Usage Tracking

- **DynamoDB Logging**: All requests logged to DynamoDB
- **Cost Calculation**: Automatic cost estimation per request
- **Token Tracking**: Input/output token breakdown
- **Performance Metrics**: Latency tracking per request

### 5. Cost Calculator

- **Multi-Provider Pricing**: Supports OpenAI, Bedrock, Google GenAI
- **Accurate Estimates**: Based on current public pricing
- **Cost Comparison**: Compare costs across different models
- **Monthly Projections**: Estimate monthly costs based on usage patterns

## Installation

### Prerequisites

```bash
# Install required Python packages
pip install boto3 redis openai
```

### AWS Resources

1. **AWS Bedrock**: Enable Bedrock in your AWS account
2. **ElastiCache**: Create a Redis cluster (optional, for caching)
3. **DynamoDB**: Create usage logs table (optional, for tracking)

### Create DynamoDB Table

```bash
# Create the LLM usage logs table
python backend/infrastructure/aws/iac/scripts/create_llm_usage_table.py create llm_usage_logs us-east-1

# Describe the table
python backend/infrastructure/aws/iac/scripts/create_llm_usage_table.py describe llm_usage_logs us-east-1

# Delete the table (if needed)
python backend/infrastructure/aws/iac/scripts/create_llm_usage_table.py delete llm_usage_logs us-east-1
```

## Usage

### Basic Usage

```python
from backend.infrastructure.aws.services.llm_adapter import AWSLLMAdapter

# Initialize adapter
llm_service = AWSLLMAdapter(
    region_name="us-east-1",
    elasticache_endpoint="your-cluster.cache.amazonaws.com",
    dynamodb_table_name="llm_usage_logs"
)

# Generate completion
response = await llm_service.generate_completion(
    prompt="Explain quantum computing in simple terms",
    agent_id="my_agent",
    tenant_id="tenant_123",
    model="gpt-4",
    temperature=0.3,
    max_tokens=500,
    response_format="json"
)

print(f"Response: {response['content']}")
print(f"Provider: {response['provider']}")
print(f"Tokens: {response['tokens']}")
print(f"Cost: ${response['estimated_cost']:.6f}")
print(f"Cached: {response['cached']}")
```

### Streaming Completion

```python
# Generate streaming completion
async for chunk in llm_service.generate_streaming_completion(
    prompt="Write a short story about AI",
    agent_id="my_agent",
    tenant_id="tenant_123",
    model="gpt-4",
    temperature=0.7,
    max_tokens=1000
):
    print(chunk, end="", flush=True)
```

### Usage Statistics

```python
# Get usage stats for a tenant
stats = await llm_service.get_usage_stats(
    tenant_id="tenant_123",
    time_range="24h"
)

print(f"Total requests: {stats['total_requests']}")
print(f"Total tokens: {stats['total_tokens']}")
print(f"Total cost: ${stats['total_cost']:.2f}")
print(f"Cache hit rate: {stats['cache_hit_rate']:.1f}%")
print(f"Average latency: {stats['average_latency_ms']:.0f}ms")
```

### Health Check

```python
# Check service health
health = llm_service.get_health_status()

print(f"Service status: {health['status']}")
print(f"Bedrock available: {health['providers']['bedrock']['available']}")
print(f"OpenAI available: {health['providers']['openai']['available']}")
print(f"Cache enabled: {health['cache']['enabled']}")
```

## Cost Calculator

### Calculate Request Cost

```python
from backend.core.llm.cost_calculator import LLMCostCalculator

# Calculate cost for a specific request
cost = LLMCostCalculator.calculate_cost(
    model="gpt-4",
    prompt_tokens=100,
    completion_tokens=50
)
print(f"Cost: ${cost:.6f}")  # $0.006000
```

### Compare Model Costs

```python
# Compare costs across models
models = ["gpt-4", "gpt-3.5-turbo", "claude-3-haiku", "gemini-1.5-flash"]
costs = LLMCostCalculator.compare_model_costs(models, 100, 50)

for model, cost in sorted(costs.items(), key=lambda x: x[1]):
    print(f"{model}: ${cost:.6f}")

# Find cheapest model
cheapest_model, cheapest_cost = LLMCostCalculator.get_cheapest_model(models, 100, 50)
print(f"Cheapest: {cheapest_model} at ${cheapest_cost:.6f}")
```

### Estimate Monthly Costs

```python
# Estimate monthly costs
estimate = LLMCostCalculator.estimate_monthly_cost(
    model="gpt-4",
    requests_per_day=1000,
    avg_prompt_tokens=100,
    avg_completion_tokens=50
)

print(f"Daily cost: ${estimate['daily_cost']:.2f}")
print(f"Monthly cost: ${estimate['monthly_cost']:.2f}")
```

## Configuration

### Environment Variables

```bash
# Required for OpenAI fallback
export OPENAI_API_KEY="sk-..."

# AWS credentials (if not using IAM role)
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
```

### Initialization Options

```python
llm_service = AWSLLMAdapter(
    region_name="us-east-1",              # AWS region
    elasticache_endpoint=None,            # Optional: Redis endpoint
    dynamodb_table_name="llm_usage_logs"  # Optional: DynamoDB table
)
```

## Model Support

### AWS Bedrock Models

- `claude-3-sonnet` → `anthropic.claude-3-sonnet-20240229-v1:0`
- `claude-3-haiku` → `anthropic.claude-3-haiku-20240307-v1:0`
- `claude-3-opus` → `anthropic.claude-3-opus-20240229-v1:0`
- `claude-3.5-sonnet` → `anthropic.claude-3-5-sonnet-20240620-v1:0`
- `claude-2` → `anthropic.claude-v2`
- `claude-2.1` → `anthropic.claude-v2:1`

### OpenAI Models

- `gpt-4` → GPT-4
- `gpt-4-turbo` → GPT-4 Turbo Preview
- `gpt-3.5-turbo` → GPT-3.5 Turbo

## Pricing (as of 2024)

### OpenAI

| Model | Input (per 1k tokens) | Output (per 1k tokens) |
|-------|----------------------|------------------------|
| GPT-4 | $0.03 | $0.06 |
| GPT-4 Turbo | $0.01 | $0.03 |
| GPT-3.5 Turbo | $0.0005 | $0.0015 |

### AWS Bedrock (Claude)

| Model | Input (per 1k tokens) | Output (per 1k tokens) |
|-------|----------------------|------------------------|
| Claude 3 Opus | $0.015 | $0.075 |
| Claude 3 Sonnet | $0.003 | $0.015 |
| Claude 3 Haiku | $0.00025 | $0.00125 |

### Google GenAI

| Model | Input (per 1k tokens) | Output (per 1k tokens) |
|-------|----------------------|------------------------|
| Gemini 1.5 Pro | $0.0035 | $0.0105 |
| Gemini 1.5 Flash | $0.00035 | $0.00105 |

## Testing

### Run Cost Calculator Tests

```bash
python3 backend/infrastructure/aws/services/test_llm_adapter_simple.py
```

Expected output:
```
============================================================
LLM Cost Calculator - Verification Tests
============================================================

=== Testing Cost Calculator ===
✓ GPT-4 cost (100 input + 50 output tokens): $0.006000
✓ Claude-3-Sonnet cost (100 input + 50 output tokens): $0.001050
✓ Gemini-1.5-Flash cost (100 input + 50 output tokens): $0.000088
...
✓ All tests passed successfully!
```

## Monitoring

### DynamoDB Schema

The usage logs table stores:

- `log_id` (PK): `{tenant_id}#{agent_id}#{timestamp}`
- `tenant_id`: Tenant identifier
- `agent_id`: Agent identifier
- `timestamp`: ISO 8601 timestamp
- `model`: Model used
- `provider`: Provider used (bedrock/openai)
- `tokens_used`: Total tokens
- `prompt_tokens`: Input tokens
- `completion_tokens`: Output tokens
- `estimated_cost`: Cost in USD
- `latency_ms`: Request latency
- `cached`: Whether response was cached
- `success`: Whether request succeeded

### Global Secondary Indexes

1. **tenant_id-timestamp-index**: Query by tenant and time range
2. **agent_id-timestamp-index**: Query by agent and time range

## Error Handling

The adapter handles errors gracefully:

1. **Bedrock Failure**: Automatically falls back to OpenAI
2. **Circuit Breaker Open**: Returns error immediately, prevents cascading failures
3. **Cache Failure**: Continues without caching, logs warning
4. **Logging Failure**: Continues without logging, doesn't fail request

## Performance

- **Cache Hit**: < 10ms response time
- **Bedrock Call**: 500-2000ms typical
- **OpenAI Call**: 500-3000ms typical
- **Failover Time**: < 100ms to switch providers

## Best Practices

1. **Enable Caching**: Use ElastiCache for production deployments
2. **Monitor Costs**: Set up alerts on DynamoDB usage stats
3. **Use Appropriate Models**: Choose cheaper models for simple tasks
4. **Set Reasonable Timeouts**: Configure circuit breaker thresholds
5. **Tenant Isolation**: Always provide tenant_id for proper isolation

## Troubleshooting

### Bedrock Not Available

```python
# Check if Bedrock is available
if not llm_service.bedrock_provider.is_available():
    print("Bedrock not available. Check AWS credentials and region.")
```

### High Costs

```python
# Analyze usage patterns
stats = await llm_service.get_usage_stats(time_range="7d")
print(f"Average cost per request: ${stats['average_cost_per_request']:.6f}")

# Consider switching to cheaper models
cheapest = LLMCostCalculator.get_cheapest_model(
    ["gpt-4", "claude-3-haiku", "gemini-1.5-flash"],
    avg_prompt_tokens,
    avg_completion_tokens
)
```

### Circuit Breaker Always Open

```python
# Check circuit breaker state
health = llm_service.get_health_status()
print(f"Bedrock circuit breaker: {health['providers']['bedrock']['circuit_breaker_state']}")

# Force close if needed (for testing)
llm_service.bedrock_circuit_breaker.force_close()
```

## Future Enhancements

- [ ] Support for more Bedrock models (Titan, Jurassic)
- [ ] Streaming support for Bedrock
- [ ] Advanced caching strategies (semantic caching)
- [ ] Cost optimization recommendations
- [ ] Real-time cost alerts
- [ ] Multi-region failover

## License

Part of the HappyOS project.
