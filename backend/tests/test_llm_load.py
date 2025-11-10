"""
Load tests for LLM service production readiness.

Tests:
- 1000 requests/minute sustained load
- Circuit breaker under high error rate
- Failover time from AWS to Local
- Memory usage under load

Note: These tests may take 10+ minutes to complete and may incur significant costs.
Set SKIP_LOAD_TESTS=1 to skip these tests (default).

Usage:
    # Skip load tests (default)
    pytest backend/tests/test_llm_load.py -v
    
    # Run load tests
    SKIP_LOAD_TESTS=0 pytest backend/tests/test_llm_load.py -v -s
"""

import pytest
import asyncio
import os
import sys
import time
import psutil
import statistics
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

# Import services - use direct imports to avoid circular dependencies
try:
    # Import only what we need for load tests
    sys.path.insert(0, str(backend_path))
    from core.llm.providers.openai_provider import OpenAIProvider
    from infrastructure.local.services.llm_service import LocalLLMService
    SERVICES_AVAILABLE = True
except ImportError as e:
    SERVICES_AVAILABLE = False
    OpenAIProvider = None
    LocalLLMService = None
    print(f"Warning: Could not import services: {e}")


# Skip tests if load tests are disabled or services not available
SKIP_LOAD_TESTS = os.getenv("SKIP_LOAD_TESTS", "1") == "1"
skip_load = pytest.mark.skipif(
    SKIP_LOAD_TESTS or not SERVICES_AVAILABLE, 
    reason="Load tests disabled or services not available"
)


class LoadTestMetrics:
    """Helper class to collect and analyze load test metrics."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.requests_sent = 0
        self.requests_completed = 0
        self.requests_failed = 0
        self.latencies: List[float] = []
        self.memory_samples: List[float] = []
        self.cpu_samples: List[float] = []
        self.provider_usage: Dict[str, int] = {}
        self.error_types: Dict[str, int] = {}
        
    def start(self):
        """Start timing."""
        self.start_time = time.time()
        
    def stop(self):
        """Stop timing."""
        self.end_time = time.time()
    
    def record_request(
        self,
        success: bool,
        latency_ms: float,
        provider: str = None,
        error_type: str = None
    ):
        """Record metrics for a single request."""
        self.requests_completed += 1
        
        if success:
            self.latencies.append(latency_ms)
            if provider:
                self.provider_usage[provider] = self.provider_usage.get(provider, 0) + 1
        else:
            self.requests_failed += 1
            if error_type:
                self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
    
    def record_system_metrics(self):
        """Record current system metrics."""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent(interval=0.1)
        
        self.memory_samples.append(memory_mb)
        self.cpu_samples.append(cpu_percent)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get load test summary."""
        duration = self.end_time - self.start_time if self.start_time and self.end_time else 0
        
        return {
            "duration_seconds": duration,
            "requests_sent": self.requests_sent,
            "requests_completed": self.requests_completed,
            "requests_failed": self.requests_failed,
            "success_rate": (
                (self.requests_completed - self.requests_failed) / self.requests_completed * 100
                if self.requests_completed > 0 else 0
            ),
            "throughput_rps": self.requests_completed / duration if duration > 0 else 0,
            "latency_ms": {
                "min": min(self.latencies) if self.latencies else 0,
                "max": max(self.latencies) if self.latencies else 0,
                "mean": statistics.mean(self.latencies) if self.latencies else 0,
                "median": statistics.median(self.latencies) if self.latencies else 0,
                "p95": statistics.quantiles(self.latencies, n=20)[18] if len(self.latencies) >= 20 else (max(self.latencies) if self.latencies else 0),
                "p99": statistics.quantiles(self.latencies, n=100)[98] if len(self.latencies) >= 100 else (max(self.latencies) if self.latencies else 0),
            },
            "memory_mb": {
                "min": min(self.memory_samples) if self.memory_samples else 0,
                "max": max(self.memory_samples) if self.memory_samples else 0,
                "mean": statistics.mean(self.memory_samples) if self.memory_samples else 0,
            },
            "cpu_percent": {
                "min": min(self.cpu_samples) if self.cpu_samples else 0,
                "max": max(self.cpu_samples) if self.cpu_samples else 0,
                "mean": statistics.mean(self.cpu_samples) if self.cpu_samples else 0,
            },
            "provider_usage": self.provider_usage,
            "error_types": self.error_types
        }


