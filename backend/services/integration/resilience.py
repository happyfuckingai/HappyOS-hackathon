"""
Resilience patterns for service integration

Provides circuit breaker, retry logic, and graceful degradation
for reliable service communication.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, List

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry logic with exponential backoff"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class TimeoutConfig:
    """Configuration for timeout handling"""
    default_timeout: int = 30  # seconds
    connection_timeout: int = 10
    read_timeout: int = 20
    write_timeout: int = 10


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3


class RetryHandler:
    """
    Retry handler with exponential backoff and jitter.
    
    Implements exponential backoff with optional jitter to prevent
    thundering herd problems when multiple clients retry simultaneously.
    """
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.RetryHandler")
    
    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with retry logic"""
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/{self.config.max_attempts}")
                result = await operation(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"Operation succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                self.logger.warning(
                    f"Attempt {attempt + 1} failed: {str(e)}"
                )
                
                if attempt < self.config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    self.logger.debug(f"Waiting {delay:.2f}s before retry")
                    await asyncio.sleep(delay)
        
        self.logger.error(
            f"All {self.config.max_attempts} attempts failed. "
            f"Last error: {str(last_exception)}"
        )
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and optional jitter"""
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay
        )
        
        if self.config.jitter:
            # Add jitter: ±25% of the calculated delay
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class CircuitBreaker:
    """
    Enhanced circuit breaker implementation for service communication.
    
    Prevents cascading failures by temporarily blocking requests to
    failing services and allowing them time to recover.
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.logger = logging.getLogger(f"{__name__}.CircuitBreaker")
    
    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation through circuit breaker"""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. "
                    f"Will retry after {self.config.recovery_timeout}s"
                )
        
        try:
            result = await operation(*args, **kwargs)
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= self.config.recovery_timeout
    
    def _transition_to_half_open(self):
        """Transition circuit breaker to half-open state"""
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        self.logger.info("Circuit breaker transitioned to HALF_OPEN")
    
    def _on_success(self):
        """Handle successful operation"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._reset()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self._trip()
        elif (self.state == CircuitBreakerState.CLOSED and 
              self.failure_count >= self.config.failure_threshold):
            self._trip()
    
    def _reset(self):
        """Reset circuit breaker to closed state"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.logger.info("Circuit breaker RESET to CLOSED")
    
    def _trip(self):
        """Trip circuit breaker to open state"""
        self.state = CircuitBreakerState.OPEN
        self.logger.warning("Circuit breaker TRIPPED to OPEN")
    
    @property
    def is_closed(self) -> bool:
        return self.state == CircuitBreakerState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitBreakerState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitBreakerState.HALF_OPEN


class GracefulDegradationHandler:
    """
    Handles graceful degradation when service communication fails.
    
    Provides fallback responses and cached data when primary
    services are unavailable.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.GracefulDegradationHandler")
        self._fallback_cache = {}
    
    def get_fallback_summary(self, meeting_id: str) -> Dict[str, Any]:
        """Get fallback summary when summarizer is unavailable"""
        self.logger.info(f"Providing fallback summary for meeting {meeting_id}")
        
        return {
            "summary": "Summary temporarily unavailable. Please try again later.",
            "topics": [],
            "action_items": [],
            "participants": [],
            "status": "fallback",
            "message": "Summarizer service is currently unavailable"
        }
    
    def get_fallback_search_results(self, query: str) -> List[Dict[str, Any]]:
        """Get fallback search results when search is unavailable"""
        self.logger.info(f"Providing fallback search results for query: {query}")
        
        return [{
            "content": "Search temporarily unavailable",
            "relevance": 0.0,
            "source": "fallback",
            "message": "Search service is currently unavailable"
        }]
    
    def cache_response(self, key: str, response: Any, ttl: int = 300):
        """Cache response for fallback use"""
        expiry = time.time() + ttl
        self._fallback_cache[key] = {
            "data": response,
            "expiry": expiry
        }
    
    def get_cached_response(self, key: str) -> Optional[Any]:
        """Get cached response if available and not expired"""
        if key not in self._fallback_cache:
            return None
        
        cached = self._fallback_cache[key]
        if time.time() > cached["expiry"]:
            del self._fallback_cache[key]
            return None
        
        return cached["data"]


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests"""
    pass


class ServiceUnavailableError(Exception):
    """Raised when service is unavailable and no fallback is possible"""
    pass


# Factory functions for common configurations
def create_default_retry_handler() -> RetryHandler:
    """Create retry handler with default configuration"""
    config = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2.0,
        jitter=True
    )
    return RetryHandler(config)


def create_default_circuit_breaker() -> CircuitBreaker:
    """Create circuit breaker with default configuration"""
    config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        success_threshold=3
    )
    return CircuitBreaker(config)


def create_default_degradation_handler() -> GracefulDegradationHandler:
    """Create graceful degradation handler"""
    return GracefulDegradationHandler()