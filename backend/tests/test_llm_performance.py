"""
Performance tests for LLM service.

Tests:
- Latency for different providers (Bedrock vs OpenAI vs Gemini)
- Cache hit rate with realistic workload (requires full adapter)
- Concurrent requests (100+ simultaneous)
- Cost per 1000 requests

Note: These tests may take several minutes to complete and may incur costs.
Set SKIP_PERFORMANCE_TESTS=1 to skip these tests.

Usage:
    # Skip performance tests (default)
    pytest backend/tests/test_llm_performance.py -v
    
    # Run performance tests
    SKIP_PERFORMANCE_TESTS=0 pytest backend/tests/test_llm_performance.py -v -s
"""

import pytest
import asyncio
import os
import sys
import time
import statistics
from pathlib import Path
from typing import Dict, Any, List

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

# Import cost calculator and providers
from backend.core.llm.cost_calculator import LLMCostCalculator
from backend.core.llm.providers.openai_provider import OpenAIProvider
from backend.core.llm.providers.bedrock_provider import BedrockProvider
from backend.core.llm.providers.google_genai_provider import GoogleGenAIProvider


# Skip tests if performance tests are disabled
SKIP_PERF_TESTS = os.getenv("SKIP_PERFORMANCE_TESTS", "1") == "1"
skip_perf = pytest.mark.skipif(SKIP_PERF_TESTS, reason="Performance tests disabled")


@pytest.fixture
def aws_region():
    """AWS region for testing."""
    return os.getenv("AWS_REGION", "us-east-1")


@pytest.fixture
def openai_provider():
    """Create OpenAI provider for performance testing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    return OpenAIProvider(api_key=api_key)


@pytest.fixture
def bedrock_provider(aws_region):
    """Create Bedrock provider for performance testing."""
    provider = BedrockProvider(region_name=aws_region)
    if not provider.is_available():
        pytest.skip("Bedrock provider not available")
    return provider


@pytest.fixture
def google_provider():
    """Create Google GenAI provider for performance testing."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set")
    provider = GoogleGenAIProvider(api_key=api_key)
    if not provider.is_available():
        pytest.skip("Google GenAI provider not available")
    return provider



class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""
    
    def __init__(self):
        self.latencies: List[float] = []
        self.costs: List[float] = []
        self.tokens: List[int] = []
        self.errors = 0
        self.start_time = None
        self.end_time = None
    
    def record_request(
        self,
        latency_ms: float,
        cost: float,
        tokens: int,
        error: bool = False
    ):
        """Record metrics for a single request."""
        self.latencies.append(latency_ms)
        if not error:
            self.costs.append(cost)
            self.tokens.append(tokens)
        else:
            self.errors += 1
    
    def start(self):
        """Start timing."""
        self.start_time = time.time()
    
    def stop(self):
        """Stop timing."""
        self.end_time = time.time()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        total_requests = len(self.latencies)
        successful_requests = total_requests - self.errors
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "errors": self.errors,
            "error_rate_percent": (self.errors / total_requests * 100) if total_requests > 0 else 0,
            
            # Latency metrics
            "latency_ms": {
                "min": min(self.latencies) if self.latencies else 0,
                "max": max(self.latencies) if self.latencies else 0,
                "mean": statistics.mean(self.latencies) if self.latencies else 0,
                "median": statistics.median(self.latencies) if self.latencies else 0,
                "p95": statistics.quantiles(self.latencies, n=20)[18] if len(self.latencies) >= 20 else (max(self.latencies) if self.latencies else 0),
                "p99": statistics.quantiles(self.latencies, n=100)[98] if len(self.latencies) >= 100 else (max(self.latencies) if self.latencies else 0),
            },
            
            # Cost metrics
            "cost": {
                "total": sum(self.costs),
                "mean_per_request": statistics.mean(self.costs) if self.costs else 0,
                "cost_per_1000_requests": sum(self.costs) / len(self.costs) * 1000 if self.costs else 0,
            },
            
            # Token metrics
            "tokens": {
                "total": sum(self.tokens),
                "mean_per_request": statistics.mean(self.tokens) if self.tokens else 0,
            },
            
            # Throughput
            "throughput": {
                "duration_seconds": self.end_time - self.start_time if self.start_time and self.end_time else 0,
                "requests_per_second": total_requests / (self.end_time - self.start_time) if self.start_time and self.end_time and (self.end_time - self.start_time) > 0 else 0,
            }
        }


