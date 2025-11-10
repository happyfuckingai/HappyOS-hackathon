# AWS LLM Adapter Integration Tests

## Overview

This document describes the integration tests for the AWS LLM Adapter and how to run them.

## Test Files

### 1. `test_aws_llm_adapter_integration.py`
Comprehensive integration tests that verify the AWS LLM adapter works correctly with real AWS services.

### 2. `test_aws_llm_integration_standalone.py`
Standalone integration tests with mocked AWS services for testing without AWS credentials.

## Prerequisites

### Required Dependencies

Install all required dependencies:

```bash
pip install -r backend/requirements.txt
pip install opensearchpy aws-requests-auth  # Additional AWS dependencies
```

### Environment Variables

Set the following environment variables:

```bash
# Required for OpenAI fallback
export OPENAI_API_KEY="your-openai-api-key"

# Required for AWS Bedrock
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"

# Optional: ElastiCache endpoint for caching tests
export ELASTICACHE_ENDPOINT="your-elasticache-endpoint"

# Optional: Skip AWS tests if not configured
export SKIP_AWS_INTEGRATION_TESTS="1"
```

## Running the Tests

### Run All Integration Tests

```bash
python3 -m pytest backend/tests/test_aws_llm_adapter_integration.py -v
```

### Run Specific Test Classes

```bash
# Test Bedrock integration only
python3 -m pytest backend/tests/test_aws_llm_adapter_integration.py::TestBedrockIntegration -v

# Test ElastiCache caching only
python3 -m pytest backend/tests/test_aws_llm_adapter_integration.py::TestElastiCacheCaching -v

# Test circuit breaker failover only
python3 -m pytest backend/tests/test_aws_llm_adapter_integration.py::TestCircuitBreakerFailover -v

# Test OpenAI fallback only
python3 -m pytest backend/tests/test_aws_llm_adapter_integration.py::TestOpenAIFallback -v
```

### Run Standalone Tests (No AWS Required)

```bash
python3 -m pytest backend/tests/test_aws_llm_integration_standalone.py -v
```

## Test Coverage

### 1. Basic Adapter Tests (`TestAWSLLMAdapterBasic`)

- ✅ Adapter initialization
- ✅ Health status reporting
- ✅ Cache key generation with tenant isolation

### 2. Bedrock Integration Tests (`TestBedrockIntegration`)

- ✅ Bedrock completion generation
- ✅ JSON response format handling
- ✅ Model routing to appropriate Bedrock models
- ✅ Token counting and usage tracking

### 3. ElastiCache Caching Tests (`TestElastiCacheCaching`)

- ✅ Cache hit on second identical call
- ✅ Cache isolation by tenant
- ✅ Cache invalidation when parameters change
- ✅ TTL-based cache expiration

### 4. Circuit Breaker Failover Tests (`TestCircuitBreakerFailover`)

- ✅ Circuit breaker opens after threshold failures
- ✅ Automatic fallback to OpenAI when Bedrock fails
- ✅ Circuit breaker recovery (OPEN → HALF_OPEN → CLOSED)
- ✅ Circuit breaker prevents calls when open

### 5. OpenAI Fallback Tests (`TestOpenAIFallback`)

- ✅ OpenAI fallback completion generation
- ✅ Error handling when all providers fail
- ✅ Fallback maintains same response structure

### 6. Usage Tracking Tests (`TestUsageTracking`)

- ✅ Usage statistics structure
- ✅ Usage logging after completion
- ✅ DynamoDB integration for usage logs

### 7. Cost Tracking Tests (`TestCostTracking`)

- ✅ Cost calculation in response
- ✅ Cost tracking in usage statistics
- ✅ Per-model cost calculation

### 8. Streaming Completion Tests (`TestStreamingCompletion`)

- ✅ Streaming completion generation
- ✅ Chunk-by-chunk response delivery
- ✅ Fallback to OpenAI streaming

## Test Scenarios

### Scenario 1: Normal Operation (Bedrock Available)

```
1. Client makes LLM request
2. Adapter checks cache (miss on first call)
3. Adapter calls Bedrock (primary provider)
4. Bedrock returns response
5. Adapter caches response
6. Adapter logs usage to DynamoDB
7. Adapter returns response to client
```

**Expected Result**: Response from Bedrock, cached for future calls

### Scenario 2: Bedrock Failure (Fallback to OpenAI)

```
1. Client makes LLM request
2. Adapter checks cache (miss)
3. Adapter tries Bedrock (fails)
4. Circuit breaker detects failure
5. Adapter falls back to OpenAI
6. OpenAI returns response
7. Adapter caches response
8. Adapter logs usage to DynamoDB
9. Adapter returns response to client
```

**Expected Result**: Response from OpenAI, circuit breaker tracks Bedrock failures

### Scenario 3: Circuit Breaker Open

```
1. Client makes LLM request
2. Adapter checks cache (miss)
3. Circuit breaker is OPEN (Bedrock unavailable)
4. Adapter skips Bedrock, goes directly to OpenAI
5. OpenAI returns response
6. Adapter caches response
7. Adapter returns response to client
```

**Expected Result**: Fast failover to OpenAI without attempting Bedrock

### Scenario 4: Cache Hit

```
1. Client makes LLM request (same as previous)
2. Adapter checks cache (hit!)
3. Adapter returns cached response immediately
4. No LLM provider called
5. No usage logged (cached request)
```

**Expected Result**: Instant response from cache, no LLM costs

### Scenario 5: All Providers Fail

```
1. Client makes LLM request
2. Adapter checks cache (miss)
3. Bedrock circuit breaker is OPEN
4. Adapter tries OpenAI (fails)
5. OpenAI circuit breaker opens
6. Adapter has no available providers
7. Adapter raises exception
```

