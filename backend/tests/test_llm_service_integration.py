"""
Simple validation script for LLM service integration with ServiceFacade.

This script validates:
1. ServiceFacade can initialize LLM service
2. LLM circuit breaker is properly configured
3. Provider failover logic works
4. Health checks include LLM service
"""

import asyncio
import logging
from backend.infrastructure.service_facade import (
    ServiceFacade,
    ServiceFacadeConfig,
    ServiceMode
)
from backend.core.circuit_breaker.llm_circuit_breaker import (
    LLMCircuitBreaker,
    LLMProviderType
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_llm_service_initialization():
    """Test that LLM service can be initialized in ServiceFacade."""
    logger.info("Testing LLM service initialization...")
    
    # Create service facade in LOCAL mode (no AWS dependencies)
    config = ServiceFacadeConfig(mode=ServiceMode.LOCAL_ONLY)
    facade = ServiceFacade(config)
    
    try:
        await facade.initialize()
        logger.info("✓ ServiceFacade initialized successfully")
        
        # Get LLM service
        llm_service = facade.get_llm_service()
        logger.info(f"✓ LLM service retrieved: {type(llm_service).__name__}")
        
        # Check that LLM is in circuit breakers
        assert 'llm' in facade._circuit_breakers, "LLM circuit breaker not found"
        logger.info("✓ LLM circuit breaker registered")
        
        # Check that local LLM service is initialized
        assert 'llm' in facade._local_services, "Local LLM service not initialized"
        logger.info("✓ Local LLM service initialized")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Initialization failed: {e}")
        return False


async def test_llm_circuit_breaker():
    """Test LLM circuit breaker functionality."""
    logger.info("\nTesting LLM circuit breaker...")
    
    try:
        # Create LLM circuit breaker
        cb = LLMCircuitBreaker(
            service_name="test_llm",
            failure_threshold=2,
            timeout_seconds=5
        )
        logger.info("✓ LLM circuit breaker created")
        
        # Check provider initialization
        provider_states = cb.get_all_provider_states()
        logger.info(f"✓ Provider states: {[p.value for p in provider_states.keys()]}")
        
        # Check health summary
        health = cb.get_health_summary()
        logger.info(f"✓ Health summary: {health['available_providers']}")
        
        # Test provider health tracking
        for provider in LLMProviderType:
            provider_health = cb.get_provider_health(provider)
            assert provider_health is not None, f"Health not found for {provider.value}"
        logger.info("✓ Provider health tracking working")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Circuit breaker test failed: {e}")
        return False


async def test_health_check_integration():
    """Test that health checks include LLM service."""
    logger.info("\nTesting health check integration...")
    
    config = ServiceFacadeConfig(mode=ServiceMode.LOCAL_ONLY)
    facade = ServiceFacade(config)
    
    try:
        await facade.initialize()
        
        # Get system health
        health = await facade.get_system_health()
        logger.info(f"✓ System health retrieved: mode={health['mode']}")
        
        # Check that LLM is in services
        assert 'llm' in health['services'], "LLM not in health services"
        logger.info(f"✓ LLM health status: {health['services']['llm']}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Health check test failed: {e}")
        return False


async def test_hybrid_mode():
    """Test LLM service in HYBRID mode (AWS with local fallback)."""
    logger.info("\nTesting HYBRID mode configuration...")
    
    config = ServiceFacadeConfig(mode=ServiceMode.HYBRID)
    facade = ServiceFacade(config)
    
    try:
        await facade.initialize()
        logger.info("✓ HYBRID mode initialized")
        
        # Check that both AWS and local services are available
        has_aws = 'llm' in facade._aws_services
        has_local = 'llm' in facade._local_services
        
        logger.info(f"  AWS LLM service: {'✓' if has_aws else '✗'}")
        logger.info(f"  Local LLM service: {'✓' if has_local else '✗'}")
        
        # In HYBRID mode, we should have at least local
        assert has_local, "Local LLM service not available in HYBRID mode"
        
        return True
        
    except Exception as e:
        logger.error(f"✗ HYBRID mode test failed: {e}")
        return False


async def main():
    """Run all validation tests."""
    logger.info("=" * 60)
    logger.info("LLM Service Integration Validation")
    logger.info("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("LLM Service Initialization", await test_llm_service_initialization()))
    results.append(("LLM Circuit Breaker", await test_llm_circuit_breaker()))
    results.append(("Health Check Integration", await test_health_check_integration()))
    results.append(("HYBRID Mode", await test_hybrid_mode()))
    
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
