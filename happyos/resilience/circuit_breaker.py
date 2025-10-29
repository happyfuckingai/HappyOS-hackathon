"""
Circuit breaker for HappyOS SDK.

Stub implementation for testing purposes.
"""

import asyncio
from typing import Callable, Any


class CircuitBreaker:
    """Circuit breaker for resilience."""
    
    def __init__(self, threshold: int = 5, timeout: int = 60):
        self.threshold = threshold
        self.timeout = timeout
        self.failure_count = 0
        self.is_open = False
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function with circuit breaker protection."""
        if self.is_open:
            raise Exception("Circuit breaker is open")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self.failure_count = 0  # Reset on success
            return result
        
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.threshold:
                self.is_open = True
            raise


class RetryStrategy:
    """Retry strategy for resilience."""
    
    def __init__(self, max_attempts: int = 3, backoff_type: str = "exponential"):
        self.max_attempts = max_attempts
        self.backoff_type = backoff_type
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            
            except Exception as e:
                last_exception = e
                if attempt < self.max_attempts - 1:
                    await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
        
        raise last_exception