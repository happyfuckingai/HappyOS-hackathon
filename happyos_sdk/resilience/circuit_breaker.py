"""
Circuit Breaker - Resilience pattern implementation for SDK

Provides circuit breaker functionality for agents to handle service failures gracefully.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from dataclasses import dataclass

try:
    from ..exceptions import ServiceUnavailableError
except ImportError:
    from happyos_sdk.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    success_threshold: int = 3  # for half-open state
    timeout: float = 30.0  # operation timeout
    expected_exception: type = Exception


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against cascading failures.
    
    Monitors failures and automatically opens the circuit when failure threshold
    is reached, then attempts recovery after a timeout period.
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        """
        Initialize circuit breaker.
        
        Args:
            config: Circuit breaker configuration
        """
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        
        logger.debug(f"Circuit breaker initialized with config: {config}")
    
    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.state == CircuitState.HALF_OPEN
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        return self.state == CircuitState.CLOSED
    
    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """
        Execute operation with circuit breaker protection.
        
        Args:
            operation: Async function to execute
            *args: Operation arguments
            **kwargs: Operation keyword arguments
            
        Returns:
            Operation result
            
        Raises:
            ServiceUnavailableError: When circuit is open
        """
        # Check if we should attempt the operation
        if not self._should_attempt_call():
            raise ServiceUnavailableError("Circuit breaker is open")
        
        try:
            # Execute operation with timeout
            result = await asyncio.wait_for(
                operation(*args, **kwargs),
                timeout=self.config.timeout
            )
            
            # Record success
            await self._on_success()
            return result
            
        except self.config.expected_exception as e:
            # Record failure
            await self._on_failure()
            raise
        except asyncio.TimeoutError:
            # Treat timeout as failure
            await self._on_failure()
            raise ServiceUnavailableError("Operation timeout")
    
    def _should_attempt_call(self) -> bool:
        """Determine if we should attempt the call based on current state."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if (self.last_failure_time and 
                datetime.utcnow() - self.last_failure_time >= 
                timedelta(seconds=self.config.recovery_timeout)):
                
                # Transition to half-open
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    async def _on_success(self):
        """Handle successful operation."""
        self.last_success_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                # Transition back to closed
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker transitioning to CLOSED")
        
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed operation."""
        self.last_failure_time = datetime.utcnow()
        self.failure_count += 1
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                # Transition to open
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker transitioning to OPEN after {self.failure_count} failures")
        
        elif self.state == CircuitState.HALF_OPEN:
            # Go back to open on any failure in half-open state
            self.state = CircuitState.OPEN
            self.success_count = 0
            logger.warning("Circuit breaker transitioning back to OPEN from HALF_OPEN")
    
    def reset(self):
        """Manually reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info("Circuit breaker manually reset to CLOSED")
    
    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            }
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        """Initialize circuit breaker registry."""
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
    
    def get_or_create(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one.
        
        Args:
            name: Circuit breaker name
            config: Configuration (uses default if not provided)
            
        Returns:
            Circuit breaker instance
        """
        if name not in self.circuit_breakers:
            if config is None:
                config = CircuitBreakerConfig()
            
            self.circuit_breakers[name] = CircuitBreaker(config)
            logger.debug(f"Created new circuit breaker: {name}")
        
        return self.circuit_breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self.circuit_breakers.get(name)
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.reset()
        logger.info("Reset all circuit breakers")
    
    def get_all_status(self) -> dict:
        """Get status of all circuit breakers."""
        return {
            name: cb.get_status() 
            for name, cb in self.circuit_breakers.items()
        }


# Global registry instance
_circuit_breaker_registry = CircuitBreakerRegistry()


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """
    Get or create a circuit breaker.
    
    Args:
        name: Circuit breaker name
        config: Optional configuration
        
    Returns:
        Circuit breaker instance
    """
    return _circuit_breaker_registry.get_or_create(name, config)


def reset_all_circuit_breakers():
    """Reset all circuit breakers in the registry."""
    _circuit_breaker_registry.reset_all()


def get_all_circuit_breaker_status() -> dict:
    """Get status of all circuit breakers."""
    return _circuit_breaker_registry.get_all_status()