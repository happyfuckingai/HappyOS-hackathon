"""
Circuit breaker and fallback coordination module.
Provides circuit breaker pattern implementation, health monitoring, and fallback management.
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerManager,
    CircuitBreakerError,
    CircuitBreakerOpenError,
    CircuitBreakerTimeoutError,
    CircuitBreakerStats,
    get_circuit_breaker_manager
)

from .health_service import (
    HealthMonitoringService,
    HealthCheckResult,
    ServiceHealthMetrics,
    AWSHealthChecker,
    LocalHealthChecker,
    get_health_service
)

from .fallback_manager import (
    FallbackManager,
    FallbackConfiguration,
    ServiceMode,
    FallbackStrategy,
    ServiceTransition,
    ServiceRegistry,
    GracefulDegradationManager,
    RecoveryCoordinator,
    get_fallback_manager,
    configure_fallback_manager
)

__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerManager", 
    "CircuitBreakerError",
    "CircuitBreakerOpenError",
    "CircuitBreakerTimeoutError",
    "CircuitBreakerStats",
    "get_circuit_breaker_manager",
    
    # Health Service
    "HealthMonitoringService",
    "HealthCheckResult",
    "ServiceHealthMetrics", 
    "AWSHealthChecker",
    "LocalHealthChecker",
    "get_health_service",
    
    # Fallback Manager
    "FallbackManager",
    "FallbackConfiguration",
    "ServiceMode",
    "FallbackStrategy", 
    "ServiceTransition",
    "ServiceRegistry",
    "GracefulDegradationManager",
    "RecoveryCoordinator",
    "get_fallback_manager",
    "configure_fallback_manager"
]