"""
🛡️ ERROR HANDLING & RECOVERY MODULE

Advanced error handling and recovery system for HappyOS:
- Circuit breaker pattern for external services
- Retry mechanisms with exponential backoff
- Graceful degradation strategies
- Error classification and routing
- Recovery workflows
- Health monitoring and alerting
"""

from .circuit_breaker import CircuitBreaker, CircuitBreakerState
from .retry_manager import RetryManager, RetryPolicy, RetryResult
from .error_classifier import ErrorClassifier, ErrorSeverity, ErrorCategory
from .recovery_manager import RecoveryManager, RecoveryStrategy
from .health_monitor import HealthMonitor, ComponentHealth
from .graceful_degradation import GracefulDegradationManager, DegradationLevel

__all__ = [
    'CircuitBreaker',
    'CircuitBreakerState',
    'RetryManager',
    'RetryPolicy',
    'RetryResult',
    'ErrorClassifier',
    'ErrorSeverity',
    'ErrorCategory',
    'RecoveryManager',
    'RecoveryStrategy',
    'HealthMonitor',
    'ComponentHealth',
    'GracefulDegradationManager',
    'DegradationLevel'
]

