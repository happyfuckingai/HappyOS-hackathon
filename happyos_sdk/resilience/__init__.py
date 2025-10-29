"""
HappyOS Resilience Framework

Provides fault tolerance patterns including circuit breakers, retries,
and error handling for robust agent systems.
"""

from .circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, get_circuit_breaker,
    reset_all_circuit_breakers, get_all_circuit_breaker_status
)
from .retry import (
    # Error handling and retry logic
    UnifiedErrorCode, UnifiedError, UnifiedErrorHandler, ErrorRecoveryStrategy,
    get_error_handler
)

__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "get_circuit_breaker",
    "reset_all_circuit_breakers", 
    "get_all_circuit_breaker_status",
    
    # Error Handling & Retry
    "UnifiedErrorCode",
    "UnifiedError",
    "UnifiedErrorHandler",
    "ErrorRecoveryStrategy",
    "get_error_handler",
]