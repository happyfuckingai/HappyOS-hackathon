"""
LLM-specific circuit breaker implementation with provider failover.

This module provides a specialized circuit breaker for LLM services that:
- Detects LLM-specific failures (rate limits, API errors, timeouts)
- Implements automatic failover from AWS Bedrock to OpenAI to local
- Tracks provider-specific health and performance
- Provides half-open state for recovery testing
"""

import asyncio
import time
import logging
from typing import Any, Callable, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitBreakerOpenError
from ..interfaces import CircuitState


logger = logging.getLogger(__name__)


class LLMProviderType(Enum):
    """LLM provider types."""
    AWS_BEDROCK = "aws_bedrock"
    OPENAI = "openai"
    GOOGLE_GENAI = "google_genai"
    LOCAL = "local"


@dataclass
class LLMProviderHealth:
    """Health status for an LLM provider."""
    provider: LLMProviderType
    is_available: bool = True
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0


class LLMCircuitBreaker:
    """
    Specialized circuit breaker for LLM services with provider failover.
    
    Features:
    - Provider-specific circuit breakers
    - Automatic failover cascade: AWS Bedrock -> OpenAI -> Local
    - LLM-specific error detection (rate limits, API errors)
    - Provider health tracking
    - Half-open state for recovery testing
    """
    
    def __init__(
        self,
        service_name: str = "llm_service",
        failure_threshold: int = 3,
        timeout_seconds: int = 30,
        half_open_max_calls: int = 2,
        recovery_timeout: int = 60,
        enable_provider_failover: bool = True
    ):
        """
        Initialize LLM circuit breaker.
        
        Args:
            service_name: Name of the LLM service
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Timeout for LLM calls
            half_open_max_calls: Max calls in half-open state
            recovery_timeout: Time to wait before attempting recovery
            enable_provider_failover: Enable automatic provider failover
        """
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        self.recovery_timeout = recovery_timeout
        self.enable_provider_failover = enable_provider_failover
        
        # Provider-specific circuit breakers
        self._provider_breakers: Dict[LLMProviderType, CircuitBreaker] = {}
        self._provider_health: Dict[LLMProviderType, LLMProviderHealth] = {}
        
        # Initialize circuit breakers for each provider
        self._initialize_provider_breakers()
        
        # Provider priority order (for failover)
        self.provider_priority: List[LLMProviderType] = [
            LLMProviderType.AWS_BEDROCK,
            LLMProviderType.OPENAI,
            LLMProviderType.LOCAL
        ]
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        logger.info(f"LLM circuit breaker initialized for {service_name}")
    
    def _initialize_provider_breakers(self):
        """Initialize circuit breakers for each LLM provider."""
        for provider in LLMProviderType:
            self._provider_breakers[provider] = CircuitBreaker(
                service_name=f"{self.service_name}_{provider.value}",
                failure_threshold=self.failure_threshold,
                timeout_seconds=self.timeout_seconds,
                half_open_max_calls=self.half_open_max_calls
            )
            self._provider_health[provider] = LLMProviderHealth(provider=provider)
            
            logger.debug(f"Circuit breaker initialized for provider: {provider.value}")
    
    async def call_with_failover(
        self,
        primary_provider: LLMProviderType,
        provider_functions: Dict[LLMProviderType, Callable],
        *args,
        **kwargs
    ) -> Any:
        """
        Execute LLM call with automatic provider failover.
        
        Args:
            primary_provider: Preferred provider to try first
            provider_functions: Dict mapping provider types to callable functions
            *args: Arguments to pass to provider functions
            **kwargs: Keyword arguments to pass to provider functions
            
        Returns:
            Result from successful provider call
            
        Raises:
            CircuitBreakerOpenError: When all providers are unavailable
        """
        # Reorder providers to try primary first
        providers_to_try = self._get_provider_order(primary_provider)
        
        last_exception = None
        
        for provider in providers_to_try:
            if provider not in provider_functions:
                logger.debug(f"Provider {provider.value} not available in functions")
                continue
            
            provider_func = provider_functions[provider]
            circuit_breaker = self._provider_breakers[provider]
            
            # Check if circuit breaker is open
            if circuit_breaker.state == CircuitState.OPEN:
                logger.debug(f"Circuit breaker OPEN for {provider.value}, trying next provider")
                continue
            
            try:
                logger.info(f"Attempting LLM call with provider: {provider.value}")
                
                # Execute with circuit breaker protection
                start_time = time.time()
                result = await circuit_breaker.call(provider_func, *args, **kwargs)
                latency_ms = int((time.time() - start_time) * 1000)
                
                # Update provider health on success
                await self._on_provider_success(provider, latency_ms)
                
                # Add provider info to result
                if isinstance(result, dict):
                    result['provider_used'] = provider.value
                
                logger.info(f"LLM call succeeded with provider: {provider.value}")
                return result
                
            except CircuitBreakerOpenError as e:
                logger.warning(f"Circuit breaker open for {provider.value}: {e}")
                last_exception = e
                continue
                
            except Exception as e:
                logger.warning(f"LLM call failed with provider {provider.value}: {e}")
                await self._on_provider_failure(provider, e)
                last_exception = e
                
                # If failover is disabled, raise immediately
                if not self.enable_provider_failover:
                    raise
                
                continue
        
        # All providers failed
        error_msg = (
            f"All LLM providers failed for {self.service_name}. "
            f"Last error: {last_exception}"
        )
        logger.error(error_msg)
        raise CircuitBreakerOpenError(error_msg)
    
    def _get_provider_order(self, primary_provider: LLMProviderType) -> List[LLMProviderType]:
        """
        Get provider order with primary provider first.
        
        Args:
            primary_provider: Provider to try first
            
        Returns:
            Ordered list of providers to try
        """
        # Start with primary provider
        providers = [primary_provider]
        
        # Add remaining providers in priority order
        for provider in self.provider_priority:
            if provider != primary_provider:
                providers.append(provider)
        
        return providers
    
    async def _on_provider_success(self, provider: LLMProviderType, latency_ms: int):
        """
        Handle successful provider call.
        
        Args:
            provider: Provider that succeeded
            latency_ms: Call latency in milliseconds
        """
        async with self._lock:
            health = self._provider_health[provider]
            health.is_available = True
            health.last_success_time = datetime.now()
            health.consecutive_failures = 0
            health.total_requests += 1
            health.successful_requests += 1
            
            # Update average latency (exponential moving average)
            alpha = 0.3  # Smoothing factor
            if health.average_latency_ms == 0:
                health.average_latency_ms = latency_ms
            else:
                health.average_latency_ms = (
                    alpha * latency_ms + (1 - alpha) * health.average_latency_ms
                )
    
    async def _on_provider_failure(self, provider: LLMProviderType, error: Exception):
        """
        Handle failed provider call.
        
        Args:
            provider: Provider that failed
            error: Exception that occurred
        """
        async with self._lock:
            health = self._provider_health[provider]
            health.last_failure_time = datetime.now()
            health.consecutive_failures += 1
            health.total_requests += 1
            health.failed_requests += 1
            
            # Mark as unavailable if too many consecutive failures
            if health.consecutive_failures >= self.failure_threshold:
                health.is_available = False
                logger.warning(
                    f"Provider {provider.value} marked as unavailable after "
                    f"{health.consecutive_failures} consecutive failures"
                )
    
    def get_provider_health(self, provider: LLMProviderType) -> LLMProviderHealth:
        """Get health status for a specific provider."""
        return self._provider_health.get(provider)
    
    def get_all_provider_health(self) -> Dict[LLMProviderType, LLMProviderHealth]:
        """Get health status for all providers."""
        return self._provider_health.copy()
    
    def get_provider_state(self, provider: LLMProviderType) -> CircuitState:
        """Get circuit breaker state for a specific provider."""
        breaker = self._provider_breakers.get(provider)
        return breaker.get_state() if breaker else CircuitState.OPEN
    
    def get_all_provider_states(self) -> Dict[LLMProviderType, CircuitState]:
        """Get circuit breaker states for all providers."""
        return {
            provider: breaker.get_state()
            for provider, breaker in self._provider_breakers.items()
        }
    
    async def force_provider_recovery(self, provider: LLMProviderType):
        """
        Force a provider to attempt recovery.
        
        Args:
            provider: Provider to force recovery for
        """
        async with self._lock:
            breaker = self._provider_breakers.get(provider)
            if breaker:
                breaker.force_close()
                
                health = self._provider_health[provider]
                health.is_available = True
                health.consecutive_failures = 0
                
                logger.info(f"Forced recovery for provider: {provider.value}")
    
    def reset_provider_stats(self, provider: Optional[LLMProviderType] = None):
        """
        Reset statistics for a provider or all providers.
        
        Args:
            provider: Specific provider to reset, or None for all
        """
        if provider:
            breaker = self._provider_breakers.get(provider)
            if breaker:
                breaker.reset_stats()
            self._provider_health[provider] = LLMProviderHealth(provider=provider)
            logger.info(f"Reset stats for provider: {provider.value}")
        else:
            for p in LLMProviderType:
                breaker = self._provider_breakers.get(p)
                if breaker:
                    breaker.reset_stats()
                self._provider_health[p] = LLMProviderHealth(provider=p)
            logger.info("Reset stats for all providers")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary for LLM service."""
        available_providers = [
            p.value for p, h in self._provider_health.items()
            if h.is_available
        ]
        
        total_requests = sum(h.total_requests for h in self._provider_health.values())
        total_successful = sum(h.successful_requests for h in self._provider_health.values())
        
        return {
            "service_name": self.service_name,
            "available_providers": available_providers,
            "total_providers": len(self._provider_health),
            "total_requests": total_requests,
            "overall_success_rate": (
                (total_successful / total_requests * 100) if total_requests > 0 else 100.0
            ),
            "provider_states": {
                p.value: self.get_provider_state(p).value
                for p in LLMProviderType
            },
            "provider_health": {
                p.value: {
                    "available": h.is_available,
                    "success_rate": h.success_rate,
                    "avg_latency_ms": h.average_latency_ms,
                    "consecutive_failures": h.consecutive_failures
                }
                for p, h in self._provider_health.items()
            }
        }


# Global LLM circuit breaker instance
_llm_circuit_breaker: Optional[LLMCircuitBreaker] = None


def get_llm_circuit_breaker(
    service_name: str = "llm_service",
    **kwargs
) -> LLMCircuitBreaker:
    """
    Get or create the global LLM circuit breaker instance.
    
    Args:
        service_name: Name of the LLM service
        **kwargs: Additional configuration options
        
    Returns:
        LLM circuit breaker instance
    """
    global _llm_circuit_breaker
    if _llm_circuit_breaker is None:
        _llm_circuit_breaker = LLMCircuitBreaker(service_name=service_name, **kwargs)
    return _llm_circuit_breaker


def reset_llm_circuit_breaker():
    """Reset the global LLM circuit breaker instance."""
    global _llm_circuit_breaker
    _llm_circuit_breaker = None
