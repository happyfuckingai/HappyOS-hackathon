"""
⚡ CIRCUIT BREAKER PATTERN

Implements circuit breaker pattern to protect against cascading failures:
- Automatic failure detection
- Service isolation during outages
- Gradual recovery testing
- Configurable thresholds and timeouts
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Failing, blocking requests
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: int = 60          # Seconds before trying recovery
    success_threshold: int = 3          # Successes needed to close
    timeout: float = 30.0               # Request timeout in seconds
    expected_exception: type = Exception # Exception type to monitor
    
    # Advanced settings
    sliding_window_size: int = 100      # Size of sliding window for failure rate
    minimum_requests: int = 10          # Minimum requests before considering failure rate
    failure_rate_threshold: float = 0.5 # Failure rate threshold (0.0-1.0)


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0
    current_consecutive_failures: int = 0
    current_consecutive_successes: int = 0
    
    def get_failure_rate(self) -> float:
        """Get current failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    def get_success_rate(self) -> float:
        """Get current success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting external service calls.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()
        self._last_state_change = datetime.utcnow()
        
        # Sliding window for failure rate calculation
        self._request_history = []
        
        logger.info(f"Circuit breaker '{name}' initialized in {self.state.value} state")
    
    async def call(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            TimeoutError: When request times out
            Exception: Original function exceptions
        """
        async with self._lock:
            # Check if circuit should be opened
            await self._check_state_transition()
            
            # Reject request if circuit is open
            if self.state == CircuitBreakerState.OPEN:
                self.metrics.rejected_requests += 1
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Last failure: {self.metrics.last_failure_time}"
                )
        
        # Execute the function with timeout
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            # Record success
            await self._record_success()
            return result
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            await self._record_failure(
                TimeoutError(f"Request timed out after {execution_time:.2f}s")
            )
            raise TimeoutError(f"Circuit breaker timeout after {execution_time:.2f}s")
            
        except Exception as e:
            # Only count expected exceptions as failures
            if isinstance(e, self.config.expected_exception):
                await self._record_failure(e)
            else:
                # Unexpected exceptions are passed through without affecting circuit
                logger.warning(f"Unexpected exception in circuit breaker '{self.name}': {e}")
            raise
    
    async def _record_success(self):
        """Record successful request."""
        async with self._lock:
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.current_consecutive_successes += 1
            self.metrics.current_consecutive_failures = 0
            self.metrics.last_success_time = datetime.utcnow()
            
            # Add to sliding window
            self._request_history.append({
                'timestamp': datetime.utcnow(),
                'success': True
            })
            self._cleanup_sliding_window()
            
            # Check if we should close the circuit
            if (self.state == CircuitBreakerState.HALF_OPEN and 
                self.metrics.current_consecutive_successes >= self.config.success_threshold):
                await self._transition_to_closed()
            
            logger.debug(f"Circuit breaker '{self.name}' recorded success. "
                        f"Consecutive successes: {self.metrics.current_consecutive_successes}")
    
    async def _record_failure(self, exception: Exception):
        """Record failed request."""
        async with self._lock:
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.current_consecutive_failures += 1
            self.metrics.current_consecutive_successes = 0
            self.metrics.last_failure_time = datetime.utcnow()
            
            # Add to sliding window
            self._request_history.append({
                'timestamp': datetime.utcnow(),
                'success': False,
                'exception': str(exception)
            })
            self._cleanup_sliding_window()
            
            logger.warning(f"Circuit breaker '{self.name}' recorded failure: {exception}. "
                          f"Consecutive failures: {self.metrics.current_consecutive_failures}")
    
    async def _check_state_transition(self):
        """Check if circuit breaker state should change."""
        now = datetime.utcnow()
        
        if self.state == CircuitBreakerState.CLOSED:
            # Check if we should open the circuit
            should_open = False
            
            # Check consecutive failures
            if self.metrics.current_consecutive_failures >= self.config.failure_threshold:
                should_open = True
                logger.info(f"Opening circuit '{self.name}' due to consecutive failures: "
                           f"{self.metrics.current_consecutive_failures}")
            
            # Check failure rate in sliding window
            elif (len(self._request_history) >= self.config.minimum_requests and
                  self._get_sliding_window_failure_rate() >= self.config.failure_rate_threshold):
                should_open = True
                failure_rate = self._get_sliding_window_failure_rate()
                logger.info(f"Opening circuit '{self.name}' due to high failure rate: "
                           f"{failure_rate:.2%}")
            
            if should_open:
                await self._transition_to_open()
        
        elif self.state == CircuitBreakerState.OPEN:
            # Check if we should try recovery
            time_since_last_change = now - self._last_state_change
            if time_since_last_change.total_seconds() >= self.config.recovery_timeout:
                await self._transition_to_half_open()
    
    async def _transition_to_open(self):
        """Transition to OPEN state."""
        self.state = CircuitBreakerState.OPEN
        self._last_state_change = datetime.utcnow()
        self.metrics.state_changes += 1
        
        logger.warning(f"Circuit breaker '{self.name}' transitioned to OPEN state. "
                      f"Failure rate: {self.metrics.get_failure_rate():.2%}")
    
    async def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self.state = CircuitBreakerState.HALF_OPEN
        self._last_state_change = datetime.utcnow()
        self.metrics.state_changes += 1
        self.metrics.current_consecutive_successes = 0
        
        logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN state. "
                   f"Testing recovery...")
    
    async def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.state = CircuitBreakerState.CLOSED
        self._last_state_change = datetime.utcnow()
        self.metrics.state_changes += 1
        self.metrics.current_consecutive_failures = 0
        
        logger.info(f"Circuit breaker '{self.name}' transitioned to CLOSED state. "
                   f"Service recovered successfully.")
    
    def _cleanup_sliding_window(self):
        """Clean up old entries from sliding window."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)  # Keep 5 minutes of history
        self._request_history = [
            entry for entry in self._request_history
            if entry['timestamp'] > cutoff_time
        ]
        
        # Limit window size
        if len(self._request_history) > self.config.sliding_window_size:
            self._request_history = self._request_history[-self.config.sliding_window_size:]
    
    def _get_sliding_window_failure_rate(self) -> float:
        """Get failure rate from sliding window."""
        if not self._request_history:
            return 0.0
        
        failures = sum(1 for entry in self._request_history if not entry['success'])
        return failures / len(self._request_history)
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "rejected_requests": self.metrics.rejected_requests,
                "failure_rate": self.metrics.get_failure_rate(),
                "success_rate": self.metrics.get_success_rate(),
                "consecutive_failures": self.metrics.current_consecutive_failures,
                "consecutive_successes": self.metrics.current_consecutive_successes,
                "state_changes": self.metrics.state_changes,
                "last_failure": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
                "last_success": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "failure_rate_threshold": self.config.failure_rate_threshold
            },
            "sliding_window": {
                "size": len(self._request_history),
                "failure_rate": self._get_sliding_window_failure_rate()
            }
        }
    
    async def reset(self):
        """Reset circuit breaker to initial state."""
        async with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.metrics = CircuitBreakerMetrics()
            self._request_history = []
            self._last_state_change = datetime.utcnow()
            
            logger.info(f"Circuit breaker '{self.name}' reset to initial state")
    
    async def force_open(self):
        """Force circuit breaker to OPEN state."""
        async with self._lock:
            await self._transition_to_open()
            logger.warning(f"Circuit breaker '{self.name}' forced to OPEN state")
    
    async def force_close(self):
        """Force circuit breaker to CLOSED state."""
        async with self._lock:
            await self._transition_to_closed()
            logger.info(f"Circuit breaker '{self.name}' forced to CLOSED state")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerManager:
    """
    Manager for multiple circuit breakers.
    """
    
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get or create circuit breaker."""
        async with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker(name, config)
                logger.info(f"Created new circuit breaker: {name}")
            
            return self._circuit_breakers[name]
    
    async def call_with_circuit_breaker(self, name: str, func: Callable[..., Awaitable[Any]], 
                                       *args, config: CircuitBreakerConfig = None, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        circuit_breaker = await self.get_circuit_breaker(name, config)
        return await circuit_breaker.call(func, *args, **kwargs)
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {
            name: cb.get_status()
            for name, cb in self._circuit_breakers.items()
        }
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        async with self._lock:
            for cb in self._circuit_breakers.values():
                await cb.reset()
            logger.info("All circuit breakers reset")
    
    async def cleanup(self):
        """Cleanup circuit breaker manager."""
        async with self._lock:
            self._circuit_breakers.clear()
            logger.info("Circuit breaker manager cleaned up")


# Global circuit breaker manager
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None


async def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get global circuit breaker manager."""
    global _circuit_breaker_manager
    
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    
    return _circuit_breaker_manager


async def circuit_breaker_call(name: str, func: Callable[..., Awaitable[Any]], 
                              *args, config: CircuitBreakerConfig = None, **kwargs) -> Any:
    """Convenience function for circuit breaker protected calls."""
    manager = await get_circuit_breaker_manager()
    return await manager.call_with_circuit_breaker(name, func, *args, config=config, **kwargs)