class TestProviderLatency:
    """Test latency for different LLM providers."""
    
    @skip_perf
    @pytest.mark.asyncio
    async def test_openai_latency(self, openai_provider):
        """Test OpenAI latency with multiple requests."""
        metrics = PerformanceMetrics()
        num_requests = 10
        
        print(f"\n\n=== Testing OpenAI Latency ({num_requests} requests) ===")
        metrics.start()
        
        for i in range(num_requests):
            start = time.time()
            try:
                result = await openai_provider.generate_completion(
                    prompt=f"What is {i+1} + {i+1}? Answer with just the number.",
                    model="gpt-3.5-turbo",
                    temperature=0.1,
                    max_tokens=10,
                    response_format="text"
                )
                latency_ms = (time.time() - start) * 1000
                
                cost = LLMCostCalculator.calculate_cost(
                    result.get("model", "gpt-3.5-turbo"),
                    result.get("prompt_tokens", 0),
                    result.get("completion_tokens", 0)
                )
                
                metrics.record_request(
                    latency_ms=latency_ms,
                    cost=cost,
                    tokens=result.get("tokens", 0)
                )
                
                print(f"  Request {i+1}: {latency_ms:.0f}ms")
                
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(latency_ms=latency_ms, cost=0, tokens=0, error=True)
                print(f"  Request {i+1}: ERROR - {e}")
        
        metrics.stop()
        
        summary = metrics.get_summary()
        print(f"\nOpenAI Performance Summary:")
        print(f"  Successful: {summary['successful_requests']}/{summary['total_requests']}")
        print(f"  Latency (mean): {summary['latency_ms']['mean']:.0f}ms")
        print(f"  Latency (median): {summary['latency_ms']['median']:.0f}ms")
        print(f"  Latency (p95): {summary['latency_ms']['p95']:.0f}ms")
        print(f"  Total cost: ${summary['cost']['total']:.4f}")
        
        assert summary['successful_requests'] > 0, "No successful requests"
        assert summary['latency_ms']['mean'] < 5000, "Mean latency too high"
    
    @skip_perf
    @pytest.mark.asyncio
    async def test_bedrock_latency(self, bedrock_provider):
        """Test AWS Bedrock latency with multiple requests."""
        metrics = PerformanceMetrics()
        num_requests = 10
        
        print(f"\n\n=== Testing Bedrock Latency ({num_requests} requests) ===")
        metrics.start()
        
        for i in range(num_requests):
            start = time.time()
            try:
                result = await bedrock_provider.generate_completion(
                    prompt=f"What is {i+2} + {i+2}? Answer with just the number.",
                    model="claude-3-haiku",
                    temperature=0.1,
                    max_tokens=10,
                    response_format="text"
                )
                latency_ms = (time.time() - start) * 1000
                
                cost = LLMCostCalculator.calculate_cost(
                    result.get("model", "claude-3-haiku"),
                    result.get("prompt_tokens", 0),
                    result.get("completion_tokens", 0)
                )
                
                metrics.record_request(
                    latency_ms=latency_ms,
                    cost=cost,
                    tokens=result.get("tokens", 0)
                )
                
                print(f"  Request {i+1}: {latency_ms:.0f}ms")
                
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(latency_ms=latency_ms, cost=0, tokens=0, error=True)
                print(f"  Request {i+1}: ERROR - {e}")
        
        metrics.stop()
        
        summary = metrics.get_summary()
        print(f"\nBedrock Performance Summary:")
        print(f"  Successful: {summary['successful_requests']}/{summary['total_requests']}")
        print(f"  Latency (mean): {summary['latency_ms']['mean']:.0f}ms")
        print(f"  Latency (median): {summary['latency_ms']['median']:.0f}ms")
        print(f"  Latency (p95): {summary['latency_ms']['p95']:.0f}ms")
        print(f"  Total cost: ${summary['cost']['total']:.4f}")
        
        assert summary['successful_requests'] > 0, "No successful requests"
        assert summary['latency_ms']['mean'] < 5000, "Mean latency too high"
    
    @skip_perf
    @pytest.mark.asyncio
    async def test_google_genai_latency(self, google_provider):
        """Test Google GenAI latency with multiple requests."""
        metrics = PerformanceMetrics()
        num_requests = 10
        
        print(f"\n\n=== Testing Google GenAI Latency ({num_requests} requests) ===")
        metrics.start()
        
        for i in range(num_requests):
            start = time.time()
            try:
                result = await google_provider.generate_completion(
                    prompt=f"What is {i+3} + {i+3}? Answer with just the number.",
                    model="gemini-1.5-flash",
                    temperature=0.1,
                    max_tokens=10,
                    response_format="text"
                )
                latency_ms = (time.time() - start) * 1000
                
                cost = LLMCostCalculator.calculate_cost(
                    result.get("model", "gemini-1.5-flash"),
                    result.get("prompt_tokens", 0),
                    result.get("completion_tokens", 0)
                )
                
                metrics.record_request(
                    latency_ms=latency_ms,
                    cost=cost,
                    tokens=result.get("tokens", 0)
                )
                
                print(f"  Request {i+1}: {latency_ms:.0f}ms")
                
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(latency_ms=latency_ms, cost=0, tokens=0, error=True)
                print(f"  Request {i+1}: ERROR - {e}")
        
        metrics.stop()
        
        summary = metrics.get_summary()
        print(f"\nGoogle GenAI Performance Summary:")
        print(f"  Successful: {summary['successful_requests']}/{summary['total_requests']}")
        print(f"  Latency (mean): {summary['latency_ms']['mean']:.0f}ms")
        print(f"  Latency (median): {summary['latency_ms']['median']:.0f}ms")
        print(f"  Latency (p95): {summary['latency_ms']['p95']:.0f}ms")
        print(f"  Total cost: ${summary['cost']['total']:.4f}")
        
        assert summary['successful_requests'] > 0, "No successful requests"
        assert summary['latency_ms']['mean'] < 5000, "Mean latency too high"



