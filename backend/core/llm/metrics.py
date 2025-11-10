"""
Prometheus metrics for LLM service monitoring.

This module provides comprehensive metrics collection for LLM operations including:
- Request counts per agent, model, and provider
- Request duration histograms
- Token usage tracking
- Cache hit/miss rates
- Error tracking by type
"""

import logging
from typing import Optional
from contextlib import contextmanager
import time

try:
    from prometheus_client import Counter, Histogram, Gauge
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock classes for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self


logger = logging.getLogger(__name__)


class LLMMetrics:
    """
    Centralized metrics collection for LLM operations.
    
    Tracks:
    - Total requests by agent, model, and provider
    - Request duration distribution
    - Token usage
    - Cache performance
    - Error rates
    """
    
    def __init__(self):
        """Initialize LLM metrics collectors."""
        self.logger = logger
        self._setup_metrics()
        
        if PROMETHEUS_AVAILABLE:
            self.logger.info("LLM Prometheus metrics initialized")
        else:
            self.logger.warning(
                "Prometheus client not available - LLM metrics will be no-op"
            )
    
    def _setup_metrics(self):
        """Initialize all Prometheus metrics for LLM operations."""
        
        # Request counter - tracks all LLM requests
        self.llm_requests_total = Counter(
            'llm_requests_total',
            'Total number of LLM requests',
            ['agent_id', 'model', 'provider', 'status']
        )
        
        # Request duration histogram
        self.llm_request_duration_seconds = Histogram(
            'llm_request_duration_seconds',
            'LLM request duration in seconds',
            ['agent_id', 'model', 'provider'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
        )
        
        # Token usage counter
        self.llm_tokens_used_total = Counter(
            'llm_tokens_used_total',
            'Total number of tokens used',
            ['agent_id', 'model', 'provider', 'token_type']
        )
        
        # Cache hit counter
        self.llm_cache_hits_total = Counter(
            'llm_cache_hits_total',
            'Total number of LLM cache hits',
            ['agent_id', 'model']
        )
        
        # Cache miss counter
        self.llm_cache_misses_total = Counter(
            'llm_cache_misses_total',
            'Total number of LLM cache misses',
            ['agent_id', 'model']
        )
        
        # Error counter
        self.llm_errors_total = Counter(
            'llm_errors_total',
            'Total number of LLM errors',
            ['agent_id', 'model', 'provider', 'error_type']
        )
        
        # Cost tracking (in USD)
        self.llm_cost_total = Counter(
            'llm_cost_total',
            'Total LLM cost in USD',
            ['agent_id', 'model', 'provider']
        )
        
        # Active requests gauge
        self.llm_active_requests = Gauge(
            'llm_active_requests',
            'Number of active LLM requests',
            ['agent_id', 'provider']
        )
        
        # Cache size gauge
        self.llm_cache_size = Gauge(
            'llm_cache_size',
            'Number of items in LLM cache',
            ['tenant_id']
        )
    
    def record_request(
        self,
        agent_id: str,
        model: str,
        provider: str,
        status: str,
        duration_seconds: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached: bool = False,
        cost: float = 0.0
    ):
        """
        Record a complete LLM request with all metrics.
        
        Args:
            agent_id: Agent making the request
            model: Model used
            provider: Provider used (openai, bedrock, genai)
            status: Request status (success, error, timeout)
            duration_seconds: Request duration
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            cached: Whether response was from cache
            cost: Estimated cost in USD
        """
        # Record request count
        self.llm_requests_total.labels(
            agent_id=agent_id,
            model=model,
            provider=provider,
            status=status
        ).inc()
        
        # Record duration
        self.llm_request_duration_seconds.labels(
            agent_id=agent_id,
            model=model,
            provider=provider
        ).observe(duration_seconds)
        
        # Record token usage
        if prompt_tokens > 0:
            self.llm_tokens_used_total.labels(
                agent_id=agent_id,
                model=model,
                provider=provider,
                token_type='prompt'
            ).inc(prompt_tokens)
        
        if completion_tokens > 0:
            self.llm_tokens_used_total.labels(
                agent_id=agent_id,
                model=model,
                provider=provider,
                token_type='completion'
            ).inc(completion_tokens)
        
        # Record cache hit/miss
        if cached:
            self.llm_cache_hits_total.labels(
                agent_id=agent_id,
                model=model
            ).inc()
        else:
            self.llm_cache_misses_total.labels(
                agent_id=agent_id,
                model=model
            ).inc()
        
        # Record cost
        if cost > 0:
            self.llm_cost_total.labels(
                agent_id=agent_id,
                model=model,
                provider=provider
            ).inc(cost)
    
    def record_error(
        self,
        agent_id: str,
        model: str,
        provider: str,
        error_type: str
    ):
        """
        Record an LLM error.
        
        Args:
            agent_id: Agent that encountered the error
            model: Model being used
            provider: Provider being used
            error_type: Type of error (timeout, rate_limit, api_error, etc.)
        """
        self.llm_errors_total.labels(
            agent_id=agent_id,
            model=model,
            provider=provider,
            error_type=error_type
        ).inc()
    
    def record_cache_hit(self, agent_id: str, model: str):
        """Record a cache hit."""
        self.llm_cache_hits_total.labels(
            agent_id=agent_id,
            model=model
        ).inc()
    
    def record_cache_miss(self, agent_id: str, model: str):
        """Record a cache miss."""
        self.llm_cache_misses_total.labels(
            agent_id=agent_id,
            model=model
        ).inc()
    
    def set_cache_size(self, tenant_id: str, size: int):
        """
        Set the current cache size.
        
        Args:
            tenant_id: Tenant identifier
            size: Number of items in cache
        """
        self.llm_cache_size.labels(tenant_id=tenant_id).set(size)
    
    def increment_active_requests(self, agent_id: str, provider: str):
        """Increment active request counter."""
        self.llm_active_requests.labels(
            agent_id=agent_id,
            provider=provider
        ).inc()
    
    def decrement_active_requests(self, agent_id: str, provider: str):
        """Decrement active request counter."""
        self.llm_active_requests.labels(
            agent_id=agent_id,
            provider=provider
        ).dec()
    
    @contextmanager
    def track_request(
        self,
        agent_id: str,
        model: str,
        provider: str
    ):
        """
        Context manager to track an LLM request.
        
        Usage:
            with metrics.track_request("agent.id", "gpt-4", "openai"):
                result = await llm_service.generate_completion(...)
        
        Args:
            agent_id: Agent making the request
            model: Model being used
            provider: Provider being used
        """
        start_time = time.time()
        self.increment_active_requests(agent_id, provider)
        
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.decrement_active_requests(agent_id, provider)
            
            # Duration is recorded separately by the caller
            # This just ensures active requests are tracked


# Global metrics instance
_llm_metrics: Optional[LLMMetrics] = None


def get_llm_metrics() -> LLMMetrics:
    """
    Get or create the global LLM metrics instance.
    
    Returns:
        LLMMetrics instance
    """
    global _llm_metrics
    if _llm_metrics is None:
        _llm_metrics = LLMMetrics()
    return _llm_metrics
