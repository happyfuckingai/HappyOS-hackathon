"""
Simple unit test for LLM circuit breaker without external dependencies.
"""

import asyncio
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import directly to avoid fallback_manager issue
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core', 'circuit_breaker'))

from llm_circuit_breaker import (
    LLMCircuitBreaker,
    LLMProviderType,
    LLMProviderHealth
)

# Import CircuitState from interfaces
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core'))
from interfaces import CircuitState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_circuit_breaker_initialization():
    """Test LLM circuit breaker initialization."""
    logger.info("Test 1: Circuit breaker initialization")
    
    cb = LLMCircuitBreaker(
        service_name="test_llm",
        failure_threshold=3,
        timeout_seconds=30
    )
    
    # Check providers are initialized
    assert len(cb._provider_breakers) == len(LLMProviderType), "Not all providers initialized"
    assert len(cb._provider_health) == len(LLMProviderType), "Not all provider health initialized"
    
    # Check all providers start in CLOSED state
    for provider in LLMProviderType:
        state = cb.get_provider_state(provider)
        assert state == CircuitState.CLOSED, f"Provider {provider.value} not in CLOSED state"
    
    logger.info("✓ Circuit breaker initialized correctly")
    return True


async def test_provider_health_tracking():
    """Test provider health tracking."""
    logger.info("\nTest 2: Provider health tracking")
    
    cb = LLMCircuitBreaker(service_name="test_llm")
    
    # Simulate success
    await cb._on_provider_success(LLMProviderType.OPENAI, latency_ms=150)
    
    health = cb.get_provider_health(LLMProviderType.OPENAI)
    assert health.successful_requests == 1, "Success not tracked"
    assert health.total_requests == 1, "Total requests not tracked"
    assert health.average_latency_ms == 150, "Latency not tracked"
    assert health.consecutive_failures == 0, "Consecutive failures should be 0"
    
    logger.info("✓ Provider health tracking works")
    return True


async def test_provider_failure_tracking():
    """Test provider failure tracking."""
    logger.info("\nTest 3: Provider failure tracking")
    
    cb = LLMCircuitBreaker(
        service_name="test_llm",
        failure_threshold=2
    )
    
    # Simulate failures
    await cb._on_provider_failure(LLMProviderType.AWS_BEDROCK, Exception("Test error"))
    await cb._on_provider_failure(LLMProviderType.AWS_BEDROCK, Exception("Test error"))
    
    health = cb.get_provider_health(LLMProviderType.AWS_BEDROCK)
    assert health.failed_requests == 2, "Failures not tracked"
    assert health.consecutive_failures == 2, "Consecutive failures not tracked"
    assert not health.is_available, "Provider should be marked unavailable"
    
    logger.info("✓ Provider failure tracking works")
    return True


async def test_provider_order():
    """Test provider failover order."""
    logger.info("\nTest 4: Provider failover order")
    
    cb = LLMCircuitBreaker(service_name="test_llm")
    
    # Test with AWS Bedrock as primary
    order = cb._get_provider_order(LLMProviderType.AWS_BEDROCK)
    assert order[0] == LLMProviderType.AWS_BEDROCK, "Primary provider not first"
    assert LLMProviderType.OPENAI in order, "OpenAI not in failover order"
    assert LLMProviderType.LOCAL in order, "Local not in failover order"
    
    # Test with OpenAI as primary
    order = cb._get_provider_order(LLMProviderType.OPENAI)
    assert order[0] == LLMProviderType.OPENAI, "Primary provider not first"
    
    logger.info("✓ Provider failover order correct")
    return True


async def test_health_summary():
    """Test health summary generation."""
    logger.info("\nTest 5: Health summary")
    
    cb = LLMCircuitBreaker(service_name="test_llm")
    
    # Simulate some activity
    await cb._on_provider_success(LLMProviderType.OPENAI, 100)
    await cb._on_provider_success(LLMProviderType.OPENAI, 200)
    await cb._on_provider_failure(LLMProviderType.AWS_BEDROCK, Exception("Test"))
    
    summary = cb.get_health_summary()
    
    assert summary['service_name'] == "test_llm", "Service name incorrect"
    assert 'available_providers' in summary, "Available providers missing"
    assert 'provider_health' in summary, "Provider health missing"
    assert 'provider_states' in summary, "Provider states missing"
    assert summary['total_requests'] == 3, "Total requests incorrect"
    
    logger.info(f"✓ Health summary: {summary['available_providers']}")
    return True


async def test_provider_recovery():
    """Test forced provider recovery."""
    logger.info("\nTest 6: Provider recovery")
    
    cb = LLMCircuitBreaker(
        service_name="test_llm",
        failure_threshold=1
    )
    
    # Cause failure to mark unavailable
    await cb._on_provider_failure(LLMProviderType.OPENAI, Exception("Test"))
    
    health_before = cb.get_provider_health(LLMProviderType.OPENAI)
    assert not health_before.is_available, "Provider should be unavailable"
    
    # Force recovery
    await cb.force_provider_recovery(LLMProviderType.OPENAI)
    
    health_after = cb.get_provider_health(LLMProviderType.OPENAI)
    assert health_after.is_available, "Provider should be available after recovery"
    assert health_after.consecutive_failures == 0, "Consecutive failures should be reset"
    
    logger.info("✓ Provider recovery works")
    return True


async def test_stats_reset():
    """Test statistics reset."""
    logger.info("\nTest 7: Statistics reset")
    
    cb = LLMCircuitBreaker(service_name="test_llm")
    
    # Generate some stats
    await cb._on_provider_success(LLMProviderType.OPENAI, 100)
    await cb._on_provider_failure(LLMProviderType.OPENAI, Exception("Test"))
    
    # Reset stats for one provider
    cb.reset_provider_stats(LLMProviderType.OPENAI)
    
    health = cb.get_provider_health(LLMProviderType.OPENAI)
    assert health.total_requests == 0, "Stats not reset"
    assert health.successful_requests == 0, "Success count not reset"
    assert health.failed_requests == 0, "Failure count not reset"
    
    logger.info("✓ Statistics reset works")
    return True


async def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("LLM Circuit Breaker Unit Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Initialization", test_circuit_breaker_initialization),
        ("Health Tracking", test_provider_health_tracking),
        ("Failure Tracking", test_provider_failure_tracking),
        ("Provider Order", test_provider_order),
        ("Health Summary", test_health_summary),
        ("Provider Recovery", test_provider_recovery),
        ("Stats Reset", test_stats_reset)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"✗ {test_name} failed: {e}")
            results.append((test_name, False))
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("=" * 60)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
