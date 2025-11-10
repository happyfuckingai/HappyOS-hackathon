# LLM Service Load Tests

## Overview

This document describes the load tests for the LLM service, designed to validate production readiness by testing sustained load, circuit breaker behavior, failover times, and memory usage.

## Test Suite

### 1. Sustained Load Test (`test_1000_requests_per_minute`)

**Purpose**: Validate the system can handle 1000 requests per minute sustained load.

**Test Details**:
- Target: 16.67 requests/second
- Duration: 60 seconds
- Total requests: ~1000
- Model: GPT-3.5-turbo (cost-effective)
- Metrics tracked:
  - Throughput (requests/second)
  - Latency (mean, p95, p99)
  - Success rate
  - Memory usage
  - CPU usage

**Success Criteria**:
- ✓ At least 900 requests completed
- ✓ Success rate >= 70%
- ✓ Throughput >= 13.3 RPS (80% of target)
- ✓ P95 latency < 10 seconds

**Expected Cost**: ~$0.50 - $1.00

### 2. Circuit Breaker Test (`test_circuit_breaker_high_error_rate`)

**Purpose**: Validate circuit breaker opens under high error rate and fails over correctly.

**Test Details**:
- Simulates failing AWS Bedrock provider
- Working OpenAI fallback provider
- Circuit breaker threshold: 5 failures
- 20 test requests
- Metrics tracked:
  - Circuit breaker state transitions
  - Provider usage distribution
  - Failover success rate

**Success Criteria**:
- ✓ Bedrock circuit breaker opens after failures
- ✓ OpenAI circuit breaker remains closed
- ✓ Requests successfully fail over to OpenAI
- ✓ No complete system failures

**Expected Cost**: Minimal (uses mocks)

### 3. Failover Time Test (`test_aws_to_local_failover_time`)

**Purpose**: Measure failover time from AWS Bedrock to Local OpenAI.

**Test Details**:
- Simulates AWS Bedrock failure
- Measures time to failover to local provider
- 10 failover attempts
- Metrics tracked:
  - Mean failover time
  - Min/max failover time
  - Failover success rate

**Success Criteria**:
- ✓ At least 8/10 successful failovers
- ✓ Mean failover time < 5 seconds
- ✓ Max failover time < 10 seconds

**Expected Cost**: Minimal (uses mocks)

### 4. Memory Usage Test (`test_memory_usage_under_load`)

**Purpose**: Validate memory usage remains stable under sustained load.

**Test Details**:
- 500 requests total
- Concurrency limit: 50
- Model: GPT-3.5-turbo
- Metrics tracked:
  - Initial memory
  - Peak memory
  - Final memory
  - Memory growth rate

**Success Criteria**:
- ✓ Memory increase < 100%
- ✓ Peak memory < 2x initial memory
- ✓ Memory growth rate < 50% (no leaks)

**Expected Cost**: ~$0.30 - $0.50

### 5. Production Readiness Test (`test_production_readiness_combined`)

**Purpose**: Combined test simulating production conditions.

**Test Details**:
- Duration: 120 seconds (2 minutes)
- Target: 10 requests/second
- Total requests: ~1200
- Model: GPT-3.5-turbo
- Comprehensive metrics collection

**Success Criteria**:
- ✓ Success rate >= 95%
- ✓ Throughput >= 9 RPS (90% of target)
- ✓ P95 latency < 5 seconds
- ✓ P99 latency < 10 seconds

**Expected Cost**: ~$0.60 - $1.00

## Running the Tests

### Prerequisites

1. **Python Dependencies**:
   ```bash
   pip install pytest pytest-asyncio psutil
   ```

2. **Environment Variables**:
   ```bash
   export OPENAI_API_KEY="sk-..."
   export AWS_REGION="us-east-1"  # Optional for AWS tests
   ```

3. **System Requirements**:
   - At least 2GB free RAM
   - Stable internet connection
   - OpenAI API access

### Running All Load Tests

**Default (tests skipped)**:
```bash
pytest backend/tests/test_llm_load.py -v
```

**Enable load tests**:
```bash
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py -v -s
```

### Running Individual Tests

**Sustained load test**:
```bash
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestSustainedLoad::test_1000_requests_per_minute -v -s
```

**Circuit breaker test**:
```bash
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestCircuitBreakerUnderLoad::test_circuit_breaker_high_error_rate -v -s
```

