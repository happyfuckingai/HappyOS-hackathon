"""
Circuit Breaker - Enterprise Resilience Pattern

Production-ready circuit breaker implementation for protecting AI agent
systems against cascading failures with comprehensive monitoring.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, Dict, Union
from dataclasses import dataclass

from ..exceptions import CircuitBreakerError, ServiceUnavailableError
from ..observability.logging import get_logger


class CircuitBreakerState(Enum):
    """Circuit breaker states with enterprise context."""
    CLOSED = "closed"        # Normal operation - requests pass through
    OPEN = "open"           # Circuit is open - requests fail fast
    HALF_OPEN = "half_open" # Testing recovery - limited requests allowed


@dataclass
class CircuitBreakerConfig:
    """Enterprise circuit breaker configuration.
    
    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        success_threshold: Successes needed to close circuit from half-open
        timeout: Operation timeout in seconds
        expected_exceptions: Exception types that trigger circuit breaker
        slow_call_threshold: Threshold for considering calls "slow"
        slow_call_rate_threshold: Rate of slow calls that triggers opening
        minimum_throughput: Minimum calls before evaluating failure rate
    """
    
    # Basic thresholds
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 3
    timeout: float = 30.0
    
    # Exception handling
    expected_exceptions: tuple = (Exception,)
    
    # Advanced features
    slow_call_threshold: float = 10.0  # seconds
    slow_call_rate_threshold: float = 0.5  # 50%
    minimum_throughput: int = 10
    
    # Monitoring
    enable_metrics: bool = True
    enable_detailed_logging: bool = True


class CircuitBreakerMetrics:
    """Metrics collection for circuit breaker monitoring."""
    
    def __init__(self):
        """Initialize metrics."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.slow_calls = 0
        self.rejected_calls = 0
        
        # Time-based metrics
        self.last_call_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.last_failure_time: Optional[datetime] = None
        
        # Response time tracking
        self.response_times: list = []
        self.max_response_times = 100  # Keep last 100 response times
    
    def record_call(self, duration: float, success: bool, slow: bool = False) -> None:
        """Record call metrics."""
        self.total_calls += 1
        self.last_call_time = datetime.utcnow()
        
        # Track response time
        self.response_times.append(duration)
        if len(self.response_times) > self.max_response_times:
            self.response_times.pop(0)
        
        if success:
            self.successful_calls += 1
            self.last_success_time = datetime.utcnow()
        else:
            self.failed_calls += 1
            self.last_failure_time = datetime.utcnow()
        
        if slow:
            self.slow_calls += 1
    
    def record_rejection(self) -> None:
        """Record rejected call."""
        self.rejected_calls += 1
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls
    
    @property
    def slow_call_rate(self) -> float:
        """Calculate slow call rate."""
        if self.total_calls == 0:
            return 0.0
        return self.slow_calls / self.total_calls
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.slow_calls = 0
        self.rejected_calls = 0
        self.response_times.clear()


