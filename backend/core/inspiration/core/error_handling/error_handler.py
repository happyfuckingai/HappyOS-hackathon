"""
Error Handling and Recovery System for HappyOS
Robust error handling with recovery mechanisms and graceful degradation.
"""
import asyncio
import functools
import sys
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from enum import Enum
import time

from app.core.logging.logger import get_logger


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(Enum):
    """Available recovery actions."""
    RETRY = "retry"
    RESTART = "restart"
    FAILOVER = "failover"
    DEGRADED = "degraded"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """Context information for errors."""
    component: str
    operation: str
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    recoverable: bool = True
    retry_count: int = 0
    max_retries: int = 3
    timeout: float = 30.0
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorReport:
    """Comprehensive error report."""
    error: Exception
    context: ErrorContext
    traceback: str
    timestamp: float = field(default_factory=time.time)
    recovery_action: Optional[RecoveryAction] = None
    recovered: bool = False
    recovery_time: Optional[float] = None
    system_state: Dict[str, Any] = field(default_factory=dict)


class ErrorHandler:
    """Centralized error handling and recovery system."""

    def __init__(self):
        self.logger = get_logger("error_handler")
        self.error_history: List[ErrorReport] = []
        self.recovery_strategies: Dict[str, Callable] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # Register default recovery strategies
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """Register default error recovery strategies."""
        self.register_recovery_strategy("retry", self._retry_strategy)
        self.register_recovery_strategy("restart", self._restart_strategy)
        self.register_recovery_strategy("degraded", self._degraded_mode_strategy)

    def register_recovery_strategy(self, name: str, strategy: Callable) -> None:
        """Register a recovery strategy."""
        self.recovery_strategies[name] = strategy
        self.logger.debug(f"Registered recovery strategy: {name}")

    def register_fallback_handler(self, component: str, handler: Callable) -> None:
        """Register a fallback handler for a component."""
        self.fallback_handlers[component] = handler
        self.logger.debug(f"Registered fallback handler for: {component}")

    def get_circuit_breaker(self, component: str) -> 'CircuitBreaker':
        """Get or create a circuit breaker for a component."""
        if component not in self.circuit_breakers:
            self.circuit_breakers[component] = CircuitBreaker(component)
        return self.circuit_breakers[component]

    async def handle_error(
        self,
        error: Exception,
        context: ErrorContext,
        system_state: Optional[Dict[str, Any]] = None
    ) -> ErrorReport:
        """
        Handle an error with context and attempt recovery.

        Args:
            error: The exception that occurred
            context: Error context information
            system_state: Current system state

        Returns:
            ErrorReport: Complete error report with recovery information
        """
        # Create error report
        error_report = ErrorReport(
            error=error,
            context=context,
            traceback=traceback.format_exc(),
            system_state=system_state or {}
        )

        # Log error
        await self._log_error(error_report)

        # Store in history
        self.error_history.append(error_report)

        # Check circuit breaker
        circuit_breaker = self.get_circuit_breaker(context.component)
        if circuit_breaker.is_open():
            self.logger.warning(f"Circuit breaker open for {context.component}, skipping recovery")
            error_report.recovery_action = RecoveryAction.ABORT
            return error_report

        # Attempt recovery if error is recoverable
        if context.recoverable and context.retry_count < context.max_retries:
            try:
                recovery_action = await self._attempt_recovery(error_report)
                error_report.recovery_action = recovery_action
                error_report.recovered = True
                error_report.recovery_time = time.time()

                # Reset circuit breaker on successful recovery
                circuit_breaker.reset()

            except Exception as recovery_error:
                self.logger.error(f"Recovery failed: {recovery_error}")
                error_report.recovered = False
                circuit_breaker.record_failure()

        # Store updated report
        return error_report

    async def _log_error(self, error_report: ErrorReport) -> None:
        """Log error with appropriate severity."""
        context = error_report.context

        log_data = {
            "component": context.component,
            "operation": context.operation,
            "severity": context.severity.value,
            "retry_count": context.retry_count,
            "error_type": type(error_report.error).__name__,
            "error_message": str(error_report.error)
        }

        if context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(
                f"Critical error in {context.component}.{context.operation}",
                error=error_report.error,
                **log_data
            )
        elif context.severity == ErrorSeverity.HIGH:
            self.logger.error(
                f"High severity error in {context.component}.{context.operation}",
                error=error_report.error,
                **log_data
            )
        elif context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(
                f"Medium severity error in {context.component}.{context.operation}",
                error=error_report.error,
                **log_data
            )
        else:
            self.logger.info(
                f"Low severity error in {context.component}.{context.operation}",
                error=error_report.error,
                **log_data
            )

    async def _attempt_recovery(self, error_report: ErrorReport) -> RecoveryAction:
        """Attempt to recover from an error."""
        context = error_report.context

        # Try component-specific fallback first
        if context.component in self.fallback_handlers:
            try:
                self.logger.info(f"Attempting fallback for {context.component}")
                await self.fallback_handlers[context.component](error_report)
                return RecoveryAction.DEGRADED
            except Exception as e:
                self.logger.error(f"Fallback failed for {context.component}: {e}")

        # Try retry strategy
        if context.retry_count < context.max_retries:
            try:
                self.logger.info(f"Attempting retry for {context.component} (attempt {context.retry_count + 1})")
                await self._retry_strategy(error_report)
                return RecoveryAction.RETRY
            except Exception as e:
                self.logger.error(f"Retry failed for {context.component}: {e}")

        # Try restart strategy
        try:
            self.logger.info(f"Attempting restart for {context.component}")
            await self._restart_strategy(error_report)
            return RecoveryAction.RESTART
        except Exception as e:
            self.logger.error(f"Restart failed for {context.component}: {e}")

        # Default to degraded mode
        return RecoveryAction.DEGRADED

    async def _retry_strategy(self, error_report: ErrorReport) -> None:
        """Retry strategy implementation."""
        # Simple exponential backoff
        delay = min(2 ** error_report.context.retry_count, 60)
        await asyncio.sleep(delay)

    async def _restart_strategy(self, error_report: ErrorReport) -> None:
        """Restart strategy implementation."""
        # This would typically restart a service or component
        # For now, just log the intent
        self.logger.info(f"Restart strategy triggered for {error_report.context.component}")

    async def _degraded_mode_strategy(self, error_report: ErrorReport) -> None:
        """Degraded mode strategy implementation."""
        self.logger.warning(f"Entering degraded mode for {error_report.context.component}")

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics."""
        total_errors = len(self.error_history)
        if not total_errors:
            return {"total_errors": 0}

        recent_errors = [e for e in self.error_history if time.time() - e.timestamp < 3600]  # Last hour

        severity_counts = {}
        component_counts = {}
        recovery_counts = {}

        for error in self.error_history:
            severity = error.context.severity.value
            component = error.context.component
            recovery = error.recovery_action.value if error.recovery_action else "none"

            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            component_counts[component] = component_counts.get(component, 0) + 1
            recovery_counts[recovery] = recovery_counts.get(recovery, 0) + 1

        return {
            "total_errors": total_errors,
            "recent_errors": len(recent_errors),
            "severity_counts": severity_counts,
            "component_counts": component_counts,
            "recovery_counts": recovery_counts,
            "recovery_rate": sum(1 for e in self.error_history if e.recovered) / total_errors
        }

    def clear_error_history(self, older_than: float = 86400) -> int:
        """Clear old error history."""
        cutoff_time = time.time() - older_than
        old_count = len(self.error_history)
        self.error_history = [e for e in self.error_history if e.timestamp > cutoff_time]
        cleared_count = old_count - len(self.error_history)

        self.logger.info(f"Cleared {cleared_count} old error reports")
        return cleared_count


class CircuitBreaker:
    """Circuit breaker implementation for fault tolerance."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.failure_count = 0
        self.success_count = 0
        self.state = "closed"  # closed, open, half-open
        self.last_failure_time: Optional[float] = None

    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.state == "open":
            if self.last_failure_time and time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                self.success_count = 0
                return False
            return True
        return False

    def record_failure(self) -> None:
        """Record a failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def record_success(self) -> None:
        """Record a success."""
        if self.state == "half-open":
            self.success_count += 1

            if self.success_count >= self.success_threshold:
                self.reset()

    def reset(self) -> None:
        """Reset the circuit breaker."""
        self.failure_count = 0
        self.success_count = 0
        self.state = "closed"
        self.last_failure_time = None


# Decorators for error handling
F = TypeVar('F', bound=Callable[..., Any])


def handle_errors(
    component: str,
    operation: str,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    recoverable: bool = True,
    max_retries: int = 3
):
    """Decorator for automatic error handling."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get error handler from context (typically from dependency injection)
            # For now, create a new instance
            error_handler = ErrorHandler()

            context = ErrorContext(
                component=component,
                operation=operation,
                severity=severity,
                recoverable=recoverable,
                max_retries=max_retries
            )

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_report = await error_handler.handle_error(e, context)

                if error_report.recovered:
                    # Retry the operation if recovery was successful
                    if error_report.recovery_action == RecoveryAction.RETRY:
                        context.retry_count += 1
                        return await wrapper(*args, **kwargs)

                # Re-raise if not recovered or not recoverable
                raise e

        return wrapper  # type: ignore
    return decorator


@asynccontextmanager
async def error_boundary(
    component: str,
    operation: str,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
):
    """Async context manager for error boundaries."""
    error_handler = ErrorHandler()
    context = ErrorContext(component=component, operation=operation, severity=severity)

    try:
        yield context
    except Exception as e:
        await error_handler.handle_error(e, context)
        raise


# Global error handler instance
_error_handler_instance: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    global _error_handler_instance

    if _error_handler_instance is None:
        _error_handler_instance = ErrorHandler()

    return _error_handler_instance


def configure_error_handler(config: Dict[str, Any]) -> None:
    """Configure the global error handler."""
    handler = get_error_handler()

    # Configure circuit breakers
    if "circuit_breakers" in config:
        for name, cb_config in config["circuit_breakers"].items():
            handler.circuit_breakers[name] = CircuitBreaker(name, **cb_config)

    # Configure recovery strategies
    if "recovery_strategies" in config:
        for name, strategy in config["recovery_strategies"].items():
            handler.register_recovery_strategy(name, strategy)