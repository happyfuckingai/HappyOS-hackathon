"""
🔄 RETRY MANAGER

Advanced retry mechanisms with:
- Exponential backoff with jitter
- Configurable retry policies
- Retry result tracking
- Dead letter queue for failed retries
"""

import asyncio
import logging
import random
import time
import functools
from typing import Dict, Any, Optional, Callable, Awaitable, List, Union, TypeVar, Type
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_exceptions: Optional[List[Type[Exception]]] = None
):
    """
    Decorator for retrying async functions with exponential backoff and jitter.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Factor by which the delay increases with each retry
        jitter: Whether to add random jitter to the delay
        retry_exceptions: List of exception types to retry on. If None, retries on all exceptions.
    
    Returns:
        Decorated function that will retry on failure
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_count = 0
            delay = base_delay
            
            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # If we've specified which exceptions to retry on, check if this is one of them
                    if retry_exceptions and not any(isinstance(e, exc) for exc in retry_exceptions):
                        logger.warning(f"Exception {type(e).__name__} not in retry_exceptions list, raising")
                        raise
                    
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error(f"Maximum retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    # Calculate delay with optional jitter
                    current_delay = min(delay, max_delay)
                    if jitter:
                        # Add random jitter between 0% and 25% of the delay
                        jitter_amount = random.uniform(0, 0.25 * current_delay)
                        current_delay = current_delay + jitter_amount
                    
                    logger.warning(
                        f"Retry {retry_count}/{max_retries} for {func.__name__} "
                        f"after {current_delay:.2f}s due to {type(e).__name__}: {str(e)}"
                    )
                    
                    # Wait before retrying
                    await asyncio.sleep(current_delay)
                    
                    # Increase delay for next retry using exponential backoff
                    delay = min(delay * backoff_factor, max_delay)
        
        return wrapper
    
    return decorator


class RetryStrategy(Enum):
    """Retry strategies."""
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


class RetryResult(Enum):
    """Retry operation results."""
    SUCCESS = "success"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_NON_RETRYABLE = "failed_non_retryable"
    FAILED_MAX_ATTEMPTS = "failed_max_attempts"
    FAILED_TIMEOUT = "failed_timeout"


@dataclass
class RetryPolicy:
    """Retry policy configuration."""
    max_attempts: int = 3
    base_delay: float = 1.0                    # Base delay in seconds
    max_delay: float = 60.0                    # Maximum delay in seconds
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    backoff_multiplier: float = 2.0            # Multiplier for exponential backoff
    jitter: bool = True                        # Add random jitter to delays
    jitter_range: float = 0.1                 # Jitter range (0.0-1.0)
    timeout: Optional[float] = None            # Total timeout for all attempts
    
    # Exception handling
    retryable_exceptions: List[type] = field(default_factory=lambda: [Exception])
    non_retryable_exceptions: List[type] = field(default_factory=list)
    
    # Conditional retry
    retry_condition: Optional[Callable[[Exception], bool]] = None


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt_number: int
    delay: float
    start_time: datetime
    end_time: Optional[datetime] = None
    exception: Optional[Exception] = None
    result: Optional[RetryResult] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Get attempt duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


@dataclass
class RetryExecution:
    """Complete retry execution information."""
    operation_name: str
    policy: RetryPolicy
    attempts: List[RetryAttempt] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    final_result: Optional[RetryResult] = None
    final_exception: Optional[Exception] = None
    success_result: Any = None
    
    @property
    def total_duration(self) -> Optional[float]:
        """Get total execution duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def total_attempts(self) -> int:
        """Get total number of attempts."""
        return len(self.attempts)