class TestConcurrentRequests:
    """Test concurrent request handling."""
    
    @skip_perf
    @pytest.mark.asyncio
    async def test_concurrent_requests_small_batch(self, openai_provider):
        """Test handling of 20 concurrent requests."""
        metrics = PerformanceMetrics()
        num_concurrent = 20
        
        print(f"\n\n=== Testing {num_concurrent} Concurrent Requests ===")
        
        async def make_request(request_id: int):
            """Make a single request and record metrics."""
            start = time.time()
            try:
                result = await openai_provider.generate_completion(
                    prompt=f"What is {request_id} times 2? Answer with just the number.",
                    model="gpt-3.5-turbo",
                    temperature=0.1,
                    max_tokens=10,
                    response_format="text"
                )
                latency_ms = (time.time() - start) * 1000
                
                cost = LLMCostCalculator.calculate_cost(
                    result.get("model", "gpt-3.5-turbo"),
                    result.get("prompt_tokens", 0),
                    result.get("completion_tokens", 0)
                )
                
                metrics.record_request(
                    latency_ms=latency_ms,
                    cost=cost,
                    tokens=result.get("tokens", 0)
                )
                return True
            
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(latency_ms=latency_ms, cost=0, tokens=0, error=True)
                print(f"  Request {request_id} failed: {e}")
                return False
        
        # Execute concurrent requests
        metrics.start()
        tasks = [make_request(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        metrics.stop()
        
        summary = metrics.get_summary()
        print(f"\nConcurrent Requests Performance ({num_concurrent} requests):")
        print(f"  Successful: {summary['successful_requests']}/{summary['total_requests']}")
        print(f"  Error rate: {summary['error_rate_percent']:.1f}%")
        print(f"  Total duration: {summary['throughput']['duration_seconds']:.2f}s")
        print(f"  Throughput: {summary['throughput']['requests_per_second']:.2f} req/s")
        print(f"  Mean latency: {summary['latency_ms']['mean']:.0f}ms")
        print(f"  P95 latency: {summary['latency_ms']['p95']:.0f}ms")
        print(f"  Total cost: ${summary['cost']['total']:.4f}")
        
        assert summary['successful_requests'] >= num_concurrent * 0.8, "Too many failures"
        assert summary['error_rate_percent'] < 30, "Error rate too high"
    
    @skip_perf
    @pytest.mark.asyncio
    async def test_concurrent_requests_large_batch(self, openai_provider):
        """Test handling of 100+ concurrent requests."""
        metrics = PerformanceMetrics()
        num_concurrent = 100
        
        print(f"\n\n=== Testing {num_concurrent} Concurrent Requests ===")
        
        async def make_request(request_id: int):
            """Make a single request and record metrics."""
            start = time.time()
            try:
                result = await openai_provider.generate_completion(
                    prompt=f"Count to {(request_id % 5) + 1}",
                    model="gpt-3.5-turbo",
                    temperature=0.1,
                    max_tokens=20,
                    response_format="text"
                )
                latency_ms = (time.time() - start) * 1000
                
                cost = LLMCostCalculator.calculate_cost(
                    result.get("model", "gpt-3.5-turbo"),
                    result.get("prompt_tokens", 0),
                    result.get("completion_tokens", 0)
                )
                
                metrics.record_request(
                    latency_ms=latency_ms,
                    cost=cost,
                    tokens=result.get("tokens", 0)
                )
                return True
            
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(latency_ms=latency_ms, cost=0, tokens=0, error=True)
                return False
        
        # Execute concurrent requests
        metrics.start()
        tasks = [make_request(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        metrics.stop()
        
        summary = metrics.get_summary()
        print(f"\nLarge Batch Concurrent Requests Performance ({num_concurrent} requests):")
        print(f"  Successful: {summary['successful_requests']}/{summary['total_requests']}")
        print(f"  Error rate: {summary['error_rate_percent']:.1f}%")
        print(f"  Total duration: {summary['throughput']['duration_seconds']:.2f}s")
        print(f"  Throughput: {summary['throughput']['requests_per_second']:.2f} req/s")
        print(f"  Mean latency: {summary['latency_ms']['mean']:.0f}ms")
        print(f"  Median latency: {summary['latency_ms']['median']:.0f}ms")
        print(f"  P95 latency: {summary['latency_ms']['p95']:.0f}ms")
        print(f"  P99 latency: {summary['latency_ms']['p99']:.0f}ms")
        print(f"  Total cost: ${summary['cost']['total']:.4f}")
        
        assert summary['successful_requests'] >= num_concurrent * 0.7, "Too many failures"
        assert summary['error_rate_percent'] < 40, "Error rate too high"


class TestCostPer1000Requests:
    """Test cost per 1000 requests for different models."""
    
    @skip_perf
    @pytest.mark.asyncio
    async def test_cost_per_1000_requests_gpt35(self, openai_provider):
        """Test cost per 1000 requests for GPT-3.5-turbo."""
        metrics = PerformanceMetrics()
        num_requests = 20
        
        print(f"\n\n=== Testing Cost for GPT-3.5-turbo ({num_requests} requests) ===")
        metrics.start()
        
        for i in range(num_requests):
            try:
                result = await openai_provider.generate_completion(
                    prompt=f"Summarize the key points from meeting {i+1}. Keep it brief.",
                    model="gpt-3.5-turbo",
                    temperature=0.3,
                    max_tokens=100,
                    response_format="text"
                )
                
                cost = LLMCostCalculator.calculate_cost(
                    result.get("model", "gpt-3.5-turbo"),
                    result.get("prompt_tokens", 0),
                    result.get("completion_tokens", 0)
                )
                
                metrics.record_request(
                    latency_ms=0,
                    cost=cost,
                    tokens=result.get("tokens", 0)
                )
                
                if (i + 1) % 5 == 0:
                    print(f"  Completed {i+1}/{num_requests} requests...")
            
            except Exception as e:
                metrics.record_request(latency_ms=0, cost=0, tokens=0, error=True)
                print(f"  Request {i+1} failed: {e}")
        
        metrics.stop()
        
        summary = metrics.get_summary()
        cost_per_1000 = summary['cost']['cost_per_1000_requests']
        
        print(f"\nGPT-3.5-turbo Cost Analysis:")
        print(f"  Sample size: {summary['successful_requests']} requests")
        print(f"  Total cost: ${summary['cost']['total']:.4f}")
        print(f"  Mean cost per request: ${summary['cost']['mean_per_request']:.6f}")
        print(f"  Estimated cost per 1000 requests: ${cost_per_1000:.2f}")
        print(f"  Mean tokens per request: {summary['tokens']['mean_per_request']:.0f}")
        
        assert summary['successful_requests'] > 0, "No successful requests"
        assert cost_per_1000 > 0, "Cost calculation failed"
        assert cost_per_1000 < 10, "Cost per 1000 requests too high for GPT-3.5"
    
    @skip_perf
    @pytest.mark.asyncio
    async def test_cost_per_1000_requests_gpt4(self, openai_provider):
        """Test cost per 1000 requests for GPT-4."""
        metrics = PerformanceMetrics()
        num_requests = 10
        
        print(f"\n\n=== Testing Cost for GPT-4 ({num_requests} requests) ===")
        metrics.start()
        
        for i in range(num_requests):
            try:
                result = await openai_provider.generate_completion(
                    prompt=f"Analyze meeting {i+1} and provide insights.",
                    model="gpt-4",
                    temperature=0.3,
                    max_tokens=100,
                    response_format="text"
                )
                
                cost = LLMCostCalculator.calculate_cost(
                    result.get("model", "gpt-4"),
                    result.get("prompt_tokens", 0),
                    result.get("completion_tokens", 0)
                )
                
                metrics.record_request(
                    latency_ms=0,
                    cost=cost,
                    tokens=result.get("tokens", 0)
                )
                
                print(f"  Completed {i+1}/{num_requests} requests...")
            
            except Exception as e:
                metrics.record_request(latency_ms=0, cost=0, tokens=0, error=True)
                print(f"  Request {i+1} failed: {e}")
        
        metrics.stop()
        
        summary = metrics.get_summary()
        cost_per_1000 = summary['cost']['cost_per_1000_requests']
        
        print(f"\nGPT-4 Cost Analysis:")
        print(f"  Sample size: {summary['successful_requests']} requests")
        print(f"  Total cost: ${summary['cost']['total']:.4f}")
        print(f"  Mean cost per request: ${summary['cost']['mean_per_request']:.6f}")
        print(f"  Estimated cost per 1000 requests: ${cost_per_1000:.2f}")
        print(f"  Mean tokens per request: {summary['tokens']['mean_per_request']:.0f}")
        
        assert summary['successful_requests'] > 0, "No successful requests"
        assert cost_per_1000 > 0, "Cost calculation failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