class CircuitBreaker:
    """Enterprise-grade circuit breaker implementation.
    
    Provides comprehensive protection against cascading failures with:
    - Configurable failure thresholds and recovery timeouts
    - Slow call detection and rate limiting
    - Comprehensive metrics and monitoring
    - Structured logging for observability
    - Thread-safe operation
    
    Example:
        >>> config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30)
        >>> cb = CircuitBreaker("payment_service", config)
        >>> 
        >>> result = await cb.call(payment_service.process_payment, payment_data)
    """
    
    def __init__(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ):
        """Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name for identification
            config: Configuration (uses defaults if not provided)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        
        # Metrics
        self.metrics = CircuitBreakerMetrics()
        
        # Logging
        self.logger = get_logger(f"circuit_breaker.{name}")
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        self.logger.info(
            f"Circuit breaker '{name}' initialized",
            extra={
                "circuit_breaker": name,
                "config": self.config.__dict__
            }
        )
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitBreakerState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.state == CircuitBreakerState.HALF_OPEN
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        return self.state == CircuitBreakerState.CLOSED
    
    async def call(
        self, 
        operation: Callable, 
        *args, 
        fallback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """Execute operation with circuit breaker protection.
        
        Args:
            operation: Async function to execute
            *args: Operation arguments
            fallback: Optional fallback function when circuit is open
            **kwargs: Operation keyword arguments
            
        Returns:
            Operation result or fallback result
            
        Raises:
            CircuitBreakerError: When circuit is open and no fallback provided
        """
        async with self._lock:
            # Check if we should attempt the operation
            if not await self._should_attempt_call():
                self.metrics.record_rejection()
                
                if fallback:
                    self.logger.debug(
                        f"Circuit breaker '{self.name}' is open, using fallback",
                        extra={"circuit_breaker": self.name, "state": self.state.value}
                    )
                    return await self._execute_fallback(fallback, *args, **kwargs)
                
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is open",
                    context={"circuit_breaker": self.name, "state": self.state.value}
                )
        
        # Execute operation outside of lock to avoid blocking other calls
        start_time = datetime.utcnow()
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                operation(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            # Calculate duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            is_slow = duration > self.config.slow_call_threshold
            
            # Record success
            async with self._lock:
                await self._on_success(duration, is_slow)
            
            return result
            
        except self.config.expected_exceptions as e:
            # Calculate duration for failed call
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Record failure
            async with self._lock:
                await self._on_failure(duration, e)
            
            raise
        
        except asyncio.TimeoutError as e:
            # Record timeout as failure
            duration = self.config.timeout
            
            async with self._lock:
                await self._on_failure(duration, e)
            
            raise CircuitBreakerError(
                f"Operation timeout in circuit breaker '{self.name}'",
                context={"timeout": self.config.timeout}
            ) from e
    
    async def _should_attempt_call(self) -> bool:
        """Determine if we should attempt the call based on current state."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (self.metrics.last_failure_time and 
                datetime.utcnow() - self.metrics.last_failure_time >= 
                timedelta(seconds=self.config.recovery_timeout)):
                
                # Transition to half-open
                await self._transition_to_half_open()
                return True
            
            return False
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    async def _on_success(self, duration: float, is_slow: bool) -> None:
        """Handle successful operation."""
        self.metrics.record_call(duration, success=True, slow=is_slow)
        
        if self.config.enable_detailed_logging:
            self.logger.debug(
                f"Circuit breaker '{self.name}' - successful call",
                extra={
                    "circuit_breaker": self.name,
                    "duration": duration,
                    "slow": is_slow,
                    "state": self.state.value
                }
            )
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                await self._transition_to_closed()
        
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
            
            # Check for slow call rate threshold
            if (self.metrics.total_calls >= self.config.minimum_throughput and
                self.metrics.slow_call_rate >= self.config.slow_call_rate_threshold):
                
                await self._transition_to_open("High slow call rate")
    
    async def _on_failure(self, duration: float, exception: Exception) -> None:
        """Handle failed operation."""
        self.metrics.record_call(duration, success=False)
        self.failure_count += 1
        
        if self.config.enable_detailed_logging:
            self.logger.warning(
                f"Circuit breaker '{self.name}' - failed call",
                extra={
                    "circuit_breaker": self.name,
                    "duration": duration,
                    "exception": str(exception),
                    "failure_count": self.failure_count,
                    "state": self.state.value
                }
            )
        
        if self.state == CircuitBreakerState.CLOSED:
            # Check failure threshold
            if self.failure_count >= self.config.failure_threshold:
                await self._transition_to_open("Failure threshold exceeded")
            
            # Check failure rate if we have minimum throughput
            elif (self.metrics.total_calls >= self.config.minimum_throughput and
                  self.metrics.failure_rate >= 0.5):  # 50% failure rate
                
                await self._transition_to_open("High failure rate")
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Any failure in half-open state goes back to open
            await self._transition_to_open("Failure in half-open state")
    
    async def _transition_to_open(self, reason: str) -> None:
        """Transition circuit breaker to open state."""
        old_state = self.state
        self.state = CircuitBreakerState.OPEN
        self.success_count = 0
        
        self.logger.warning(
            f"Circuit breaker '{self.name}' opened: {reason}",
            extra={
                "circuit_breaker": self.name,
                "old_state": old_state.value,
                "new_state": self.state.value,
                "reason": reason,
                "failure_count": self.failure_count,
                "failure_rate": self.metrics.failure_rate
            }
        )
    
    async def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to half-open state."""
        old_state = self.state
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        
        self.logger.info(
            f"Circuit breaker '{self.name}' transitioning to half-open",
            extra={
                "circuit_breaker": self.name,
                "old_state": old_state.value,
                "new_state": self.state.value
            }
        )
    
    async def _transition_to_closed(self) -> None:
        """Transition circuit breaker to closed state."""
        old_state = self.state
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        
        self.logger.info(
            f"Circuit breaker '{self.name}' closed - service recovered",
            extra={
                "circuit_breaker": self.name,
                "old_state": old_state.value,
                "new_state": self.state.value,
                "success_count": self.success_count
            }
        )
    
    async def _execute_fallback(
        self, 
        fallback: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """Execute fallback function."""
        try:
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            else:
                return fallback(*args, **kwargs)
        except Exception as e:
            self.logger.error(
                f"Fallback execution failed for circuit breaker '{self.name}'",
                extra={
                    "circuit_breaker": self.name,
                    "fallback_error": str(e)
                }
            )
            raise
    
    async def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        async with self._lock:
            old_state = self.state
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.metrics.reset()
            
            self.logger.info(
                f"Circuit breaker '{self.name}' manually reset",
                extra={
                    "circuit_breaker": self.name,
                    "old_state": old_state.value,
                    "new_state": self.state.value
                }
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "metrics": {
                "total_calls": self.metrics.total_calls,
                "successful_calls": self.metrics.successful_calls,
                "failed_calls": self.metrics.failed_calls,
                "slow_calls": self.metrics.slow_calls,
                "rejected_calls": self.metrics.rejected_calls,
                "failure_rate": self.metrics.failure_rate,
                "slow_call_rate": self.metrics.slow_call_rate,
                "average_response_time": self.metrics.average_response_time,
                "last_call_time": self.metrics.last_call_time.isoformat() if self.metrics.last_call_time else None,
                "last_success_time": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
                "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "slow_call_threshold": self.config.slow_call_threshold,
                "slow_call_rate_threshold": self.config.slow_call_rate_threshold,
                "minimum_throughput": self.config.minimum_throughput,
            }
        }


class CircuitBreakerRegistry:
    """Enterprise registry for managing multiple circuit breakers."""
    
    def __init__(self):
        """Initialize circuit breaker registry."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.logger = get_logger("circuit_breaker_registry")
    
    def get_or_create(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one.
        
        Args:
            name: Circuit breaker name
            config: Configuration (uses default if not provided)
            
        Returns:
            Circuit breaker instance
        """
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
            self.logger.debug(f"Created circuit breaker: {name}")
        
        return self.circuit_breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self.circuit_breakers.get(name)
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            await cb.reset()
        
        self.logger.info("Reset all circuit breakers")
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {
            name: cb.get_status() 
            for name, cb in self.circuit_breakers.items()
        }
    
    def list_names(self) -> list:
        """List all circuit breaker names."""
        return list(self.circuit_breakers.keys())


# Global registry instance
_circuit_breaker_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str, 
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """Get or create a circuit breaker.
    
    Args:
        name: Circuit breaker name
        config: Optional configuration
        
    Returns:
        Circuit breaker instance
    """
    return _circuit_breaker_registry.get_or_create(name, config)


async def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers in the registry."""
    await _circuit_breaker_registry.reset_all()


def get_all_circuit_breaker_status() -> Dict[str, Dict[str, Any]]:
    """Get status of all circuit breakers."""
    return _circuit_breaker_registry.get_all_status()