"""
Basic verification test for AWS LLM Adapter.

This is a simple smoke test to verify the adapter can be instantiated
and basic methods work without errors.
"""

import asyncio
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.insert(0, project_root)

from backend.infrastructure.aws.services.llm_adapter import AWSLLMAdapter
from backend.core.llm.cost_calculator import LLMCostCalculator


def test_cost_calculator():
    """Test cost calculator functionality."""
    print("\n=== Testing Cost Calculator ===")
    
    # Test GPT-4 cost calculation
    cost = LLMCostCalculator.calculate_cost(
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50
    )
    print(f"GPT-4 cost (100 input + 50 output tokens): ${cost:.6f}")
    assert cost > 0, "Cost should be positive"
    
    # Test Claude cost calculation
    cost = LLMCostCalculator.calculate_cost(
        model="claude-3-sonnet",
        prompt_tokens=100,
        completion_tokens=50
    )
    print(f"Claude-3-Sonnet cost (100 input + 50 output tokens): ${cost:.6f}")
    assert cost > 0, "Cost should be positive"
    
    # Test model comparison
    models = ["gpt-4", "gpt-3.5-turbo", "claude-3-haiku"]
    costs = LLMCostCalculator.compare_model_costs(models, 100, 50)
    print(f"\nModel cost comparison (100 input + 50 output tokens):")
    for model, cost in costs.items():
        print(f"  {model}: ${cost:.6f}")
    
    # Test cheapest model
    cheapest_model, cheapest_cost = LLMCostCalculator.get_cheapest_model(models, 100, 50)
    print(f"\nCheapest model: {cheapest_model} at ${cheapest_cost:.6f}")
    
    print("✓ Cost calculator tests passed")


def test_adapter_initialization():
    """Test adapter can be initialized."""
    print("\n=== Testing Adapter Initialization ===")
    
    # Initialize without ElastiCache (for testing)
    adapter = AWSLLMAdapter(
        region_name="us-east-1",
        elasticache_endpoint=None,  # Disable caching for test
        dynamodb_table_name="llm_usage_logs_test"
    )
    
    print(f"Adapter initialized: {adapter}")
    print(f"Bedrock provider available: {adapter.bedrock_provider.is_available()}")
    print(f"OpenAI provider available: {adapter.openai_provider.is_available()}")
    print(f"Cache service enabled: {adapter.cache_service is not None}")
    
    # Get health status
    health = adapter.get_health_status()
    print(f"\nHealth status:")
    print(f"  Service: {health['service']}")
    print(f"  Status: {health['status']}")
    print(f"  Bedrock available: {health['providers']['bedrock']['available']}")
    print(f"  OpenAI available: {health['providers']['openai']['available']}")
    print(f"  Cache enabled: {health['cache']['enabled']}")
    print(f"  Usage logging enabled: {health['usage_logging']['enabled']}")
    
    print("✓ Adapter initialization tests passed")


async def test_cache_key_generation():
    """Test cache key generation."""
    print("\n=== Testing Cache Key Generation ===")
    
    adapter = AWSLLMAdapter(
        region_name="us-east-1",
        elasticache_endpoint=None
    )
    
    # Generate cache keys
    key1 = adapter._generate_cache_key(
        prompt="Hello world",
        model="gpt-4",
        temperature=0.3,
        max_tokens=500,
        tenant_id="tenant1"
    )
    
    key2 = adapter._generate_cache_key(
        prompt="Hello world",
        model="gpt-4",
        temperature=0.3,
        max_tokens=500,
        tenant_id="tenant1"
    )
    
    key3 = adapter._generate_cache_key(
        prompt="Hello world",
        model="gpt-4",
        temperature=0.3,
        max_tokens=500,
        tenant_id="tenant2"  # Different tenant
    )
    
    print(f"Key 1: {key1}")
    print(f"Key 2: {key2}")
    print(f"Key 3: {key3}")
    
    # Same parameters should generate same key
    assert key1 == key2, "Same parameters should generate same cache key"
    
    # Different tenant should generate different key
    assert key1 != key3, "Different tenant should generate different cache key"
    
    # Keys should include tenant ID
    assert "tenant1" in key1, "Cache key should include tenant ID"
    assert "tenant2" in key3, "Cache key should include tenant ID"
    
    print("✓ Cache key generation tests passed")


async def test_usage_stats_structure():
    """Test usage stats return structure."""
    print("\n=== Testing Usage Stats Structure ===")
    
    adapter = AWSLLMAdapter(
        region_name="us-east-1",
        elasticache_endpoint=None
    )
    
    # Get usage stats (will return empty/error since no DynamoDB)
    stats = await adapter.get_usage_stats(
        agent_id="test_agent",
        tenant_id="test_tenant",
        time_range="24h"
    )
    
    print(f"Usage stats structure:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Verify expected keys exist
    assert "total_requests" in stats, "Stats should include total_requests"
    assert "total_tokens" in stats, "Stats should include total_tokens"
    
    print("✓ Usage stats structure tests passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("AWS LLM Adapter - Basic Verification Tests")
    print("=" * 60)
    
    try:
        # Synchronous tests
        test_cost_calculator()
        test_adapter_initialization()
        
        # Async tests
        asyncio.run(test_cache_key_generation())
        asyncio.run(test_usage_stats_structure())
        
        print("\n" + "=" * 60)
        print("✓ All basic verification tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