class RetryManager:
    """
    Advanced retry manager with multiple strategies and policies.
    """
    
    def __init__(self):
        self._executions: List[RetryExecution] = []
        self._dead_letter_queue: List[RetryExecution] = []
        self._lock = asyncio.Lock()
    
    async def execute_with_retry(self, operation_name: str, func: Callable[..., Awaitable[Any]], 
                                *args, policy: RetryPolicy = None, **kwargs) -> Any:
        """
        Execute function with retry policy.
        
        Args:
            operation_name: Name for tracking/logging
            func: Async function to execute
            *args: Function arguments
            policy: Retry policy (uses default if None)
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: Final exception if all retries fail
        """
        if policy is None:
            policy = RetryPolicy()
        
        execution = RetryExecution(operation_name=operation_name, policy=policy)
        
        async with self._lock:
            self._executions.append(execution)
        
        logger.info(f"Starting retry execution for '{operation_name}' with policy: "
                   f"max_attempts={policy.max_attempts}, strategy={policy.strategy.value}")
        
        try:
            result = await self._execute_with_policy(execution, func, *args, **kwargs)
            execution.success_result = result
            execution.final_result = RetryResult.SUCCESS
            execution.end_time = datetime.utcnow()
            
            logger.info(f"Retry execution '{operation_name}' succeeded after "
                       f"{execution.total_attempts} attempts in {execution.total_duration:.2f}s")
            
            return result
            
        except Exception as e:
            execution.final_exception = e
            execution.end_time = datetime.utcnow()
            
            # Add to dead letter queue if all retries failed
            if execution.final_result in [RetryResult.FAILED_MAX_ATTEMPTS, 
                                        RetryResult.FAILED_TIMEOUT,
                                        RetryResult.FAILED_NON_RETRYABLE]:
                async with self._lock:
                    self._dead_letter_queue.append(execution)
            
            logger.error(f"Retry execution '{operation_name}' failed with result "
                        f"{execution.final_result.value} after {execution.total_attempts} attempts "
                        f"in {execution.total_duration:.2f}s: {e}")
            
            raise
    
    async def _execute_with_policy(self, execution: RetryExecution, func: Callable[..., Awaitable[Any]], 
                                  *args, **kwargs) -> Any:
        """Execute function according to retry policy."""
        policy = execution.policy
        start_time = execution.start_time
        
        for attempt_num in range(1, policy.max_attempts + 1):
            # Check total timeout
            if policy.timeout:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed >= policy.timeout:
                    execution.final_result = RetryResult.FAILED_TIMEOUT
                    raise TimeoutError(f"Retry timeout after {elapsed:.2f}s")
            
            # Calculate delay for this attempt (except first)
            delay = 0.0
            if attempt_num > 1:
                delay = self._calculate_delay(attempt_num - 1, policy)
                logger.debug(f"Waiting {delay:.2f}s before attempt {attempt_num}")
                await asyncio.sleep(delay)
            
            # Create attempt record
            attempt = RetryAttempt(
                attempt_number=attempt_num,
                delay=delay,
                start_time=datetime.utcnow()
            )
            execution.attempts.append(attempt)
            
            try:
                logger.debug(f"Executing attempt {attempt_num}/{policy.max_attempts} "
                           f"for '{execution.operation_name}'")
                
                result = await func(*args, **kwargs)
                
                # Success!
                attempt.end_time = datetime.utcnow()
                attempt.result = RetryResult.SUCCESS
                
                return result
                
            except Exception as e:
                attempt.end_time = datetime.utcnow()
                attempt.exception = e
                
                # Check if exception is retryable
                if not self._is_retryable_exception(e, policy):
                    attempt.result = RetryResult.FAILED_NON_RETRYABLE
                    execution.final_result = RetryResult.FAILED_NON_RETRYABLE
                    logger.warning(f"Non-retryable exception in attempt {attempt_num}: {e}")
                    raise
                
                # Check custom retry condition
                if policy.retry_condition and not policy.retry_condition(e):
                    attempt.result = RetryResult.FAILED_NON_RETRYABLE
                    execution.final_result = RetryResult.FAILED_NON_RETRYABLE
                    logger.warning(f"Retry condition failed in attempt {attempt_num}: {e}")
                    raise
                
                attempt.result = RetryResult.FAILED_RETRYABLE
                
                if attempt_num < policy.max_attempts:
                    logger.warning(f"Attempt {attempt_num} failed (retryable): {e}")
                else:
                    # Final attempt failed
                    execution.final_result = RetryResult.FAILED_MAX_ATTEMPTS
                    logger.error(f"All {policy.max_attempts} attempts failed. Final error: {e}")
                    raise
        
        # Should not reach here
        raise RuntimeError("Unexpected end of retry loop")
    
    def _calculate_delay(self, attempt_num: int, policy: RetryPolicy) -> float:
        """Calculate delay for retry attempt."""
        if policy.strategy == RetryStrategy.FIXED_DELAY:
            delay = policy.base_delay
            
        elif policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = policy.base_delay * (policy.backoff_multiplier ** (attempt_num - 1))
            
        elif policy.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = policy.base_delay * attempt_num
            
        elif policy.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            delay = policy.base_delay * self._fibonacci(attempt_num)
            
        else:
            delay = policy.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, policy.max_delay)
        
        # Add jitter if enabled
        if policy.jitter:
            jitter_amount = delay * policy.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.0, delay + jitter)
        
        return delay
    
    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
    
    def _is_retryable_exception(self, exception: Exception, policy: RetryPolicy) -> bool:
        """Check if exception is retryable according to policy."""
        # Check non-retryable exceptions first
        for exc_type in policy.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False
        
        # Check retryable exceptions
        for exc_type in policy.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True
        
        return False
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get retry execution statistics."""
        if not self._executions:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "success_rate": 0.0,
                "average_attempts": 0.0,
                "average_duration": 0.0
            }
        
        successful = sum(1 for e in self._executions if e.final_result == RetryResult.SUCCESS)
        failed = len(self._executions) - successful
        
        total_attempts = sum(e.total_attempts for e in self._executions)
        total_duration = sum(e.total_duration or 0 for e in self._executions)
        
        return {
            "total_executions": len(self._executions),
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": successful / len(self._executions),
            "average_attempts": total_attempts / len(self._executions),
            "average_duration": total_duration / len(self._executions),
            "dead_letter_queue_size": len(self._dead_letter_queue)
        }
    
    def get_recent_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent retry executions."""
        recent = sorted(self._executions, key=lambda e: e.start_time, reverse=True)[:limit]
        
        return [
            {
                "operation_name": e.operation_name,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "total_attempts": e.total_attempts,
                "total_duration": e.total_duration,
                "final_result": e.final_result.value if e.final_result else None,
                "final_exception": str(e.final_exception) if e.final_exception else None,
                "policy": {
                    "max_attempts": e.policy.max_attempts,
                    "strategy": e.policy.strategy.value,
                    "base_delay": e.policy.base_delay,
                    "max_delay": e.policy.max_delay
                }
            }
            for e in recent
        ]
    
    def get_dead_letter_queue(self) -> List[Dict[str, Any]]:
        """Get failed executions from dead letter queue."""
        return [
            {
                "operation_name": e.operation_name,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat() if e.end_time else None,
                "total_attempts": e.total_attempts,
                "final_result": e.final_result.value if e.final_result else None,
                "final_exception": str(e.final_exception) if e.final_exception else None
            }
            for e in self._dead_letter_queue
        ]
    
    async def clear_dead_letter_queue(self):
        """Clear the dead letter queue."""
        async with self._lock:
            cleared_count = len(self._dead_letter_queue)
            self._dead_letter_queue.clear()
            logger.info(f"Cleared {cleared_count} items from dead letter queue")
    
    async def cleanup_old_executions(self, max_age_hours: int = 24):
        """Clean up old execution records."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        async with self._lock:
            original_count = len(self._executions)
            self._executions = [
                e for e in self._executions
                if e.start_time > cutoff_time
            ]
            
            # Also clean up dead letter queue
            original_dlq_count = len(self._dead_letter_queue)
            self._dead_letter_queue = [
                e for e in self._dead_letter_queue
                if e.start_time > cutoff_time
            ]
            
            cleaned_executions = original_count - len(self._executions)
            cleaned_dlq = original_dlq_count - len(self._dead_letter_queue)
            
            logger.info(f"Cleaned up {cleaned_executions} old executions and "
                       f"{cleaned_dlq} old dead letter queue items")


# Global retry manager
_retry_manager: Optional[RetryManager] = None


async def get_retry_manager() -> RetryManager:
    """Get global retry manager."""
    global _retry_manager
    
    if _retry_manager is None:
        _retry_manager = RetryManager()
    
    return _retry_manager


async def retry_call(operation_name: str, func: Callable[..., Awaitable[Any]], 
                    *args, policy: RetryPolicy = None, **kwargs) -> Any:
    """Convenience function for retry-protected calls."""
    manager = await get_retry_manager()
    return await manager.execute_with_retry(operation_name, func, *args, policy=policy, **kwargs)


# Common retry policies
QUICK_RETRY = RetryPolicy(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)

STANDARD_RETRY = RetryPolicy(
    max_attempts=5,
    base_delay=1.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)

PERSISTENT_RETRY = RetryPolicy(
    max_attempts=10,
    base_delay=2.0,
    max_delay=120.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    timeout=600.0  # 10 minutes total timeout
)

NETWORK_RETRY = RetryPolicy(
    max_attempts=5,
    base_delay=1.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    retryable_exceptions=[ConnectionError, TimeoutError, OSError],
    non_retryable_exceptions=[ValueError, TypeError]
)