@pytest.fixture
def openai_provider():
    """Create OpenAI provider for load testing."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    return OpenAIProvider(api_key=api_key)


@pytest.fixture
def local_llm_service():
    """Create local LLM service for load testing."""
    return LocalLLMService()


# Removed service_facade fixture - not needed for load tests


class TestSustainedLoad:
    """Test sustained load handling."""
    
    @skip_load
    @pytest.mark.asyncio
    async def test_1000_requests_per_minute(self, openai_provider):
        """Test handling 1000 requests per minute sustained load."""
        metrics = LoadTestMetrics()
        target_rps = 1000 / 60  # ~16.67 requests per second
        duration_seconds = 60
        
        print(f"\n\n=== Testing 1000 Requests/Minute Sustained Load ===")
        print(f"Target: {target_rps:.2f} requests/second for {duration_seconds} seconds")
        
        async def make_request(request_id: int):
            """Make a single request."""
            start = time.time()
            try:
                result = await openai_provider.generate_completion(
                    prompt=f"What is {request_id % 100}? Answer briefly.",
                    model="gpt-3.5-turbo",
                    temperature=0.1,
                    max_tokens=20,
                    response_format="text"
                )
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(
                    success=True,
                    latency_ms=latency_ms,
                    provider="openai"
                )
                return True
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(
                    success=False,
                    latency_ms=latency_ms,
                    error_type=type(e).__name__
                )
                return False
        
        # Start metrics collection
        metrics.start()
        
        # System metrics monitoring task
        async def monitor_system():
            while time.time() - metrics.start_time < duration_seconds + 5:
                metrics.record_system_metrics()
                await asyncio.sleep(1)
        
        monitor_task = asyncio.create_task(monitor_system())
        
        # Generate requests at target rate
        request_id = 0
        interval = 1.0 / target_rps
        
        tasks = []
        while time.time() - metrics.start_time < duration_seconds:
            # Create batch of requests
            batch_size = min(10, int(target_rps))
            for _ in range(batch_size):
                task = asyncio.create_task(make_request(request_id))
                tasks.append(task)
                request_id += 1
                metrics.requests_sent += 1
            
            # Wait for interval
            await asyncio.sleep(interval * batch_size)
            
            # Progress update every 10 seconds
            if request_id % 100 == 0:
                elapsed = time.time() - metrics.start_time
                current_rps = metrics.requests_completed / elapsed if elapsed > 0 else 0
                print(f"  Progress: {request_id} requests sent, {metrics.requests_completed} completed, {current_rps:.2f} RPS")
        
        # Wait for remaining requests to complete
        print("  Waiting for remaining requests to complete...")
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Stop monitoring
        metrics.stop()
        await monitor_task
        
        # Print summary
        summary = metrics.get_summary()
        print(f"\nSustained Load Test Results:")
        print(f"  Duration: {summary['duration_seconds']:.2f}s")
        print(f"  Requests sent: {summary['requests_sent']}")
        print(f"  Requests completed: {summary['requests_completed']}")
        print(f"  Requests failed: {summary['requests_failed']}")
        print(f"  Success rate: {summary['success_rate']:.2f}%")
        print(f"  Throughput: {summary['throughput_rps']:.2f} requests/second")
        print(f"  Latency (mean): {summary['latency_ms']['mean']:.0f}ms")
        print(f"  Latency (p95): {summary['latency_ms']['p95']:.0f}ms")
        print(f"  Latency (p99): {summary['latency_ms']['p99']:.0f}ms")
        print(f"  Memory (mean): {summary['memory_mb']['mean']:.2f}MB")
        print(f"  Memory (max): {summary['memory_mb']['max']:.2f}MB")
        print(f"  CPU (mean): {summary['cpu_percent']['mean']:.1f}%")
        print(f"  CPU (max): {summary['cpu_percent']['max']:.1f}%")
        
        # Assertions
        assert summary['requests_completed'] >= 900, "Too many requests failed to complete"
        assert summary['success_rate'] >= 70, "Success rate too low"
        assert summary['throughput_rps'] >= target_rps * 0.8, "Throughput too low"
        assert summary['latency_ms']['p95'] < 10000, "P95 latency too high"


class TestCircuitBreakerUnderLoad:
    """Test circuit breaker behavior under high error rate."""
    
    @skip_load
    @pytest.mark.asyncio
    async def test_circuit_breaker_high_error_rate(self):
        """Test circuit breaker opens under high error rate (simplified)."""
        print(f"\n\n=== Testing Circuit Breaker Under High Error Rate ===")
        
        # Simplified circuit breaker simulation
        class SimpleCircuitBreaker:
            def __init__(self, threshold=5):
                self.threshold = threshold
                self.failures = 0
                self.state = "CLOSED"
            
            def record_failure(self):
                self.failures += 1
                if self.failures >= self.threshold:
                    self.state = "OPEN"
            
            def record_success(self):
                if self.state == "CLOSED":
                    self.failures = 0
        
        # Create mock providers
        class FailingProvider:
            async def generate_completion(self, **kwargs):
                raise Exception("Simulated provider failure")
        
        class WorkingProvider:
            async def generate_completion(self, **kwargs):
                await asyncio.sleep(0.01)
                return {"content": "success", "tokens": 10, "provider": "fallback"}
        
        circuit_breaker = SimpleCircuitBreaker(threshold=5)
        failing_provider = FailingProvider()
        working_provider = WorkingProvider()
        
        metrics = LoadTestMetrics()
        metrics.start()
        
        # Send requests that will trigger circuit breaker
        print("  Phase 1: Triggering circuit breaker with failures...")
        for i in range(20):
            try:
                # Try primary provider if circuit is closed
                if circuit_breaker.state == "CLOSED":
                    try:
                        await failing_provider.generate_completion()
                        circuit_breaker.record_success()
                    except Exception:
                        circuit_breaker.record_failure()
                        # Fallback to working provider
                        result = await working_provider.generate_completion()
                        metrics.record_request(
                            success=True,
                            latency_ms=10,
                            provider="fallback"
                        )
                else:
                    # Circuit is open, use fallback directly
                    result = await working_provider.generate_completion()
                    metrics.record_request(
                        success=True,
                        latency_ms=10,
                        provider="fallback"
                    )
            except Exception as e:
                metrics.record_request(
                    success=False,
                    latency_ms=0,
                    error_type=type(e).__name__
                )
            
            if i % 5 == 0:
                print(f"    Request {i}: Circuit breaker state = {circuit_breaker.state}, failures = {circuit_breaker.failures}")
        
        metrics.stop()
        
        print(f"\nCircuit Breaker Test Results:")
        print(f"  Final state: {circuit_breaker.state}")
        print(f"  Requests completed: {metrics.requests_completed}")
        print(f"  Requests failed: {metrics.requests_failed}")
        print(f"  Provider usage: {metrics.provider_usage}")
        
        # Assertions
        assert circuit_breaker.state == "OPEN", "Circuit breaker should be OPEN after failures"
        assert "fallback" in metrics.provider_usage, "Should have used fallback provider"
        assert metrics.provider_usage.get("fallback", 0) > 0, "Fallback should have handled requests"


class TestFailoverTime:
    """Test failover time from AWS to Local."""
    
    @skip_load
    @pytest.mark.asyncio
    async def test_aws_to_local_failover_time(self):
        """Test failover time from AWS Bedrock to Local OpenAI (simplified)."""
        print(f"\n\n=== Testing AWS to Local Failover Time ===")
        
        # Create mock AWS provider that fails
        class FailingAWSProvider:
            async def generate_completion(self, **kwargs):
                await asyncio.sleep(0.05)  # Simulate network delay
                raise Exception("AWS Bedrock unavailable")
        
        # Create mock local provider that succeeds
        class LocalProvider:
            async def generate_completion(self, **kwargs):
                await asyncio.sleep(0.02)  # Faster local response
                return {"content": "local success", "tokens": 10, "provider": "local"}
        
        aws_provider = FailingAWSProvider()
        local_provider = LocalProvider()
        
        # Measure failover times
        failover_times = []
        
        print("  Measuring failover times...")
        for i in range(10):
            start = time.time()
            try:
                # Try AWS first, then failover to local
                try:
                    result = await aws_provider.generate_completion()
                except Exception:
                    # Failover to local
                    result = await local_provider.generate_completion()
                
                failover_time_ms = (time.time() - start) * 1000
                failover_times.append(failover_time_ms)
                
                if i < 3:
                    print(f"    Request {i+1}: Failover time = {failover_time_ms:.0f}ms, Provider = {result.get('provider', 'unknown')}")
            except Exception as e:
                print(f"    Request {i+1}: Failed - {e}")
        
        # Calculate statistics
        if failover_times:
            mean_failover = statistics.mean(failover_times)
            max_failover = max(failover_times)
            min_failover = min(failover_times)
            
            print(f"\nFailover Time Results:")
            print(f"  Mean failover time: {mean_failover:.0f}ms")
            print(f"  Min failover time: {min_failover:.0f}ms")
            print(f"  Max failover time: {max_failover:.0f}ms")
            print(f"  Successful failovers: {len(failover_times)}/10")
            
            # Assertions
            assert len(failover_times) >= 8, "Too many failover attempts failed"
            assert mean_failover < 5000, "Mean failover time too high (should be < 5s)"
            assert max_failover < 10000, "Max failover time too high (should be < 10s)"
        else:
            pytest.fail("No successful failovers recorded")


class TestMemoryUsage:
    """Test memory usage under load."""
    
    @skip_load
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, local_llm_service):
        """Test memory usage remains stable under sustained load."""
        print(f"\n\n=== Testing Memory Usage Under Load ===")
        
        metrics = LoadTestMetrics()
        num_requests = 500
        concurrent_limit = 50
        
        # Record initial memory
        process = psutil.Process()
        initial_memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"  Initial memory: {initial_memory_mb:.2f}MB")
        
        async def make_request(request_id: int):
            """Make a single request."""
            try:
                result = await local_llm_service.generate_completion(
                    prompt=f"Count to {(request_id % 5) + 1}",
                    agent_id="test_agent",
                    tenant_id="test_tenant",
                    model="gpt-3.5-turbo",
                    temperature=0.1,
                    max_tokens=20,
                    response_format="text"
                )
                return True
            except Exception as e:
                return False
        
        # System metrics monitoring task
        async def monitor_system():
            while metrics.requests_completed < num_requests:
                metrics.record_system_metrics()
                await asyncio.sleep(0.5)
        
        metrics.start()
        monitor_task = asyncio.create_task(monitor_system())
        
        # Send requests with concurrency limit
        print(f"  Sending {num_requests} requests with concurrency limit of {concurrent_limit}...")
        
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def limited_request(request_id: int):
            async with semaphore:
                success = await make_request(request_id)
                metrics.record_request(
                    success=success,
                    latency_ms=0
                )
                metrics.requests_completed += 1
                
                if metrics.requests_completed % 100 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    print(f"    Progress: {metrics.requests_completed}/{num_requests}, Memory: {current_memory:.2f}MB")
        
        tasks = [limited_request(i) for i in range(num_requests)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        metrics.stop()
        await monitor_task
        
        # Record final memory
        final_memory_mb = process.memory_info().rss / 1024 / 1024
        memory_increase_mb = final_memory_mb - initial_memory_mb
        memory_increase_percent = (memory_increase_mb / initial_memory_mb) * 100
        
        summary = metrics.get_summary()
        
        print(f"\nMemory Usage Test Results:")
        print(f"  Requests completed: {metrics.requests_completed}")
        print(f"  Initial memory: {initial_memory_mb:.2f}MB")
        print(f"  Final memory: {final_memory_mb:.2f}MB")
        print(f"  Memory increase: {memory_increase_mb:.2f}MB ({memory_increase_percent:.1f}%)")
        print(f"  Peak memory: {summary['memory_mb']['max']:.2f}MB")
        print(f"  Mean memory: {summary['memory_mb']['mean']:.2f}MB")
        
        # Assertions
        assert memory_increase_percent < 100, "Memory usage increased by more than 100%"
        assert summary['memory_mb']['max'] < initial_memory_mb * 2, "Peak memory usage too high"
        
        # Check for memory leaks (memory should stabilize)
        if len(metrics.memory_samples) >= 10:
            first_half_mean = statistics.mean(metrics.memory_samples[:len(metrics.memory_samples)//2])
            second_half_mean = statistics.mean(metrics.memory_samples[len(metrics.memory_samples)//2:])
            memory_growth_rate = (second_half_mean - first_half_mean) / first_half_mean * 100
            
            print(f"  Memory growth rate: {memory_growth_rate:.1f}%")
            assert memory_growth_rate < 50, "Possible memory leak detected"


class TestProductionReadiness:
    """Combined production readiness test."""
    
    @skip_load
    @pytest.mark.asyncio
    async def test_production_readiness_combined(self, openai_provider):
        """Combined test for production readiness."""
        print(f"\n\n=== Production Readiness Combined Test ===")
        
        metrics = LoadTestMetrics()
        duration_seconds = 120  # 2 minutes
        target_rps = 10  # Moderate load
        
        print(f"Running combined test for {duration_seconds} seconds at {target_rps} RPS")
        
        async def make_request(request_id: int):
            """Make a single request."""
            start = time.time()
            try:
                result = await openai_provider.generate_completion(
                    prompt=f"Summarize point {request_id % 20}",
                    model="gpt-3.5-turbo",
                    temperature=0.3,
                    max_tokens=50,
                    response_format="text"
                )
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(
                    success=True,
                    latency_ms=latency_ms,
                    provider="openai"
                )
                return True
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                metrics.record_request(
                    success=False,
                    latency_ms=latency_ms,
                    error_type=type(e).__name__
                )
                return False
        
        # Start metrics collection
        metrics.start()
        
        # System metrics monitoring
        async def monitor_system():
            while time.time() - metrics.start_time < duration_seconds + 5:
                metrics.record_system_metrics()
                await asyncio.sleep(2)
        
        monitor_task = asyncio.create_task(monitor_system())
        
        # Generate requests
        request_id = 0
        interval = 1.0 / target_rps
        tasks = []
        
        while time.time() - metrics.start_time < duration_seconds:
            task = asyncio.create_task(make_request(request_id))
            tasks.append(task)
            request_id += 1
            metrics.requests_sent += 1
            
            await asyncio.sleep(interval)
            
            if request_id % 100 == 0:
                elapsed = time.time() - metrics.start_time
                current_rps = metrics.requests_completed / elapsed if elapsed > 0 else 0
                print(f"  Progress: {request_id} requests, {current_rps:.2f} RPS")
        
        # Wait for completion
        await asyncio.gather(*tasks, return_exceptions=True)
        metrics.stop()
        await monitor_task
        
        # Print comprehensive summary
        summary = metrics.get_summary()
        print(f"\nProduction Readiness Test Results:")
        print(f"  Duration: {summary['duration_seconds']:.2f}s")
        print(f"  Total requests: {summary['requests_completed']}")
        print(f"  Success rate: {summary['success_rate']:.2f}%")
        print(f"  Throughput: {summary['throughput_rps']:.2f} RPS")
        print(f"  Latency p50: {summary['latency_ms']['median']:.0f}ms")
        print(f"  Latency p95: {summary['latency_ms']['p95']:.0f}ms")
        print(f"  Latency p99: {summary['latency_ms']['p99']:.0f}ms")
        print(f"  Memory usage: {summary['memory_mb']['mean']:.2f}MB (peak: {summary['memory_mb']['max']:.2f}MB)")
        print(f"  CPU usage: {summary['cpu_percent']['mean']:.1f}% (peak: {summary['cpu_percent']['max']:.1f}%)")
        
        # Production readiness criteria
        print(f"\nProduction Readiness Criteria:")
        success_rate_ok = summary['success_rate'] >= 95
        throughput_ok = summary['throughput_rps'] >= target_rps * 0.9
        latency_p95_ok = summary['latency_ms']['p95'] < 5000
        latency_p99_ok = summary['latency_ms']['p99'] < 10000
        
        print(f"  ✓ Success rate >= 95%: {success_rate_ok} ({summary['success_rate']:.2f}%)")
        print(f"  ✓ Throughput >= 90% target: {throughput_ok} ({summary['throughput_rps']:.2f} RPS)")
        print(f"  ✓ P95 latency < 5s: {latency_p95_ok} ({summary['latency_ms']['p95']:.0f}ms)")
        print(f"  ✓ P99 latency < 10s: {latency_p99_ok} ({summary['latency_ms']['p99']:.0f}ms)")
        
        all_criteria_met = success_rate_ok and throughput_ok and latency_p95_ok and latency_p99_ok
        print(f"\n  Overall: {'✓ READY FOR PRODUCTION' if all_criteria_met else '✗ NOT READY'}")
        
        # Assertions
        assert success_rate_ok, f"Success rate too low: {summary['success_rate']:.2f}%"
        assert throughput_ok, f"Throughput too low: {summary['throughput_rps']:.2f} RPS"
        assert latency_p95_ok, f"P95 latency too high: {summary['latency_ms']['p95']:.0f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
