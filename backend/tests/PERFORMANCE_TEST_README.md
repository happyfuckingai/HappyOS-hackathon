# LLM Performance Tests

This document describes the performance tests for the LLM service and how to run them.

## Overview

The performance tests (`test_llm_performance.py`) measure:

1. **Latency** - Response time for different providers (Bedrock, OpenAI, Gemini)
2. **Concurrent Requests** - System behavior under load (20-100+ simultaneous requests)
3. **Cost per 1000 Requests** - Cost analysis for different models

## Test Coverage

### Provider Latency Tests
- `test_openai_latency` - Tests OpenAI GPT-3.5-turbo latency (10 requests)
- `test_bedrock_latency` - Tests AWS Bedrock Claude-3-haiku latency (10 requests)
- `test_google_genai_latency` - Tests Google Gemini-1.5-flash latency (10 requests)

### Concurrent Request Tests
- `test_concurrent_requests_small_batch` - Tests 20 concurrent requests
- `test_concurrent_requests_large_batch` - Tests 100 concurrent requests

### Cost Analysis Tests
- `test_cost_per_1000_requests_gpt35` - Estimates cost per 1000 requests for GPT-3.5-turbo
- `test_cost_per_1000_requests_gpt4` - Estimates cost per 1000 requests for GPT-4

## Running the Tests

### Prerequisites

1. **API Keys** - Set environment variables for the providers you want to test:
   ```bash
   export OPENAI_API_KEY="sk-..."
   export GOOGLE_API_KEY="..."  # Optional
   ```

2. **AWS Credentials** - For Bedrock tests (optional):
   ```bash
   export AWS_REGION="us-east-1"
   export AWS_ACCESS_KEY_ID="..."
   export AWS_SECRET_ACCESS_KEY="..."
   ```

### Running Tests

**Skip all performance tests (default):**
```bash
pytest backend/tests/test_llm_performance.py -v
```

**Run all performance tests:**
```bash
SKIP_PERFORMANCE_TESTS=0 pytest backend/tests/test_llm_performance.py -v -s
```

**Run specific test:**
```bash
SKIP_PERFORMANCE_TESTS=0 pytest backend/tests/test_llm_performance.py::TestProviderLatency::test_openai_latency -v -s
```

**Run only latency tests:**
```bash
SKIP_PERFORMANCE_TESTS=0 pytest backend/tests/test_llm_performance.py::TestProviderLatency -v -s
```

**Run only cost tests:**
```bash
SKIP_PERFORMANCE_TESTS=0 pytest backend/tests/test_llm_performance.py::TestCostPer1000Requests -v -s
```

## Expected Results

### Latency Benchmarks

Typical latency ranges (may vary based on network, region, and load):

- **OpenAI GPT-3.5-turbo**: 500-2000ms
- **AWS Bedrock Claude-3-haiku**: 800-2500ms
- **Google Gemini-1.5-flash**: 600-2000ms

### Cost Benchmarks

Estimated costs per 1000 requests (100 tokens per request):

- **GPT-3.5-turbo**: $0.50 - $2.00
- **GPT-4**: $5.00 - $15.00
- **Claude-3-haiku**: $0.25 - $1.00
- **Gemini-1.5-flash**: $0.35 - $1.05

### Concurrent Request Performance

- **20 concurrent requests**: Should complete in 5-15 seconds
- **100 concurrent requests**: Should complete in 20-60 seconds
- **Error rate**: Should be < 30% (some rate limiting is expected)

## Cost Warnings

⚠️ **These tests will incur costs!**

Estimated costs per full test run:
- OpenAI tests: ~$0.10 - $0.50
- Bedrock tests: ~$0.05 - $0.20
- Google GenAI tests: ~$0.05 - $0.15

**Total estimated cost per full run: $0.20 - $0.85**

## Interpreting Results

### Latency Metrics

- **Mean**: Average response time
- **Median**: Middle value (50th percentile)
- **P95**: 95th percentile (95% of requests faster than this)
- **P99**: 99th percentile (99% of requests faster than this)

### Performance Indicators

**Good Performance:**
- Mean latency < 2000ms
- P95 latency < 3000ms
- Error rate < 10%
- Throughput > 5 req/s (for concurrent tests)

**Acceptable Performance:**
- Mean latency < 3000ms
- P95 latency < 5000ms
- Error rate < 20%
- Throughput > 2 req/s

**Poor Performance:**
- Mean latency > 5000ms
- P95 latency > 8000ms
- Error rate > 30%
- Throughput < 1 req/s

## Troubleshooting

### Tests are skipped

Make sure to set `SKIP_PERFORMANCE_TESTS=0`:
```bash
SKIP_PERFORMANCE_TESTS=0 pytest backend/tests/test_llm_performance.py -v -s
```

### API Key errors

Ensure environment variables are set:
```bash
echo $OPENAI_API_KEY  # Should print your key
```

### High error rates

- Check API rate limits
- Verify API keys are valid
- Check network connectivity
- Try reducing concurrent request count

### Bedrock not available

- Verify AWS credentials are set
- Check AWS region supports Bedrock
- Verify Bedrock model access is enabled in AWS console

## Adding New Tests

To add new performance tests:

1. Create a new test method in the appropriate class
2. Use the `@skip_perf` decorator
3. Use `PerformanceMetrics` to collect metrics
4. Print summary results
5. Add assertions for minimum performance requirements

Example:
```python
@skip_perf
@pytest.mark.asyncio
async def test_my_performance_test(self, openai_provider):
    """Test description."""
    metrics = PerformanceMetrics()
    
    print(f"\n\n=== My Performance Test ===")
    metrics.start()
    
    # Run test...
    
    metrics.stop()
    summary = metrics.get_summary()
    
    # Print results...
    
    # Assertions
    assert summary['successful_requests'] > 0
```

## CI/CD Integration

Performance tests are skipped by default in CI/CD pipelines. To run them in CI:

```yaml
# .github/workflows/performance-tests.yml
- name: Run Performance Tests
  env:
    SKIP_PERFORMANCE_TESTS: 0
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  run: pytest backend/tests/test_llm_performance.py -v -s
```

## Related Documentation

- [LLM Service README](../core/llm/README.md)
- [Cost Calculator](../core/llm/cost_calculator.py)
- [Provider Documentation](../core/llm/providers/)

