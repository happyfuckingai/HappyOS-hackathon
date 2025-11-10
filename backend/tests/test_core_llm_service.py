"""
Unit tests for core LLM service components.

Tests:
- BaseLLMService with mock providers
- Cache key generation
- Provider routing logic
- Error handling and retry logic
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

# Add backend to path for absolute imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

# Import the components to test
from backend.core.llm.llm_service import BaseLLMService
from backend.core.llm.cache_manager import CacheManager


# Mock provider for testing
class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def __init__(self, should_fail: bool = False, fail_count: int = 0):
        self.should_fail = should_fail
        self.fail_count = fail_count
        self.call_count = 0
    
    async def generate_completion(self, prompt: str, **kwargs) -> Dict[str, Any]:
        self.call_count += 1
        
        if self.should_fail:
            if self.fail_count == 0 or self.call_count <= self.fail_count:
                raise Exception("Mock provider failure")
        
        return {
            "content": f"Mock response to: {prompt[:50]}",
            "model": kwargs.get("model", "mock-model"),
            "tokens": 100,
            "prompt_tokens": 50,
            "completion_tokens": 50,
            "finish_reason": "stop"
        }


# Concrete implementation for testing
class MockLLMService(BaseLLMService):
    """Mock implementation of BaseLLMService for testing."""
    
    def __init__(self, providers_dict: Dict[str, MockLLMProvider], **kwargs):
        super().__init__(**kwargs)
        self.providers_dict = providers_dict
        self.providers = list(providers_dict.keys())
    
    async def _call_provider(
        self,
        provider: str,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: str
    ) -> Dict[str, Any]:
        """Call mock provider."""
        if provider not in self.providers_dict:
            raise ValueError(f"Unknown provider: {provider}")
        
        mock_provider = self.providers_dict[provider]
        return await mock_provider.generate_completion(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
    
    async def generate_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500,
        response_format: str = "json"
    ) -> Dict[str, Any]:
        """Generate completion using provider routing."""
        return await self._route_to_provider(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
    
    async def generate_streaming_completion(
        self,
        prompt: str,
        agent_id: str,
        tenant_id: str,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 500
    ):
        """Generate streaming completion (not implemented for tests)."""
        raise NotImplementedError("Streaming not implemented in test service")
    
    async def get_usage_stats(
        self,
        agent_id: str = None,
        tenant_id: str = None,
        time_range: str = "24h"
    ) -> Dict[str, Any]:
        """Get usage stats (mock implementation)."""
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0
        }


class TestBaseLLMService:
    """Test suite for BaseLLMService."""
    
    def test_cache_key_generation(self):
        """Test that cache keys are generated correctly and consistently."""
        # Create service
        service = MockLLMService(providers_dict={})
        
        # Generate cache key
        key1 = service._generate_cache_key(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id="tenant1"
        )
        
        # Same parameters should generate same key
        key2 = service._generate_cache_key(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id="tenant1"
        )
        
        assert key1 == key2, "Same parameters should generate same cache key"
        
        # Different prompt should generate different key
        key3 = service._generate_cache_key(
            prompt="Different prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id="tenant1"
        )
        
        assert key1 != key3, "Different prompts should generate different cache keys"
        
        # Different tenant should generate different key
        key4 = service._generate_cache_key(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id="tenant2"
        )
        
        assert key1 != key4, "Different tenants should generate different cache keys"
        
        # Check key format
        assert key1.startswith("llm_cache:tenant1:gpt-4:"), "Cache key should have correct format"
        assert len(key1.split(":")) == 4, "Cache key should have 4 parts"
    
    @pytest.mark.asyncio
    async def test_provider_routing_success(self):
        """Test successful provider routing."""
        # Create mock providers
        provider1 = MockLLMProvider()
        providers_dict = {"provider1": provider1}
        
        # Create service
        service = MockLLMService(providers_dict=providers_dict)
        
        # Route request
        result = await service._route_to_provider(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            response_format="json"
        )
        
        # Verify result
        assert result is not None
        assert result["content"].startswith("Mock response")
        assert result["provider"] == "provider1"
        assert result["tokens"] == 100
        assert provider1.call_count == 1
    
    @pytest.mark.asyncio
    async def test_provider_routing_with_fallback(self):
        """Test provider routing with fallback when first provider fails."""
        # Create mock providers - first fails, second succeeds
        provider1 = MockLLMProvider(should_fail=True)
        provider2 = MockLLMProvider(should_fail=False)
        providers_dict = {"provider1": provider1, "provider2": provider2}
        
        # Create service
        service = MockLLMService(providers_dict=providers_dict)
        
        # Route request
        result = await service._route_to_provider(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            response_format="json"
        )
        
        # Verify fallback worked
        assert result is not None
        assert result["provider"] == "provider2"
        assert provider1.call_count == 1  # First provider was tried
        assert provider2.call_count == 1  # Second provider succeeded
    
    @pytest.mark.asyncio
    async def test_provider_routing_all_fail(self):
        """Test provider routing when all providers fail."""
        # Create mock providers - all fail
        provider1 = MockLLMProvider(should_fail=True)
        provider2 = MockLLMProvider(should_fail=True)
        providers_dict = {"provider1": provider1, "provider2": provider2}
        
        # Create service
        service = MockLLMService(providers_dict=providers_dict)
        
        # Route request should raise exception
        with pytest.raises(Exception) as exc_info:
            await service._route_to_provider(
                prompt="Test prompt",
                model="gpt-4",
                temperature=0.3,
                max_tokens=500,
                response_format="json"
            )
        
        # Verify error message
        assert "All LLM providers failed" in str(exc_info.value)
        assert provider1.call_count == 1
        assert provider2.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff_success(self):
        """Test retry logic succeeds after initial failures."""
        # Create mock function that fails twice then succeeds
        call_count = 0
        
        async def mock_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return {"success": True}
        
        # Create service with retry settings
        service = MockLLMService(
            providers_dict={},
            max_retries=3,
            retry_delay=0.01  # Short delay for testing
        )
        
        # Call with retry
        result = await service._retry_with_backoff(mock_func)
        
        # Verify success after retries
        assert result == {"success": True}
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_with_backoff_exhausted(self):
        """Test retry logic fails after max retries."""
        # Create mock function that always fails
        call_count = 0
        
        async def mock_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")
        
        # Create service with retry settings
        service = MockLLMService(
            providers_dict={},
            max_retries=3,
            retry_delay=0.01  # Short delay for testing
        )
        
        # Call with retry should fail
        with pytest.raises(Exception) as exc_info:
            await service._retry_with_backoff(mock_func)
        
        # Verify all retries were attempted
        assert "Permanent failure" in str(exc_info.value)
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_usage_logging(self):
        """Test that usage is logged correctly."""
        # Create service
        service = MockLLMService(providers_dict={})
        
        # Mock logger
        with patch.object(service.logger, 'info') as mock_log:
            # Log usage
            await service._log_usage(
                agent_id="test_agent",
                tenant_id="test_tenant",
                model="gpt-4",
                provider="openai",
                tokens_used=100,
                latency_ms=500,
                cached=False,
                success=True
            )
            
            # Verify logging was called
            assert mock_log.called
            log_message = mock_log.call_args[0][0]
            assert "LLM usage:" in log_message
            assert "test_agent" in log_message
            assert "test_tenant" in log_message
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling logs errors correctly."""
        # Create service
        service = MockLLMService(providers_dict={})
        
        # Mock logger
        with patch.object(service.logger, 'error') as mock_log:
            # Handle error
            test_error = ValueError("Test error")
            await service._handle_llm_error(
                error=test_error,
                agent_id="test_agent",
                operation="test_operation"
            )
            
            # Verify error logging
            assert mock_log.called
            log_message = mock_log.call_args[0][0]
            assert "LLM error" in log_message
            assert "test_agent" in log_message
            assert "test_operation" in log_message
            assert "ValueError" in log_message


