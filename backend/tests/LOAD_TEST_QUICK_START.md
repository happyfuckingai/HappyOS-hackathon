# Load Test Quick Start Guide

## TL;DR

```bash
# Verify tests are available (should show 5 tests skipped)
pytest backend/tests/test_llm_load.py -v

# Run all load tests (costs ~$1.40-$2.50)
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py -v -s

# Run only free tests (circuit breaker + failover)
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestCircuitBreakerUnderLoad -v -s
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestFailoverTime -v -s
```

## Prerequisites

```bash
# 1. Install dependencies
pip install pytest pytest-asyncio psutil

# 2. Set API key (for tests that use real APIs)
export OPENAI_API_KEY="sk-..."

# 3. Verify tests are collected
pytest backend/tests/test_llm_load.py --collect-only
```

## Test Overview

| Test | Duration | Cost | Description |
|------|----------|------|-------------|
| Sustained Load | ~60s | $0.50-$1.00 | 1000 requests/minute |
| Circuit Breaker | ~5s | $0.00 | Error handling |
| Failover Time | ~2s | $0.00 | AWS→Local failover |
| Memory Usage | ~30s | $0.30-$0.50 | Memory stability |
| Production Ready | ~120s | $0.60-$1.00 | Combined validation |

## Quick Commands

### Verify Setup
```bash
# Check tests are collected
pytest backend/tests/test_llm_load.py --collect-only

# Should show: collected 5 items
```

### Run Free Tests Only
```bash
# Circuit breaker test (no cost)
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestCircuitBreakerUnderLoad::test_circuit_breaker_high_error_rate -v -s

# Failover test (no cost)
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestFailoverTime::test_aws_to_local_failover_time -v -s
```

### Run Individual Paid Tests
```bash
# Sustained load test (~$0.50-$1.00)
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestSustainedLoad::test_1000_requests_per_minute -v -s

# Memory test (~$0.30-$0.50)
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestMemoryUsage::test_memory_usage_under_load -v -s

# Production readiness test (~$0.60-$1.00)
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py::TestProductionReadiness::test_production_readiness_combined -v -s
```

### Run All Tests
```bash
# Full suite (~$1.40-$2.50)
SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py -v -s
```

## Expected Output

### Sustained Load Test
```
=== Testing 1000 Requests/Minute Sustained Load ===
Target: 16.67 requests/second for 60 seconds
  Progress: 100 requests sent, 95 completed, 15.8 RPS
  Progress: 200 requests sent, 192 completed, 16.0 RPS
  ...

Sustained Load Test Results:
  Duration: 60.23s
  Requests sent: 1000
  Requests completed: 987
  Success rate: 98.68%
  Throughput: 16.38 requests/second
  Latency (mean): 1234ms
  Latency (p95): 2456ms
  Memory (mean): 245.67MB
  CPU (mean): 45.2%
```

### Circuit Breaker Test
```
=== Testing Circuit Breaker Under High Error Rate ===
  Phase 1: Triggering circuit breaker with failures...
    Request 0: Circuit breaker state = CLOSED, failures = 0
    Request 5: Circuit breaker state = OPEN, failures = 5

Circuit Breaker Test Results:
  Final state: OPEN
  Requests completed: 20
  Provider usage: {'fallback': 15}
```

### Failover Time Test
```
=== Testing AWS to Local Failover Time ===
  Measuring failover times...
    Request 1: Failover time = 87ms, Provider = local
    Request 2: Failover time = 45ms, Provider = local

Failover Time Results:
  Mean failover time: 63ms
  Min failover time: 45ms
  Max failover time: 127ms
  Successful failovers: 10/10
```

## Troubleshooting

### Tests are skipped
**Problem**: All tests show SKIPPED
**Solution**: Set `SKIP_LOAD_TESTS=0` environment variable

### Import errors
**Problem**: ModuleNotFoundError
**Solution**: Install dependencies: `pip install pytest pytest-asyncio psutil`

### API key errors
**Problem**: "OPENAI_API_KEY not set"
**Solution**: Export API key: `export OPENAI_API_KEY="sk-..."`

### High costs
**Problem**: Tests are expensive
**Solution**: Run free tests only (circuit breaker + failover)

## Success Criteria

### Sustained Load
- ✓ At least 900 requests completed
- ✓ Success rate >= 70%
- ✓ Throughput >= 13.3 RPS

### Circuit Breaker
- ✓ Circuit opens after failures
- ✓ Fallback provider works

### Failover Time
- ✓ Mean failover < 5 seconds
- ✓ At least 8/10 successful

### Memory Usage
- ✓ Memory increase < 100%
- ✓ No memory leaks

### Production Readiness
- ✓ Success rate >= 95%
- ✓ P95 latency < 5 seconds

## Next Steps

1. **Run free tests first** to verify setup
2. **Run one paid test** to validate API access
3. **Run full suite** when ready for production validation
4. **Review results** and optimize as needed

## Documentation

- **Full Guide**: [LOAD_TEST_README.md](./LOAD_TEST_README.md)
- **Implementation**: [LOAD_TEST_SUMMARY.md](./LOAD_TEST_SUMMARY.md)
- **Test File**: [test_llm_load.py](./test_llm_load.py)

## Support

For issues:
1. Check [LOAD_TEST_README.md](./LOAD_TEST_README.md) troubleshooting section
2. Review test output for error messages
3. Verify API keys and dependencies
4. Check system resources (memory, CPU)
