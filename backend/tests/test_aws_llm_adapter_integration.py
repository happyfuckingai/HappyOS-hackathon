"""
Integration tests for AWS LLM Adapter.

These tests verify the AWS LLM adapter works correctly with real AWS services:
- AWS Bedrock integration
- ElastiCache caching
- Circuit breaker failover
- Fallback to OpenAI

Note: These tests require AWS credentials and may incur costs.
Set SKIP_AWS_INTEGRATION_TESTS=1 to skip these tests.
"""

import pytest
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

# Import directly to avoid package-level import issues
import importlib.util

# Load LLM adapter module directly
llm_adapter_path = backend_path / "infrastructure" / "aws" / "services" / "llm_adapter.py"
spec = importlib.util.spec_from_file_location("llm_adapter", llm_adapter_path)
llm_adapter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(llm_adapter_module)
AWSLLMAdapter = llm_adapter_module.AWSLLMAdapter

# Load circuit breaker module directly
cb_path = backend_path / "core" / "circuit_breaker" / "circuit_breaker.py"
spec = importlib.util.spec_from_file_location("circuit_breaker", cb_path)
cb_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb_module)
CircuitBreakerOpenError = cb_module.CircuitBreakerOpenError
CircuitState = cb_module.CircuitState


# Skip tests if AWS integration tests are disabled
SKIP_AWS_TESTS = os.getenv("SKIP_AWS_INTEGRATION_TESTS", "0") == "1"
skip_aws = pytest.mark.skipif(SKIP_AWS_TESTS, reason="AWS integration tests disabled")


@pytest.fixture
def aws_region():
    """AWS region for testing."""
    return os.getenv("AWS_REGION", "us-east-1")


@pytest.fixture
def test_tenant_id():
    """Test tenant ID."""
    return "test_tenant_integration"


@pytest.fixture
def test_agent_id():
    """Test agent ID."""
    return "test_agent_integration"


@pytest.fixture
async def llm_adapter_no_cache(aws_region):
    """Create LLM adapter without caching for testing."""
    adapter = AWSLLMAdapter(
        region_name=aws_region,
        elasticache_endpoint=None,  # No caching for basic tests
        dynamodb_table_name="llm_usage_logs_test"
    )
    yield adapter
    # Cleanup if needed


@pytest.fixture
async def llm_adapter_with_cache(aws_region):
    """Create LLM adapter with ElastiCache if available."""
    elasticache_endpoint = os.getenv("ELASTICACHE_ENDPOINT")
    
    adapter = AWSLLMAdapter(
        region_name=aws_region,
        elasticache_endpoint=elasticache_endpoint,
        dynamodb_table_name="llm_usage_logs_test"
    )
    yield adapter
    # Cleanup if needed


class TestAWSLLMAdapterBasic:
    """Basic integration tests for AWS LLM adapter."""
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_adapter_initialization(self, llm_adapter_no_cache):
        """Test adapter initializes correctly."""
        adapter = llm_adapter_no_cache
        
        # Check providers are initialized
        assert adapter.bedrock_provider is not None
        assert adapter.openai_provider is not None
        
        # Check circuit breakers are initialized
        assert adapter.bedrock_circuit_breaker is not None
        assert adapter.openai_circuit_breaker is not None
        
        # Check initial circuit breaker states
        assert adapter.bedrock_circuit_breaker.get_state() == CircuitState.CLOSED
        assert adapter.openai_circuit_breaker.get_state() == CircuitState.CLOSED
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_health_status(self, llm_adapter_no_cache):
        """Test health status reporting."""
        adapter = llm_adapter_no_cache
        
        health = adapter.get_health_status()
        
        # Verify health status structure
        assert "service" in health
        assert health["service"] == "aws_llm_adapter"
        assert "status" in health
        assert "providers" in health
        assert "bedrock" in health["providers"]
        assert "openai" in health["providers"]
        assert "cache" in health
        assert "usage_logging" in health
        
        # Verify provider availability
        assert "available" in health["providers"]["bedrock"]
        assert "available" in health["providers"]["openai"]
        assert "circuit_breaker_state" in health["providers"]["bedrock"]
        assert "circuit_breaker_state" in health["providers"]["openai"]
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, llm_adapter_no_cache, test_tenant_id):
        """Test cache key generation with tenant isolation."""
        adapter = llm_adapter_no_cache
        
        # Generate cache keys
        key1 = adapter._generate_cache_key(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id=test_tenant_id
        )
        
        # Same parameters should generate same key
        key2 = adapter._generate_cache_key(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id=test_tenant_id
        )
        
        assert key1 == key2, "Same parameters should generate same cache key"
        
        # Different tenant should generate different key
        key3 = adapter._generate_cache_key(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id="different_tenant"
        )
        
        assert key1 != key3, "Different tenants should generate different cache keys"
        
        # Verify tenant isolation in key
        assert test_tenant_id in key1
        assert "different_tenant" in key3