class TestCacheManager:
    """Test suite for CacheManager."""
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        cache_manager = CacheManager()
        
        # Generate cache key
        key1 = cache_manager.generate_cache_key(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id="tenant1"
        )
        
        # Same parameters should generate same key
        key2 = cache_manager.generate_cache_key(
            prompt="Test prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id="tenant1"
        )
        
        assert key1 == key2
        
        # Different parameters should generate different key
        key3 = cache_manager.generate_cache_key(
            prompt="Different prompt",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            tenant_id="tenant1"
        )
        
        assert key1 != key3
        
        # Check key format
        assert key1.startswith("llm:tenant1:gpt-4:")
    
    @pytest.mark.asyncio
    async def test_cache_get_miss(self):
        """Test cache get with no cached value."""
        # Create mock cache service
        mock_cache_service = AsyncMock()
        mock_cache_service.get.return_value = None
        
        cache_manager = CacheManager(cache_service=mock_cache_service)
        
        # Get from cache
        result = await cache_manager.get("test_key", "tenant1")
        
        # Verify cache miss
        assert result is None
        assert cache_manager.cache_misses == 1
        assert cache_manager.cache_hits == 0
    
    @pytest.mark.asyncio
    async def test_cache_get_hit(self):
        """Test cache get with cached value."""
        # Create mock cache service
        mock_cache_service = AsyncMock()
        cached_value = {"content": "cached response"}
        mock_cache_service.get.return_value = cached_value
        
        cache_manager = CacheManager(cache_service=mock_cache_service)
        
        # Get from cache
        result = await cache_manager.get("test_key", "tenant1")
        
        # Verify cache hit
        assert result == cached_value
        assert cache_manager.cache_hits == 1
        assert cache_manager.cache_misses == 0
    
    @pytest.mark.asyncio
    async def test_cache_set(self):
        """Test cache set operation."""
        # Create mock cache service
        mock_cache_service = AsyncMock()
        mock_cache_service.set.return_value = True
        
        cache_manager = CacheManager(
            cache_service=mock_cache_service,
            default_ttl=3600
        )
        
        # Set cache value
        value = {"content": "test response"}
        result = await cache_manager.set("test_key", value, "tenant1")
        
        # Verify set was called correctly
        assert result is True
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == value
        assert call_args[0][2] == "tenant1"
        assert call_args[1]["ttl"] == 3600
    
    @pytest.mark.asyncio
    async def test_cache_set_custom_ttl(self):
        """Test cache set with custom TTL."""
        # Create mock cache service
        mock_cache_service = AsyncMock()
        mock_cache_service.set.return_value = True
        
        cache_manager = CacheManager(cache_service=mock_cache_service)
        
        # Set cache value with custom TTL
        value = {"content": "test response"}
        result = await cache_manager.set("test_key", value, "tenant1", ttl=7200)
        
        # Verify custom TTL was used
        assert result is True
        call_args = mock_cache_service.set.call_args
        assert call_args[1]["ttl"] == 7200
    
    @pytest.mark.asyncio
    async def test_cache_invalidate(self):
        """Test cache invalidation."""
        # Create mock cache service
        mock_cache_service = AsyncMock()
        mock_cache_service.delete.return_value = True
        
        cache_manager = CacheManager(cache_service=mock_cache_service)
        
        # Invalidate cache
        result = await cache_manager.invalidate("test_key", "tenant1")
        
        # Verify delete was called
        assert result is True
        mock_cache_service.delete.assert_called_once_with("test_key", "tenant1")
    
    def test_cache_metrics(self):
        """Test cache metrics calculation."""
        cache_manager = CacheManager()
        
        # Simulate some cache operations
        cache_manager.cache_hits = 7
        cache_manager.cache_misses = 3
        
        # Get metrics
        metrics = cache_manager.get_metrics()
        
        # Verify metrics
        assert metrics["cache_hits"] == 7
        assert metrics["cache_misses"] == 3
        assert metrics["total_requests"] == 10
        assert metrics["hit_rate_percent"] == 70.0
    
    def test_cache_metrics_no_requests(self):
        """Test cache metrics with no requests."""
        cache_manager = CacheManager()
        
        # Get metrics with no requests
        metrics = cache_manager.get_metrics()
        
        # Verify metrics
        assert metrics["cache_hits"] == 0
        assert metrics["cache_misses"] == 0
        assert metrics["total_requests"] == 0
        assert metrics["hit_rate_percent"] == 0.0
    
    def test_cache_metrics_reset(self):
        """Test cache metrics reset."""
        cache_manager = CacheManager()
        
        # Simulate some cache operations
        cache_manager.cache_hits = 5
        cache_manager.cache_misses = 2
        
        # Reset metrics
        cache_manager.reset_metrics()
        
        # Verify reset
        assert cache_manager.cache_hits == 0
        assert cache_manager.cache_misses == 0
    
    @pytest.mark.asyncio
    async def test_cache_without_service(self):
        """Test cache manager without cache service."""
        # Create cache manager without service
        cache_manager = CacheManager(cache_service=None)
        
        # Operations should return None/False gracefully
        result_get = await cache_manager.get("test_key", "tenant1")
        assert result_get is None
        
        result_set = await cache_manager.set("test_key", {"data": "test"}, "tenant1")
        assert result_set is False
        
        result_invalidate = await cache_manager.invalidate("test_key", "tenant1")
        assert result_invalidate is False