**Failover time test**:
```bash
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestFailoverTime::test_aws_to_local_failover_time -v -s
```

**Memory usage test**:
```bash
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestMemoryUsage::test_memory_usage_under_load -v -s
```

**Production readiness test**:
```bash
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestProductionReadiness::test_production_readiness_combined -v -s
```

## Expected Output

### Sustained Load Test Output

```
=== Testing 1000 Requests/Minute Sustained Load ===
Target: 16.67 requests/second for 60 seconds
  Progress: 100 requests sent, 95 completed, 15.8 RPS
  Progress: 200 requests sent, 192 completed, 16.0 RPS
  ...
  Waiting for remaining requests to complete...

Sustained Load Test Results:
  Duration: 60.23s
  Requests sent: 1000
  Requests completed: 987
  Requests failed: 13
  Success rate: 98.68%
  Throughput: 16.38 requests/second
  Latency (mean): 1234ms
  Latency (p95): 2456ms
  Latency (p99): 3789ms
  Memory (mean): 245.67MB
  Memory (max): 289.34MB
  CPU (mean): 45.2%
  CPU (max): 78.9%
```

### Circuit Breaker Test Output

```
=== Testing Circuit Breaker Under High Error Rate ===
  Phase 1: Triggering circuit breaker with failures...
    Request 0: Bedrock circuit breaker state = CLOSED
    Request 5: Bedrock circuit breaker state = HALF_OPEN
    Request 10: Bedrock circuit breaker state = OPEN
    Request 15: Bedrock circuit breaker state = OPEN

Circuit Breaker Test Results:
  Bedrock state: OPEN
  OpenAI state: CLOSED
  Requests completed: 20
  Requests failed: 0
  Provider usage: {'openai': 15}
  Available providers: ['openai', 'local']
```

### Failover Time Test Output

```
=== Testing AWS to Local Failover Time ===
  Measuring failover times...
    Request 1: Failover time = 87ms, Provider = local
    Request 2: Failover time = 45ms, Provider = local
    Request 3: Failover time = 52ms, Provider = local

Failover Time Results:
  Mean failover time: 63ms
  Min failover time: 45ms
  Max failover time: 127ms
  Successful failovers: 10/10
```

### Memory Usage Test Output

```
=== Testing Memory Usage Under Load ===
  Initial memory: 156.23MB
  Sending 500 requests with concurrency limit of 50...
    Progress: 100/500, Memory: 178.45MB
    Progress: 200/500, Memory: 189.67MB
    Progress: 300/500, Memory: 195.23MB
    Progress: 400/500, Memory: 198.89MB
    Progress: 500/500, Memory: 201.34MB

Memory Usage Test Results:
  Requests completed: 500
  Initial memory: 156.23MB
  Final memory: 201.34MB
  Memory increase: 45.11MB (28.9%)
  Peak memory: 205.67MB
  Mean memory: 192.45MB
  Memory growth rate: 12.3%
```

### Production Readiness Test Output

```
=== Production Readiness Combined Test ===
Running combined test for 120 seconds at 10 RPS
  Progress: 100 requests, 9.8 RPS
  Progress: 200 requests, 9.9 RPS
  ...

Production Readiness Test Results:
  Duration: 120.45s
  Total requests: 1198
  Success rate: 97.83%
  Throughput: 9.95 RPS
  Latency p50: 1123ms
  Latency p95: 2345ms
  Latency p99: 3456ms
  Memory usage: 234.56MB (peak: 267.89MB)
  CPU usage: 42.3% (peak: 76.5%)

Production Readiness Criteria:
  ✓ Success rate >= 95%: True (97.83%)
  ✓ Throughput >= 90% target: True (9.95 RPS)
  ✓ P95 latency < 5s: True (2345ms)
  ✓ P99 latency < 10s: True (3456ms)

  Overall: ✓ READY FOR PRODUCTION
```

## Cost Estimates

### Per Test Run

- **Sustained Load Test**: $0.50 - $1.00
- **Circuit Breaker Test**: $0.00 (uses mocks)
- **Failover Time Test**: $0.00 (uses mocks)
- **Memory Usage Test**: $0.30 - $0.50
- **Production Readiness Test**: $0.60 - $1.00

**Total for full suite**: ~$1.40 - $2.50

