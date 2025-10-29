"""
HappyOS Resilience & Fault Tolerance

Enterprise-grade resilience patterns including circuit breakers,
retry strategies, and graceful degradation for AI agent systems.
"""

try:
    from .circuit_breaker import CircuitBreaker, CircuitBreakerState, CircuitBreakerError
except ImportError:
    from .circuit_breaker import CircuitBreaker
    # Fallback implementations
    class CircuitBreakerState:
        pass
    class CircuitBreakerError(Exception):
        pass

try:
    from .retry import RetryStrategy, ExponentialBackoff, LinearBackoff, FixedDelay
except ImportError:
    from .circuit_breaker import RetryStrategy
    # Fallback implementations
    class ExponentialBackoff:
        pass
    class LinearBackoff:
        pass
    class FixedDelay:
        pass

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerState", 
    "CircuitBreakerError",
    "RetryStrategy",
    "ExponentialBackoff",
    "LinearBackoff",
    "FixedDelay",
]