class TestProviderRouting:
    """Test suite for provider routing logic."""
    
    @pytest.mark.asyncio
    async def test_single_provider_success(self):
        """Test routing with single provider that succeeds."""
        provider = MockLLMProvider()
        service = MockLLMService(providers_dict={"provider1": provider})
        
        result = await service._route_to_provider(
            prompt="Test",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            response_format="json"
        )
        
        assert result["provider"] == "provider1"
        assert provider.call_count == 1
    
    @pytest.mark.asyncio
    async def test_multiple_providers_first_succeeds(self):
        """Test routing with multiple providers where first succeeds."""
        provider1 = MockLLMProvider()
        provider2 = MockLLMProvider()
        service = MockLLMService(
            providers_dict={"provider1": provider1, "provider2": provider2}
        )
        
        result = await service._route_to_provider(
            prompt="Test",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            response_format="json"
        )
        
        assert result["provider"] == "provider1"
        assert provider1.call_count == 1
        assert provider2.call_count == 0  # Second provider not called
    
    @pytest.mark.asyncio
    async def test_multiple_providers_second_succeeds(self):
        """Test routing with multiple providers where second succeeds."""
        provider1 = MockLLMProvider(should_fail=True)
        provider2 = MockLLMProvider()
        service = MockLLMService(
            providers_dict={"provider1": provider1, "provider2": provider2}
        )
        
        result = await service._route_to_provider(
            prompt="Test",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            response_format="json"
        )
        
        assert result["provider"] == "provider2"
        assert provider1.call_count == 1
        assert provider2.call_count == 1
    
    @pytest.mark.asyncio
    async def test_three_providers_third_succeeds(self):
        """Test routing with three providers where third succeeds."""
        provider1 = MockLLMProvider(should_fail=True)
        provider2 = MockLLMProvider(should_fail=True)
        provider3 = MockLLMProvider()
        service = MockLLMService(
            providers_dict={
                "provider1": provider1,
                "provider2": provider2,
                "provider3": provider3
            }
        )
        
        result = await service._route_to_provider(
            prompt="Test",
            model="gpt-4",
            temperature=0.3,
            max_tokens=500,
            response_format="json"
        )
        
        assert result["provider"] == "provider3"
        assert provider1.call_count == 1
        assert provider2.call_count == 1
        assert provider3.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