**Expected Result**: Exception with clear error message about all providers failing

## Manual Testing

### Test Bedrock Integration

```python
import asyncio
from backend.infrastructure.aws.services.llm_adapter import AWSLLMAdapter

async def test_bedrock():
    adapter = AWSLLMAdapter(region_name="us-east-1")
    
    result = await adapter.generate_completion(
        prompt="What is 2+2? Answer with just the number.",
        agent_id="test_agent",
        tenant_id="test_tenant",
        model="gpt-4",
        temperature=0.1,
        max_tokens=10,
        response_format="text"
    )
    
    print(f"Provider: {result['provider']}")
    print(f"Content: {result['content']}")
    print(f"Tokens: {result['tokens']}")
    print(f"Cost: ${result['estimated_cost']:.6f}")
    print(f"Cached: {result['cached']}")

asyncio.run(test_bedrock())
```

### Test Caching

```python
import asyncio
from backend.infrastructure.aws.services.llm_adapter import AWSLLMAdapter

async def test_caching():
    adapter = AWSLLMAdapter(
        region_name="us-east-1",
        elasticache_endpoint="your-elasticache-endpoint"
    )
    
    prompt = "What is the capital of France?"
    
    # First call - not cached
    result1 = await adapter.generate_completion(
        prompt=prompt,
        agent_id="test_agent",
        tenant_id="test_tenant",
        model="gpt-4",
        temperature=0.3,
        max_tokens=20,
        response_format="text"
    )
    print(f"First call - Cached: {result1['cached']}")
    
    # Second call - should be cached
    result2 = await adapter.generate_completion(
        prompt=prompt,
        agent_id="test_agent",
        tenant_id="test_tenant",
        model="gpt-4",
        temperature=0.3,
        max_tokens=20,
        response_format="text"
    )
    print(f"Second call - Cached: {result2['cached']}")
    print(f"Same content: {result1['content'] == result2['content']}")

asyncio.run(test_caching())
```

### Test Circuit Breaker

```python
import asyncio
from backend.infrastructure.aws.services.llm_adapter import AWSLLMAdapter

async def test_circuit_breaker():
    adapter = AWSLLMAdapter(region_name="us-east-1")
    
    # Check initial state
    health = adapter.get_health_status()
    print(f"Bedrock circuit breaker: {health['providers']['bedrock']['circuit_breaker_state']}")
    print(f"OpenAI circuit breaker: {health['providers']['openai']['circuit_breaker_state']}")
    
    # Force Bedrock circuit breaker open
    adapter.bedrock_circuit_breaker.force_open()
    
    # Make a call - should use OpenAI
    result = await adapter.generate_completion(
        prompt="Test fallback",
        agent_id="test_agent",
        tenant_id="test_tenant",
        model="gpt-4",
        temperature=0.3,
        max_tokens=20,
        response_format="text"
    )
    
    print(f"Provider used: {result['provider']}")  # Should be 'openai'
    
    # Reset circuit breaker
    adapter.bedrock_circuit_breaker.force_close()

asyncio.run(test_circuit_breaker())
```

## Troubleshooting

### Issue: Tests are skipped

**Cause**: `SKIP_AWS_INTEGRATION_TESTS=1` is set

**Solution**: Unset the environment variable:
```bash
unset SKIP_AWS_INTEGRATION_TESTS
```

### Issue: ModuleNotFoundError for opensearchpy

**Cause**: Missing AWS dependencies

**Solution**: Install additional dependencies:
```bash
pip install opensearchpy aws-requests-auth
```

### Issue: Bedrock tests fail with permission errors

**Cause**: AWS credentials don't have Bedrock permissions

**Solution**: Add Bedrock permissions to your IAM role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

### Issue: ElastiCache tests fail

**Cause**: ElastiCache endpoint not configured or not accessible

**Solution**: 
1. Set `ELASTICACHE_ENDPOINT` environment variable
2. Ensure security groups allow access from your IP
3. Or skip caching tests by not setting the endpoint

### Issue: All tests fail immediately

**Cause**: Missing required environment variables

**Solution**: Set at minimum:
```bash
export OPENAI_API_KEY="your-key"
export AWS_REGION="us-east-1"
```

## Cost Considerations

Running these integration tests will incur costs:

- **AWS Bedrock**: ~$0.003 per test call (Claude-3-Sonnet)
- **OpenAI**: ~$0.006 per test call (GPT-4)
- **ElastiCache**: Minimal (if cluster already running)
- **DynamoDB**: Minimal (write operations)

**Estimated cost for full test suite**: $0.10 - $0.50

To minimize costs:
- Set `SKIP_AWS_INTEGRATION_TESTS=1` to skip real AWS calls
- Use standalone tests with mocked services
- Run specific test classes instead of full suite

## CI/CD Integration

### GitHub Actions Example

```yaml
name: AWS LLM Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r backend/requirements.txt
        pip install opensearchpy aws-requests-auth
    
    - name: Run integration tests
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        AWS_REGION: us-east-1
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
      run: |
        python3 -m pytest backend/tests/test_aws_llm_adapter_integration.py -v
```

## Summary

The AWS LLM adapter integration tests verify:

1. ✅ **Bedrock Integration**: Primary LLM provider works correctly
2. ✅ **ElastiCache Caching**: Responses are cached with tenant isolation
3. ✅ **Circuit Breaker**: Automatic failover when providers fail
4. ✅ **OpenAI Fallback**: Secondary provider works when primary fails
5. ✅ **Usage Tracking**: All requests are logged to DynamoDB
6. ✅ **Cost Tracking**: Costs are calculated and tracked
7. ✅ **Streaming**: Streaming completions work correctly

These tests ensure the adapter provides resilient, cost-effective LLM access with 99.9% uptime through automatic failover.