### Cost Optimization Tips

1. Use GPT-3.5-turbo instead of GPT-4 for load tests
2. Reduce max_tokens to minimum needed
3. Run tests during off-peak hours
4. Use shorter test durations for initial validation
5. Skip tests that have already passed

## Troubleshooting

### Test Failures

**"Too many requests failed to complete"**:
- Check internet connection
- Verify OpenAI API key is valid
- Check OpenAI API rate limits
- Reduce target RPS

**"Success rate too low"**:
- Check OpenAI API status
- Verify sufficient API quota
- Check for rate limiting
- Review error logs

**"Throughput too low"**:
- Check system resources (CPU, memory)
- Reduce concurrent requests
- Check network latency
- Verify no other heavy processes running

**"P95 latency too high"**:
- Check network connection
- Verify OpenAI API performance
- Reduce request complexity
- Check system load

### Memory Issues

**"Memory usage increased by more than 100%"**:
- Check for memory leaks in code
- Reduce concurrent requests
- Clear caches between tests
- Restart Python process

**"Possible memory leak detected"**:
- Review code for unclosed resources
- Check cache implementation
- Monitor memory over longer duration
- Use memory profiler for detailed analysis

### Circuit Breaker Issues

**"Circuit breaker should be OPEN after failures"**:
- Verify failure threshold is correct
- Check error detection logic
- Review circuit breaker configuration
- Increase number of test failures

**"Should have failed over to OpenAI"**:
- Verify fallback provider is configured
- Check provider priority order
- Review failover logic
- Check provider availability

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: LLM Load Tests

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2 AM
  workflow_dispatch:  # Manual trigger

jobs:
  load-tests:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-asyncio psutil
      
      - name: Run load tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          SKIP_LOAD_TESTS: 0
        run: |
          pytest backend/tests/test_llm_load.py -v -s
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: test-results/
```

### Jenkins Example

```groovy
pipeline {
    agent any
    
    triggers {
        cron('0 2 * * 0')  // Weekly on Sunday at 2 AM
    }
    
    environment {
        OPENAI_API_KEY = credentials('openai-api-key')
        SKIP_LOAD_TESTS = '0'
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r backend/requirements.txt'
                sh 'pip install pytest pytest-asyncio psutil'
            }
        }
        
        stage('Load Tests') {
            steps {
                sh 'pytest backend/tests/test_llm_load.py -v -s --junitxml=test-results/load-tests.xml'
            }
        }
    }
    
    post {
        always {
            junit 'test-results/*.xml'
        }
    }
}
```

## Performance Benchmarks

### Expected Performance (Production)

| Metric | Target | Acceptable | Warning |
|--------|--------|------------|---------|
| Success Rate | >= 99% | >= 95% | < 95% |
| Throughput | >= 20 RPS | >= 15 RPS | < 15 RPS |
| P50 Latency | < 1s | < 2s | > 2s |
| P95 Latency | < 3s | < 5s | > 5s |
| P99 Latency | < 5s | < 10s | > 10s |
| Memory Growth | < 20% | < 50% | > 50% |
| Failover Time | < 1s | < 5s | > 5s |

### Baseline Performance (Development)

Based on initial test runs:

- **Throughput**: 15-20 RPS sustained
- **Latency (p50)**: 800-1200ms
- **Latency (p95)**: 2000-3000ms
- **Latency (p99)**: 3000-5000ms
- **Memory Usage**: 150-250MB baseline, 200-350MB under load
- **Failover Time**: 50-200ms average

## Next Steps

After running load tests:

1. **Review Results**: Analyze metrics and identify bottlenecks
2. **Optimize**: Address performance issues found
3. **Re-test**: Run tests again to validate improvements
4. **Document**: Update benchmarks with new results
5. **Deploy**: Proceed with production deployment if all criteria met

## Related Documentation

- [Performance Test Summary](./PERFORMANCE_TEST_SUMMARY.md)
- [Performance Test README](./PERFORMANCE_TEST_README.md)
- [LLM Service README](../core/llm/README.md)
- [Circuit Breaker Documentation](../core/circuit_breaker/README.md)

## Support

For issues or questions:
- Check troubleshooting section above
- Review test logs for detailed error messages
- Contact DevOps team for infrastructure issues
- Contact AI team for LLM-specific issues
