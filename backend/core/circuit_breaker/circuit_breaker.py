"""
Circuit breaker implementation for service resilience and automatic fallback.
Implements the circuit breaker pattern with CLOSED/OPEN/HALF_OPEN states.
"""

import asyncio
import time
import random
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

from ..interfaces import CircuitState, CircuitBreakerService
from ..settings import get_settings


logger = logging.getLogger(__name__)


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Exception raised when circuit breaker is in OPEN state."""
    pass


class CircuitBreakerTimeoutError(CircuitBreakerError):
    """Exception raised when circuit breaker call times out."""
    pass


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0
    current_failure_streak: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_calls == 0:
            return 100.0
        return (self.successful_calls / self.total_calls) * 100.0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        if self.total_calls == 0:
            return 0.0
        return (self.failed_calls / self.total_calls) * 100.0


class CircuitBreaker:
    """
    Circuit breaker implementation with exponential backoff and jitter.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Calls fail immediately, service is considered down
    - HALF_OPEN: Limited calls allowed to test service recovery
    """
    
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3,
        recovery_timeout_multiplier: float = 2.0,
        max_recovery_timeout: int = 300,
        exponential_backoff_base: int = 2,
        jitter_factor: float = 0.1
    ):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        self.recovery_timeout_multiplier = recovery_timeout_multiplier
        self.max_recovery_timeout = max_recovery_timeout
        self.exponential_backoff_base = exponential_backoff_base
        self.jitter_factor = jitter_factor
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.next_attempt_time: Optional[float] = None
        self.half_open_calls = 0
        self.consecutive_failures = 0
        
        # Statistics
        self.stats = CircuitBreakerStats()
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        logger.info(f"Circuit breaker initialized for service: {service_name}")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
            CircuitBreakerTimeoutError: When call times out
            Exception: Original function exceptions when circuit is closed
        """
        async with self._lock:
            current_time = time.time()
            
            # Check if we should attempt to reset from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset(current_time):
                    self._transition_to_half_open()
                else:
                    self.stats.total_calls += 1
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN for service: {self.service_name}. "
                        f"Next attempt at: {datetime.fromtimestamp(self.next_attempt_time)}"
                    )
            
            # In HALF_OPEN state, limit the number of calls
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is HALF_OPEN for service: {self.service_name}. "
                        f"Maximum test calls ({self.half_open_max_calls}) reached."
                    )
                self.half_open_calls += 1
        
        # Execute the function
        self.stats.total_calls += 1
        
        try:
            # Add timeout to the function call
            result = await asyncio.wait_for(
                self._execute_function(func, *args, **kwargs),
                timeout=self.timeout_seconds
            )
            
            await self._on_success()
            return result
            
        except asyncio.TimeoutError:
            self.stats.timeout_calls += 1
            await self._on_failure(current_time)
            raise CircuitBreakerTimeoutError(
                f"Call to {self.service_name} timed out after {self.timeout_seconds} seconds"
            )
        except Exception as e:
            await self._on_failure(current_time)
            raise
    
    async def _execute_function(self, func: Callable, *args, **kwargs) -> Any:
        """Execute the function, handling both sync and async functions."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Run sync function in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    async def _on_success(self):
        """Handle successful function execution."""
        async with self._lock:
            self.stats.successful_calls += 1
            self.stats.last_success_time = datetime.now()
            self.failure_count = 0
            self.consecutive_failures = 0
            
            if self.state == CircuitState.HALF_OPEN:
                # Successful call in HALF_OPEN state, transition back to CLOSED
                self._transition_to_closed()
                logger.info(f"Circuit breaker for {self.service_name} recovered: HALF_OPEN -> CLOSED")
    
    async def _on_failure(self, failure_time: float):
        """Handle failed function execution."""
        async with self._lock:
            self.stats.failed_calls += 1
            self.stats.last_failure_time = datetime.now()
            self.failure_count += 1
            self.consecutive_failures += 1
            self.last_failure_time = failure_time
            
            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self._transition_to_open(failure_time)
                    logger.warning(
                        f"Circuit breaker for {self.service_name} opened: "
                        f"{self.failure_count} failures exceeded threshold {self.failure_threshold}"
                    )
            
            elif self.state == CircuitState.HALF_OPEN:
                # Failure in HALF_OPEN state, go back to OPEN
                self._transition_to_open(failure_time)
                logger.warning(
                    f"Circuit breaker for {self.service_name} failed recovery: HALF_OPEN -> OPEN"
                )
    
    def _should_attempt_reset(self, current_time: float) -> bool:
        """Check if we should attempt to reset from OPEN to HALF_OPEN."""
        if self.next_attempt_time is None:
            return True
        return current_time >= self.next_attempt_time
    
    def _transition_to_closed(self):
        """Transition circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0
        self.next_attempt_time = None
        self.stats.state_changes += 1
    
    def _transition_to_open(self, failure_time: float):
        """Transition circuit breaker to OPEN state."""
        self.state = CircuitState.OPEN
        self.half_open_calls = 0
        
        # Calculate next attempt time with exponential backoff and jitter
        backoff_time = self._calculate_backoff_time()
        jitter = random.uniform(-self.jitter_factor, self.jitter_factor) * backoff_time
        self.next_attempt_time = failure_time + backoff_time + jitter
        
        self.stats.state_changes += 1
        
        logger.warning(
            f"Circuit breaker for {self.service_name} opened. "
            f"Next attempt in {backoff_time:.2f} seconds"
        )
    
    def _transition_to_half_open(self):
        """Transition circuit breaker to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.stats.state_changes += 1
        
        logger.info(f"Circuit breaker for {self.service_name} attempting recovery: OPEN -> HALF_OPEN")
    
    def _calculate_backoff_time(self) -> float:
        """Calculate exponential backoff time."""
        base_timeout = min(
            self.timeout_seconds * (self.exponential_backoff_base ** (self.consecutive_failures - 1)),
            self.max_recovery_timeout
        )
        return base_timeout
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.state
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self.stats
    
    def force_open(self):
        """Force circuit breaker to OPEN state (for testing/maintenance)."""
        with self._lock:
            self.state = CircuitState.OPEN
            self.next_attempt_time = time.time() + self.timeout_seconds
            self.stats.state_changes += 1
            logger.warning(f"Circuit breaker for {self.service_name} forced to OPEN state")
    
    def force_close(self):
        """Force circuit breaker to CLOSED state (for testing/maintenance)."""
        with self._lock:
            self._transition_to_closed()
            logger.info(f"Circuit breaker for {self.service_name} forced to CLOSED state")
    
    def reset_stats(self):
        """Reset circuit breaker statistics."""
        with self._lock:
            self.stats = CircuitBreakerStats()
            logger.info(f"Circuit breaker statistics reset for {self.service_name}")


class CircuitBreakerManager(CircuitBreakerService):
    """
    Manager for multiple circuit breakers.
    Provides a centralized way to manage circuit breakers for different services.
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.settings = get_settings()
        
        # Initialize circuit breakers for known services
        self._initialize_service_circuit_breakers()
    
    def _initialize_service_circuit_breakers(self):
        """Initialize circuit breakers for all configured services."""
        cb_config = self.settings.circuit_breaker
        
        for service_name, threshold in cb_config.service_thresholds.items():
            self.circuit_breakers[service_name] = CircuitBreaker(
                service_name=service_name,
                failure_threshold=threshold,
                timeout_seconds=cb_config.timeout_seconds,
                half_open_max_calls=cb_config.half_open_max_calls
            )
            
        logger.info(f"Initialized circuit breakers for {len(self.circuit_breakers)} services")
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        if service_name not in self.circuit_breakers:
            # Create new circuit breaker with default settings
            cb_config = self.settings.circuit_breaker
            self.circuit_breakers[service_name] = CircuitBreaker(
                service_name=service_name,
                failure_threshold=cb_config.failure_threshold,
                timeout_seconds=cb_config.timeout_seconds,
                half_open_max_calls=cb_config.half_open_max_calls
            )
            logger.info(f"Created new circuit breaker for service: {service_name}")
        
        return self.circuit_breakers[service_name]
    
    async def call_with_circuit_breaker(self, service_name: str, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        return await circuit_breaker.call(func, *args, **kwargs)
    
    async def get_circuit_state(self, service_name: str) -> CircuitState:
        """Get current circuit breaker state for a service."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        return circuit_breaker.get_state()
    
    async def force_open_circuit(self, service_name: str) -> bool:
        """Force circuit breaker to open state."""
        try:
            circuit_breaker = self.get_circuit_breaker(service_name)
            circuit_breaker.force_open()
            return True
        except Exception as e:
            logger.error(f"Failed to force open circuit for {service_name}: {e}")
            return False
    
    async def force_close_circuit(self, service_name: str) -> bool:
        """Force circuit breaker to closed state."""
        try:
            circuit_breaker = self.get_circuit_breaker(service_name)
            circuit_breaker.force_close()
            return True
        except Exception as e:
            logger.error(f"Failed to force close circuit for {service_name}: {e}")
            return False
    
    def get_all_states(self) -> Dict[str, CircuitState]:
        """Get states of all circuit breakers."""
        return {
            service_name: cb.get_state()
            for service_name, cb in self.circuit_breakers.items()
        }
    
    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers."""
        return {
            service_name: cb.get_stats()
            for service_name, cb in self.circuit_breakers.items()
        }
    
    def reset_all_stats(self):
        """Reset statistics for all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.reset_stats()
        logger.info("Reset statistics for all circuit breakers")


# Global circuit breaker manager instance
_circuit_breaker_manager: Optional[CircuitBreakerManager] = None


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager instance."""
    global _circuit_breaker_manager
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = CircuitBreakerManager()
    return _circuit_breaker_manager