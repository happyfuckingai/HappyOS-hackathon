"""
Standalone integration tests for AWS LLM Adapter.

These tests are designed to run without full dependency installation.
They test the core integration functionality with mocked AWS services.
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))


# Skip tests if explicitly disabled
SKIP_AWS_TESTS = os.getenv("SKIP_AWS_INTEGRATION_TESTS", "0") == "1"
skip_aws = pytest.mark.skipif(SKIP_AWS_TESTS, reason="AWS integration tests disabled")


class MockElastiCacheAdapter:
    """Mock ElastiCache adapter for testing."""
    
    def __init__(self, *args, **kwargs):
        self.cache = {}
    
    async def get(self, key: str, tenant_id: str):
        cache_key = f"{tenant_id}:{key}"
        return self.cache.get(cache_key)
    
    async def set(self, key: str, value, tenant_id: str, ttl: int = 3600):
        cache_key = f"{tenant_id}:{key}"
        self.cache[cache_key] = value
        return True
    
    async def delete(self, key: str, tenant_id: str):
        cache_key = f"{tenant_id}:{key}"
        if cache_key in self.cache:
            del self.cache[cache_key]
            return True
        return False


class MockBedrockProvider:
    """Mock Bedrock provider for testing."""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.call_count = 0
    
    def is_available(self):
        return not self.should_fail
    
    async def generate_completion(self, prompt: str, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise Exception("Bedrock unavailable")
        
        return {
            "content": f"Bedrock response to: {prompt[:30]}...",
            "model": kwargs.get("model", "claude-3-sonnet"),
            "tokens": 100,
            "prompt_tokens": 50,
            "completion_tokens": 50,
            "finish_reason": "stop"
        }
    
    async def generate_streaming_completion(self, prompt: str, **kwargs):
        if self.should_fail:
            raise NotImplementedError("Bedrock streaming not available")
        
        # Yield some chunks
        for chunk in ["Bedrock ", "streaming ", "response"]:
            yield chunk


class MockOpenAIProvider:
    """Mock OpenAI provider for testing."""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.call_count = 0
    
    def is_available(self):
        return not self.should_fail
    
    async def generate_completion(self, prompt: str, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise Exception("OpenAI unavailable")
        
        return {
            "content": f"OpenAI response to: {prompt[:30]}...",
            "model": kwargs.get("model", "gpt-4"),
            "tokens": 100,
            "prompt_tokens": 50,
            "completion_tokens": 50,
            "finish_reason": "stop"
        }
    
    async def generate_streaming_completion(self, prompt: str, **kwargs):
        if self.should_fail:
            raise Exception("OpenAI streaming unavailable")
        
        # Yield some chunks
        for chunk in ["OpenAI ", "streaming ", "response"]:
            yield chunk


# Import after mocking dependencies
with patch.dict('sys.modules', {
    'backend.infrastructure.aws.services.elasticache_adapter': MagicMock(),
    'opensearchpy': MagicMock()
}):
    from backend.infrastructure.aws.services.llm_adapter import AWSLLMAdapter
    from backend.core.circuit_breaker.circuit_breaker import CircuitState, CircuitBreakerOpenError


@pytest.fixture
def mock_bedrock_provider():
    """Create mock Bedrock provider."""
    return MockBedrockProvider()


@pytest.fixture
def mock_openai_provider():
    """Create mock OpenAI provider."""
    return MockOpenAIProvider()


@pytest.fixture
def mock_cache_service():
    """Create mock cache service."""
    return MockElastiCacheAdapter()


@pytest.fixture
async def llm_adapter_with_mocks(mock_bedrock_provider, mock_openai_provider, mock_cache_service):
    """Create LLM adapter with mocked dependencies."""
    adapter = AWSLLMAdapter(
        region_name="us-east-1",
        elasticache_endpoint=None,
        dynamodb_table_name="llm_usage_logs_test"
    )
    
    # Replace providers with mocks
    adapter.bedrock_provider = mock_bedrock_provider
    adapter.openai_provider = mock_openai_provider
    adapter.cache_service = mock_cache_service
    
    # Mock DynamoDB client
    adapter.dynamodb_client = None  # Disable DynamoDB for tests
    
    yield adapter


class TestAWSLLMAdapterIntegration:
    """Integration tests for AWS LLM adapter with mocked services."""
    
    @pytest.mark.asyncio
    async def test_bedrock_completion_success(self, llm_adapter_with_mocks):
        """Test successful Bedrock completion."""
        adapter = llm_adapter_with_mocks
        
        result = await adapter.generate_completion(
            prompt="Test prompt",
            agent_id="test_agent",
            tenant_id="test_tenant",
            model="gpt-4",
            temperature=0.3,
            max_tokens=100,
            response_format="text"
        )
        
        # Verify response structure
        assert "content" in result
        assert "model" in result
        assert "tokens" in result
        assert "provider" in result
        assert "cached" in result
        
        # Verify Bedrock was used
        assert result["provider"] == "bedrock"
        assert "Bedrock response" in result["content"]
        assert result["cached"] is False
    
    @pytest.mark.asyncio
    async def test_cache_hit_on_second_call(self, llm_adapter_with_mocks):
        """Test that second identical call returns cached response."""
        adapter = llm_adapter_with_mocks
        
        prompt = "Test caching"
        
        # First call
        result1 = await adapter.generate_completion(
            prompt=prompt,
            agent_id="test_agent",
            tenant_id="test_tenant",
            model="gpt-4",
            temperature=0.3,
            max_tokens=100,
            response_format="text"
        )
        
        assert result1["cached"] is False
        
        # Second call with same parameters
        result2 = await adapter.generate_completion(
            prompt=prompt,
            agent_id="test_agent",
            tenant_id="test_tenant",
            model="gpt-4",
            temperature=0.3,
            max_tokens=100,
            response_format="text"
        )
        
        assert result2["cached"] is True
        assert result1["content"] == result2["content"]
    
    @pytest.mark.asyncio
    async def test_cache_isolation_by_tenant(self, llm_adapter_with_mocks):
        """Test that cache is isolated by tenant."""
        adapter = llm_adapter_with_mocks
        
        prompt = "Test tenant isolation"
        
        # Call for tenant 1
        result1 = await adapter.generate_completion(
            prompt=prompt,
            agent_id="test_agent",
            tenant_id="tenant1",
            model="gpt-4",
            temperature=0.3,
            max_tokens=100,
            response_format="text"
        )
        
        # Call for tenant 2 with same prompt
        result2 = await adapter.generate_completion(
            prompt=prompt,
            agent_id="test_agent",
            tenant_id="tenant2",
            model="gpt-4",
            temperature=0.3,
            max_tokens=100,
            response_format="text"
        )
        
        # Second call should not be cached (different tenant)
        assert result2["cached"] is False
    
    @pytest.mark.asyncio
    async def test_fallback_to_openai_when_bedrock_fails(self, llm_adapter_with_mocks):
        """Test automatic fallback to OpenAI when Bedrock fails."""
        adapter = llm_adapter_with_mocks
        
        # Make Bedrock fail
        adapter.bedrock_provider.should_fail = True
        
        result = await adapter.generate_completion(
            prompt="Test fallback",
            agent_id="test_agent",
            tenant_id="test_tenant",
            model="gpt-4",
            temperature=0.3,
            max_tokens=100,
            response_format="text"
        )
        
        # Verify fallback to OpenAI
        assert result["provider"] == "openai"
        assert "OpenAI response" in result["content"]
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, llm_adapter_with_mocks):
        """Test that circuit breaker opens after threshold failures."""
        adapter = llm_adapter_with_mocks
        
        # Make Bedrock fail
        adapter.bedrock_provider.should_fail = True
        
        # Make multiple calls to trigger circuit breaker
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
                pass  # Expected to fail
        
        # Circuit breaker should be open
        assert adapter.bedrock_circuit_breaker.get_state() == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_calls_when_open(self, llm_adapter_with_mocks):
        """Test that circuit breaker prevents calls when open."""
        adapter = llm_adapter_with_mocks
        
        # Force circuit breaker to open
        adapter.bedrock_circuit_breaker.force_open()
        
        # Try to call Bedrock - should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await adapter._call_bedrock(
                prompt="test",
                model="gpt-4",
                temperature=0.3,
                max_tokens=10,
                response_format="text"
            )
    
    @pytest.mark.asyncio
    async def test_all_providers_fail(self, llm_adapter_with_mocks):
        """Test error handling when all providers fail."""
        adapter = llm_adapter_with_mocks
        
        # Make both providers fail
        adapter.bedrock_provider.should_fail = True
        adapter.openai_provider.should_fail = True
        
        # Try to generate completion - should fail
        with pytest.raises(Exception) as exc_info:
            await adapter.generate_completion(
                prompt="test",
                agent_id="test_agent",
                tenant_id="test_tenant",
                model="gpt-4",
                temperature=0.3,
                max_tokens=10,
                response_format="text"
            )
        
        # Verify error message
        error_msg = str(exc_info.value)
        assert "failed" in error_msg.lower()
    
    @pytest.mark.asyncio
    async def test_streaming_completion(self, llm_adapter_with_mocks):
        """Test streaming completion generation."""
        adapter = llm_adapter_with_mocks
        
        # Force use of OpenAI for streaming
        adapter.bedrock_provider.should_fail = True
        
        # Generate streaming completion
        chunks = []
        async for chunk in adapter.generate_streaming_completion(
            prompt="Test streaming",
            agent_id="test_agent",
            tenant_id="test_tenant",
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
        
        # Verify content
        full_response = "".join(chunks)
        assert "OpenAI" in full_response or "streaming" in full_response
    
    @pytest.mark.asyncio
    async def test_cost_calculation(self, llm_adapter_with_mocks):
        """Test that cost is calculated and included in response."""
        adapter = llm_adapter_with_mocks
        
        result = await adapter.generate_completion(
            prompt="Test cost calculation",
            agent_id="test_agent",
            tenant_id="test_tenant",
            model="gpt-4",
            temperature=0.3,
            max_tokens=100,
            response_format="text"
        )
        
        # Verify cost is included
        assert "estimated_cost" in result
        assert isinstance(result["estimated_cost"], (int, float))
        assert result["estimated_cost"] >= 0
    
    @pytest.mark.asyncio
    async def test_health_status(self, llm_adapter_with_mocks):
        """Test health status reporting."""
        adapter = llm_adapter_with_mocks
        
        health = adapter.get_health_status()
        
        # Verify health status structure
        assert "service" in health
        assert health["service"] == "aws_llm_adapter"
        assert "status" in health
        assert "providers" in health
        assert "bedrock" in health["providers"]
        assert "openai" in health["providers"]
        
        # Verify provider availability
        assert health["providers"]["bedrock"]["available"] is True
        assert health["providers"]["openai"]["available"] is True
    
    @pytest.mark.asyncio
    async def test_usage_stats_structure(self, llm_adapter_with_mocks):
        """Test usage statistics return correct structure."""
        adapter = llm_adapter_with_mocks
        
        stats = await adapter.get_usage_stats(
            agent_id="test_agent",
            tenant_id="test_tenant",
            time_range="24h"
        )
        
        # Verify stats structure
        assert "total_requests" in stats
        assert "total_tokens" in stats
        assert isinstance(stats["total_requests"], int)
        assert isinstance(stats["total_tokens"], int)


class TestCircuitBreakerBehavior:
    """Detailed tests for circuit breaker behavior."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions(self, llm_adapter_with_mocks):
        """Test circuit breaker state transitions."""
        adapter = llm_adapter_with_mocks
        cb = adapter.bedrock_circuit_breaker
        
        # Initial state should be CLOSED
        assert cb.get_state() == CircuitState.CLOSED
        
        # Force to OPEN
        cb.force_open()
        assert cb.get_state() == CircuitState.OPEN
        
        # Force back to CLOSED
        cb.force_close()
        assert cb.get_state() == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_counting(self, llm_adapter_with_mocks):
        """Test that circuit breaker counts failures correctly."""
        adapter = llm_adapter_with_mocks
        cb = adapter.bedrock_circuit_breaker
        
        # Make Bedrock fail
        adapter.bedrock_provider.should_fail = True
        
        initial_failures = cb.stats.failed_calls
        
        # Make a failing call
        try:
            await adapter._call_bedrock(
                prompt="test",
                model="gpt-4",
                temperature=0.3,
                max_tokens=10,
                response_format="text"
            )
        except Exception:
            pass
        
        # Failure count should increase
        assert cb.stats.failed_calls > initial_failures
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success_resets_failures(self, llm_adapter_with_mocks):
        """Test that successful calls reset failure count."""
        adapter = llm_adapter_with_mocks
        cb = adapter.bedrock_circuit_breaker
        
        # Make some failures
        adapter.bedrock_provider.should_fail = True
        for i in range(2):
            try:
                await adapter._call_bedrock(
                    prompt="test",
                    model="gpt-4",
                    temperature=0.3,
                    max_tokens=10,
                    response_format="text"
                )
            except Exception:
                pass
        
        # Now make a successful call
        adapter.bedrock_provider.should_fail = False
        await adapter._call_bedrock(
            prompt="test",
            model="gpt-4",
            temperature=0.3,
            max_tokens=10,
            response_format="text"
        )
        
        # Failure count should be reset
        assert cb.failure_count == 0


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