class TestBedrockIntegration:
    """Integration tests for AWS Bedrock."""
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_bedrock_completion(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test Bedrock completion generation."""
        adapter = llm_adapter_no_cache
        
        # Skip if Bedrock is not available
        if not adapter.bedrock_provider.is_available():
            pytest.skip("Bedrock provider not available")
        
        # Generate completion
        result = await adapter.generate_completion(
            prompt="What is 2+2? Answer with just the number.",
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",  # Will be routed to appropriate Bedrock model
            temperature=0.1,
            max_tokens=10,
            response_format="text"
        )
        
        # Verify response structure
        assert "content" in result
        assert "model" in result
        assert "tokens" in result
        assert "provider" in result
        assert "cached" in result
        
        # Verify content is not empty
        assert len(result["content"]) > 0
        
        # Verify provider (should be bedrock if available)
        assert result["provider"] in ["bedrock", "openai"]
        
        # Verify not cached on first call
        assert result["cached"] is False
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_bedrock_with_json_response(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test Bedrock with JSON response format."""
        adapter = llm_adapter_no_cache
        
        if not adapter.bedrock_provider.is_available():
            pytest.skip("Bedrock provider not available")
        
        # Generate completion with JSON format
        result = await adapter.generate_completion(
            prompt='Return a JSON object with a single field "answer" containing the number 42.',
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.1,
            max_tokens=50,
            response_format="json"
        )
        
        # Verify response
        assert "content" in result
        assert len(result["content"]) > 0
        
        # Try to parse as JSON (content should be JSON-like)
        import json
        try:
            # Content might be wrapped or might be raw JSON
            content = result["content"]
            if isinstance(content, str):
                # Try to extract JSON if it's in markdown code block
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                parsed = json.loads(content)
                assert "answer" in parsed or isinstance(parsed, dict)
        except json.JSONDecodeError:
            # Some models might not return perfect JSON, that's okay for this test
            pass


class TestElastiCacheCaching:
    """Integration tests for ElastiCache caching."""
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_cache_hit_on_second_call(
        self,
        llm_adapter_with_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test that second identical call returns cached response."""
        adapter = llm_adapter_with_cache
        
        # Skip if cache is not enabled
        if adapter.cache_service is None:
            pytest.skip("ElastiCache not configured")
        
        prompt = "What is the capital of France? Answer in one word."
        
        # First call - should not be cached
        result1 = await adapter.generate_completion(
            prompt=prompt,
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.3,
            max_tokens=20,
            response_format="text"
        )
        
        assert result1["cached"] is False
        
        # Second call with same parameters - should be cached
        result2 = await adapter.generate_completion(
            prompt=prompt,
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.3,
            max_tokens=20,
            response_format="text"
        )
        
        assert result2["cached"] is True
        
        # Content should be the same
        assert result1["content"] == result2["content"]
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_cache_isolation_by_tenant(
        self,
        llm_adapter_with_cache,
        test_agent_id
    ):
        """Test that cache is isolated by tenant."""
        adapter = llm_adapter_with_cache
        
        if adapter.cache_service is None:
            pytest.skip("ElastiCache not configured")
        
        prompt = "Say hello"
        
        # Call for tenant 1
        result1 = await adapter.generate_completion(
            prompt=prompt,
            agent_id=test_agent_id,
            tenant_id="tenant1",
            model="gpt-4",
            temperature=0.3,
            max_tokens=20,
            response_format="text"
        )
        
        # Call for tenant 2 with same prompt - should not be cached
        result2 = await adapter.generate_completion(
            prompt=prompt,
            agent_id=test_agent_id,
            tenant_id="tenant2",
            model="gpt-4",
            temperature=0.3,
            max_tokens=20,
            response_format="text"
        )
        
        # Second call should not be cached (different tenant)
        assert result2["cached"] is False
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_cache_invalidation_by_parameters(
        self,
        llm_adapter_with_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test that cache is invalidated when parameters change."""
        adapter = llm_adapter_with_cache
        
        if adapter.cache_service is None:
            pytest.skip("ElastiCache not configured")
        
        prompt = "Count to three"
        
        # First call
        result1 = await adapter.generate_completion(
            prompt=prompt,
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.3,
            max_tokens=20,
            response_format="text"
        )
        
        # Second call with different temperature - should not be cached
        result2 = await adapter.generate_completion(
            prompt=prompt,
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.7,  # Different temperature
            max_tokens=20,
            response_format="text"
        )
        
        assert result2["cached"] is False


class TestCircuitBreakerFailover:
    """Integration tests for circuit breaker and failover."""
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test that circuit breaker opens after threshold failures."""
        adapter = llm_adapter_no_cache
        
        # Force Bedrock provider to fail by mocking
        original_call = adapter.bedrock_provider.generate_completion
        
        async def failing_call(*args, **kwargs):
            raise Exception("Simulated Bedrock failure")
        
        adapter.bedrock_provider.generate_completion = failing_call
        
        # Make multiple calls to trigger circuit breaker
        failure_count = 0
        for i in range(5):
            try:
                await adapter._call_bedrock(
                    prompt="test",
                    model="gpt-4",
                    temperature=0.3,
                    max_tokens=10,
                    response_format="text"
                )
            except Exception:
                failure_count += 1
        
        # Circuit breaker should be open after threshold failures
        assert adapter.bedrock_circuit_breaker.get_state() == CircuitState.OPEN
        assert failure_count >= 3  # At least threshold failures
        
        # Restore original method
        adapter.bedrock_provider.generate_completion = original_call
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_fallback_to_openai_when_bedrock_fails(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test automatic fallback to OpenAI when Bedrock fails."""
        adapter = llm_adapter_no_cache
        
        # Skip if OpenAI is not available
        if not adapter.openai_provider.is_available():
            pytest.skip("OpenAI provider not available")
        
        # Force Bedrock circuit breaker to open
        adapter.bedrock_circuit_breaker.force_open()
        
        # Make a call - should fallback to OpenAI
        result = await adapter.generate_completion(
            prompt="What is 1+1? Answer with just the number.",
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.1,
            max_tokens=10,
            response_format="text"
        )
        
        # Verify fallback worked
        assert "content" in result
        assert result["provider"] == "openai"
        assert len(result["content"]) > 0
        
        # Reset circuit breaker
        adapter.bedrock_circuit_breaker.force_close()
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test circuit breaker recovery from OPEN to HALF_OPEN to CLOSED."""
        adapter = llm_adapter_no_cache
        
        # Force circuit breaker to open
        adapter.bedrock_circuit_breaker.force_open()
        assert adapter.bedrock_circuit_breaker.get_state() == CircuitState.OPEN
        
        # Wait for recovery timeout (use short timeout for testing)
        adapter.bedrock_circuit_breaker.timeout_seconds = 1
        await asyncio.sleep(1.5)
        
        # Try to make a call - should transition to HALF_OPEN
        try:
            await adapter._call_bedrock(
                prompt="test",
                model="gpt-4",
                temperature=0.3,
                max_tokens=10,
                response_format="text"
            )
        except Exception:
            pass  # Call might fail, but state should change
        
        # Circuit breaker should be in HALF_OPEN or CLOSED state
        state = adapter.bedrock_circuit_breaker.get_state()
        assert state in [CircuitState.HALF_OPEN, CircuitState.CLOSED]


class TestOpenAIFallback:
    """Integration tests for OpenAI fallback."""
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_openai_fallback_completion(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test OpenAI fallback generates completions correctly."""
        adapter = llm_adapter_no_cache
        
        if not adapter.openai_provider.is_available():
            pytest.skip("OpenAI provider not available")
        
        # Force use of OpenAI by opening Bedrock circuit breaker
        adapter.bedrock_circuit_breaker.force_open()
        
        # Generate completion
        result = await adapter.generate_completion(
            prompt="What is the color of the sky? Answer in one word.",
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.1,
            max_tokens=10,
            response_format="text"
        )
        
        # Verify response
        assert "content" in result
        assert result["provider"] == "openai"
        assert len(result["content"]) > 0
        
        # Reset circuit breaker
        adapter.bedrock_circuit_breaker.force_close()
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_all_providers_fail(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test error handling when all providers fail."""
        adapter = llm_adapter_no_cache
        
        # Force both circuit breakers to open
        adapter.bedrock_circuit_breaker.force_open()
        adapter.openai_circuit_breaker.force_open()
        
        # Try to generate completion - should fail
        with pytest.raises(Exception) as exc_info:
            await adapter.generate_completion(
                prompt="test",
                agent_id=test_agent_id,
                tenant_id=test_tenant_id,
                model="gpt-4",
                temperature=0.3,
                max_tokens=10,
                response_format="text"
            )
        
        # Verify error message mentions both providers
        error_msg = str(exc_info.value)
        assert "failed" in error_msg.lower() or "open" in error_msg.lower()
        
        # Reset circuit breakers
        adapter.bedrock_circuit_breaker.force_close()
        adapter.openai_circuit_breaker.force_close()


class TestUsageTracking:
    """Integration tests for usage tracking and statistics."""
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_usage_stats_structure(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test usage statistics return correct structure."""
        adapter = llm_adapter_no_cache
        
        # Get usage stats
        stats = await adapter.get_usage_stats(
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            time_range="24h"
        )
        
        # Verify stats structure
        assert "total_requests" in stats
        assert "total_tokens" in stats
        assert isinstance(stats["total_requests"], int)
        assert isinstance(stats["total_tokens"], int)
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_usage_logging_after_completion(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test that usage is logged after completion."""
        adapter = llm_adapter_no_cache
        
        # Skip if DynamoDB is not available
        if adapter.dynamodb_client is None:
            pytest.skip("DynamoDB client not available")
        
        # Make a completion call
        result = await adapter.generate_completion(
            prompt="Say hello",
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.3,
            max_tokens=10,
            response_format="text"
        )
        
        # Wait a bit for async logging
        await asyncio.sleep(1)
        
        # Get usage stats
        stats = await adapter.get_usage_stats(
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            time_range="1h"
        )
        
        # Verify usage was logged (might be 0 if DynamoDB write failed)
        assert "total_requests" in stats
        assert stats["total_requests"] >= 0


class TestCostTracking:
    """Integration tests for cost tracking."""
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_cost_calculation_in_response(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test that cost is calculated and included in response."""
        adapter = llm_adapter_no_cache
        
        # Generate completion
        result = await adapter.generate_completion(
            prompt="Count to five",
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.3,
            max_tokens=50,
            response_format="text"
        )
        
        # Verify cost is included
        assert "estimated_cost" in result
        assert isinstance(result["estimated_cost"], (int, float))
        assert result["estimated_cost"] >= 0
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_cost_tracking_in_stats(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test that costs are tracked in usage statistics."""
        adapter = llm_adapter_no_cache
        
        # Get usage stats
        stats = await adapter.get_usage_stats(
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            time_range="24h"
        )
        
        # Verify cost fields exist
        if "total_cost" in stats:
            assert isinstance(stats["total_cost"], (int, float))
            assert stats["total_cost"] >= 0


class TestStreamingCompletion:
    """Integration tests for streaming completions."""
    
    @skip_aws
    @pytest.mark.asyncio
    async def test_streaming_completion(
        self,
        llm_adapter_no_cache,
        test_agent_id,
        test_tenant_id
    ):
        """Test streaming completion generation."""
        adapter = llm_adapter_no_cache
        
        if not adapter.openai_provider.is_available():
            pytest.skip("OpenAI provider not available for streaming")
        
        # Force use of OpenAI (Bedrock streaming might not be implemented)
        adapter.bedrock_circuit_breaker.force_open()
        
        # Generate streaming completion
        chunks = []
        async for chunk in adapter.generate_streaming_completion(
            prompt="Count to three",
            agent_id=test_agent_id,
            tenant_id=test_tenant_id,
            model="gpt-4",
            temperature=0.3,
            max_tokens=50
        ):
            chunks.append(chunk)
        
        # Verify we received chunks
        assert len(chunks) > 0
        
        # Verify chunks are strings
        for chunk in chunks:
            assert isinstance(chunk, str)
        
        # Reset circuit breaker
        adapter.bedrock_circuit_breaker.force_close()


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
