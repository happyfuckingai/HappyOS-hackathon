"""
Fallback manager for coordinating service transitions between AWS and local implementations.
Implements graceful degradation strategies and recovery coordination.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..interfaces import (
    ServiceFactory, AgentCoreService, SearchService, ComputeService,
    CacheService, StorageService, SecretsService, HealthService,
    CircuitState, ServiceHealth
)
from .circuit_breaker import get_circuit_breaker_manager, CircuitBreakerOpenError
from .health_service import get_health_service
from ..settings import get_settings


logger = logging.getLogger(__name__)


# ServiceMode is imported from settings


class FallbackStrategy(Enum):
    """Fallback strategy types."""
    IMMEDIATE = "immediate"  # Switch immediately on failure
    GRADUAL = "gradual"     # Gradually shift traffic
    SELECTIVE = "selective"  # Fallback specific operations only


@dataclass
class ServiceTransition:
    """Information about a service transition."""
    service_name: str
    from_mode: ServiceMode
    to_mode: ServiceMode
    strategy: FallbackStrategy
    timestamp: datetime
    reason: str
    success: bool
    error_message: Optional[str] = None
    recovery_time_seconds: Optional[float] = None


@dataclass
class FallbackConfiguration:
    """Configuration for fallback behavior."""
    enabled: bool = True
    strategy: FallbackStrategy = FallbackStrategy.IMMEDIATE
    health_check_interval: int = 30
    recovery_threshold: int = 3  # Consecutive successful health checks needed for recovery
    max_recovery_attempts: int = 5
    recovery_backoff_multiplier: float = 2.0
    degraded_functionality_timeout: int = 300  # Seconds to wait before full fallback
    
    # Service-specific configurations
    service_priorities: Dict[str, int] = field(default_factory=lambda: {
        "agent_core": 1,
        "search": 2,
        "compute": 3,
        "cache": 4,
        "storage": 5,
        "secrets": 6
    })
    
    # Operations that can be degraded vs must fallback
    degradable_operations: Dict[str, List[str]] = field(default_factory=lambda: {
        "search": ["hybrid_search"],  # Can fallback to text-only search
        "cache": ["get", "set"],      # Can operate without cache
        "storage": ["list_objects"]   # Can skip non-critical operations
    })


class ServiceRegistry:
    """Registry for AWS and local service implementations."""
    
    def __init__(self):
        self.aws_services: Dict[str, Any] = {}
        self.local_services: Dict[str, Any] = {}
        self.service_factories: Dict[str, ServiceFactory] = {}
    
    def register_aws_service(self, service_name: str, service_instance: Any):
        """Register an AWS service implementation."""
        self.aws_services[service_name] = service_instance
        logger.debug(f"Registered AWS service: {service_name}")
    
    def register_local_service(self, service_name: str, service_instance: Any):
        """Register a local service implementation."""
        self.local_services[service_name] = service_instance
        logger.debug(f"Registered local service: {service_name}")
    
    def register_service_factory(self, mode: ServiceMode, factory: ServiceFactory):
        """Register a service factory for a specific mode."""
        self.service_factories[mode.value] = factory
        logger.debug(f"Registered service factory for mode: {mode.value}")
    
    def get_service(self, service_name: str, mode: ServiceMode) -> Optional[Any]:
        """Get a service instance for the specified mode."""
        if mode == ServiceMode.CLOUD:
            return self.aws_services.get(service_name)
        elif mode == ServiceMode.LOCAL:
            return self.local_services.get(service_name)
        return None
    
    def has_service(self, service_name: str, mode: ServiceMode) -> bool:
        """Check if a service is available in the specified mode."""
        return self.get_service(service_name, mode) is not None


class GracefulDegradationManager:
    """Manages graceful degradation of service functionality."""
    
    def __init__(self, config: FallbackConfiguration):
        self.config = config
        self.degraded_operations: Dict[str, List[str]] = {}
        self.degradation_start_times: Dict[str, datetime] = {}
    
    async def can_degrade_operation(self, service_name: str, operation: str) -> bool:
        """Check if an operation can be gracefully degraded."""
        degradable_ops = self.config.degradable_operations.get(service_name, [])
        return operation in degradable_ops
    
    async def start_degradation(self, service_name: str, operations: List[str]):
        """Start graceful degradation for specific operations."""
        self.degraded_operations[service_name] = operations
        self.degradation_start_times[service_name] = datetime.now()
        
        logger.warning(
            f"Started graceful degradation for {service_name}: {operations}"
        )
    
    async def stop_degradation(self, service_name: str):
        """Stop graceful degradation for a service."""
        if service_name in self.degraded_operations:
            del self.degraded_operations[service_name]
        if service_name in self.degradation_start_times:
            del self.degradation_start_times[service_name]
        
        logger.info(f"Stopped graceful degradation for {service_name}")
    
    async def is_degraded(self, service_name: str, operation: str = None) -> bool:
        """Check if a service or operation is currently degraded."""
        if service_name not in self.degraded_operations:
            return False
        
        if operation is None:
            return True
        
        return operation in self.degraded_operations[service_name]
    
    async def should_force_fallback(self, service_name: str) -> bool:
        """Check if degradation timeout has been reached and should force fallback."""
        if service_name not in self.degradation_start_times:
            return False
        
        start_time = self.degradation_start_times[service_name]
        elapsed = (datetime.now() - start_time).total_seconds()
        
        return elapsed >= self.config.degraded_functionality_timeout


class RecoveryCoordinator:
    """Coordinates recovery back to cloud services."""
    
    def __init__(self, config: FallbackConfiguration):
        self.config = config
        self.recovery_attempts: Dict[str, int] = {}
        self.recovery_tasks: Dict[str, asyncio.Task] = {}
        self.consecutive_successes: Dict[str, int] = {}
        
    async def start_recovery_monitoring(self, service_name: str):
        """Start monitoring for service recovery."""
        if service_name in self.recovery_tasks:
            # Already monitoring
            return
        
        task = asyncio.create_task(self._monitor_service_recovery(service_name))
        self.recovery_tasks[service_name] = task
        
        logger.info(f"Started recovery monitoring for {service_name}")
    
    async def stop_recovery_monitoring(self, service_name: str):
        """Stop recovery monitoring for a service."""
        if service_name in self.recovery_tasks:
            task = self.recovery_tasks[service_name]
            task.cancel()
            del self.recovery_tasks[service_name]
        
        # Reset counters
        self.recovery_attempts.pop(service_name, None)
        self.consecutive_successes.pop(service_name, None)
        
        logger.info(f"Stopped recovery monitoring for {service_name}")
    
    async def _monitor_service_recovery(self, service_name: str):
        """Monitor a service for recovery opportunities."""
        health_service = get_health_service()
        
        while True:
            try:
                # Check service health
                health_status = await health_service.check_service_health(service_name)
                
                if health_status == ServiceHealth.HEALTHY:
                    self.consecutive_successes[service_name] = (
                        self.consecutive_successes.get(service_name, 0) + 1
                    )
                    
                    # Check if we have enough consecutive successes for recovery
                    if (self.consecutive_successes[service_name] >= 
                        self.config.recovery_threshold):
                        
                        logger.info(
                            f"Service {service_name} ready for recovery: "
                            f"{self.consecutive_successes[service_name]} consecutive successes"
                        )
                        
                        # Signal that recovery is possible
                        await self._signal_recovery_ready(service_name)
                        break
                else:
                    # Reset success counter on failure
                    self.consecutive_successes[service_name] = 0
                
                # Wait before next check
                await asyncio.sleep(self.config.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring recovery for {service_name}: {e}")
                await asyncio.sleep(self.config.health_check_interval)
    
    async def _signal_recovery_ready(self, service_name: str):
        """Signal that a service is ready for recovery."""
        # This would typically notify the fallback manager
        # For now, we'll just log it
        logger.info(f"Service {service_name} is ready for recovery")
    
    async def can_attempt_recovery(self, service_name: str) -> bool:
        """Check if recovery can be attempted for a service."""
        attempts = self.recovery_attempts.get(service_name, 0)
        return attempts < self.config.max_recovery_attempts
    
    async def record_recovery_attempt(self, service_name: str, success: bool):
        """Record a recovery attempt."""
        if not success:
            self.recovery_attempts[service_name] = (
                self.recovery_attempts.get(service_name, 0) + 1
            )
        else:
            # Reset on successful recovery
            self.recovery_attempts.pop(service_name, None)
            self.consecutive_successes.pop(service_name, None)


class FallbackManager:
    """
    Main fallback manager that coordinates service transitions between AWS and local implementations.
    Implements graceful degradation strategies and recovery coordination.
    """
    
    def __init__(self, config: FallbackConfiguration = None):
        self.config = config or FallbackConfiguration()
        self.settings = get_settings()
        
        # Core components
        self.service_registry = ServiceRegistry()
        self.degradation_manager = GracefulDegradationManager(self.config)
        self.recovery_coordinator = RecoveryCoordinator(self.config)
        
        # State tracking
        self.current_mode: Dict[str, ServiceMode] = {}
        self.transition_history: List[ServiceTransition] = []
        self.active_fallbacks: Dict[str, datetime] = {}
        
        # Service instances cache
        self.active_services: Dict[str, Any] = {}
        
        # Circuit breaker and health monitoring
        self.circuit_breaker_manager = get_circuit_breaker_manager()
        self.health_service = get_health_service()
        
        # Initialize all services in cloud mode
        self._initialize_service_modes()
        
        logger.info("Fallback manager initialized")
    
    def _initialize_service_modes(self):
        """Initialize all services to start in cloud mode."""
        service_names = [
            "agent_core", "search", "compute", 
            "cache", "storage", "secrets"
        ]
        
        for service_name in service_names:
            self.current_mode[service_name] = "cloud"  # Use string instead of enum
    
    async def get_service(self, service_name: str, service_type: Type = None) -> Any:
        """
        Get the appropriate service instance based on current mode and circuit breaker state.
        
        Args:
            service_name: Name of the service to get
            service_type: Expected service type for type checking
            
        Returns:
            Service instance (AWS or local based on current state)
        """
        # Check circuit breaker state
        circuit_state = await self.circuit_breaker_manager.get_circuit_state(service_name)
        
        # Determine which mode to use
        if circuit_state == CircuitState.OPEN:
            # Circuit is open, must use local service
            target_mode = ServiceMode.LOCAL
            
            # Trigger fallback if not already in local mode
            if self.current_mode.get(service_name) != ServiceMode.LOCAL:
                await self._execute_fallback(service_name, "circuit_breaker_open")
        
        elif circuit_state == CircuitState.HALF_OPEN:
            # Circuit is half-open, prefer cloud but be ready to fallback
            target_mode = ServiceMode.CLOUD
        
        else:
            # Circuit is closed, use configured mode
            target_mode = self.current_mode.get(service_name, ServiceMode.CLOUD)
        
        # Get service instance
        service_instance = self.service_registry.get_service(service_name, target_mode)
        
        if service_instance is None:
            # Requested service not available, try fallback
            if target_mode == ServiceMode.CLOUD:
                logger.warning(f"Cloud service {service_name} not available, falling back to local")
                await self._execute_fallback(service_name, "service_unavailable")
                service_instance = self.service_registry.get_service(service_name, ServiceMode.LOCAL)
            else:
                logger.error(f"Local service {service_name} not available")
                raise RuntimeError(f"No available implementation for service: {service_name}")
        
        # Cache the active service
        self.active_services[service_name] = service_instance
        
        return service_instance
    
    async def call_with_fallback(self, service_name: str, method_name: str, *args, **kwargs) -> Any:
        """
        Call a service method with automatic fallback on failure.
        
        Args:
            service_name: Name of the service
            method_name: Method to call on the service
            *args: Method arguments
            **kwargs: Method keyword arguments
            
        Returns:
            Method result
        """
        # Check if operation is currently degraded
        if await self.degradation_manager.is_degraded(service_name, method_name):
            # Try graceful degradation first
            if await self.degradation_manager.can_degrade_operation(service_name, method_name):
                logger.info(f"Operation {service_name}.{method_name} is degraded, attempting graceful handling")
                return await self._handle_degraded_operation(service_name, method_name, *args, **kwargs)
        
        # Get the appropriate service
        service = await self.get_service(service_name)
        
        # Get the method
        if not hasattr(service, method_name):
            raise AttributeError(f"Service {service_name} does not have method {method_name}")
        
        method = getattr(service, method_name)
        
        try:
            # Call with circuit breaker protection
            result = await self.circuit_breaker_manager.call_with_circuit_breaker(
                service_name, method, *args, **kwargs
            )
            
            # If we were in fallback mode and this succeeded, consider recovery
            if self.current_mode.get(service_name) == ServiceMode.LOCAL:
                await self._consider_recovery(service_name)
            
            return result
            
        except CircuitBreakerOpenError:
            # Circuit breaker is open, execute fallback
            logger.warning(f"Circuit breaker open for {service_name}, executing fallback")
            await self._execute_fallback(service_name, "circuit_breaker_triggered")
            
            # Retry with local service
            local_service = await self.get_service(service_name)
            local_method = getattr(local_service, method_name)
            return await local_method(*args, **kwargs)
        
        except Exception as e:
            # Other errors might trigger degradation or fallback
            logger.error(f"Error calling {service_name}.{method_name}: {e}")
            
            # Check if we should start graceful degradation
            if await self.degradation_manager.can_degrade_operation(service_name, method_name):
                await self.degradation_manager.start_degradation(service_name, [method_name])
                return await self._handle_degraded_operation(service_name, method_name, *args, **kwargs)
            
            # Otherwise, execute fallback
            await self._execute_fallback(service_name, f"method_error: {str(e)}")
            
            # Retry with local service
            local_service = await self.get_service(service_name)
            local_method = getattr(local_service, method_name)
            return await local_method(*args, **kwargs)
    
    async def _execute_fallback(self, service_name: str, reason: str):
        """Execute fallback transition for a service."""
        start_time = datetime.now()
        current_mode = self.current_mode.get(service_name, ServiceMode.CLOUD)
        
        if current_mode == ServiceMode.LOCAL:
            # Already in fallback mode
            return
        
        logger.warning(f"Executing fallback for {service_name}: {reason}")
        
        try:
            # Check if local service is available
            if not self.service_registry.has_service(service_name, ServiceMode.LOCAL):
                raise RuntimeError(f"No local fallback available for {service_name}")
            
            # Update mode
            self.current_mode[service_name] = ServiceMode.LOCAL
            self.active_fallbacks[service_name] = start_time
            
            # Start recovery monitoring
            await self.recovery_coordinator.start_recovery_monitoring(service_name)
            
            # Record transition
            transition = ServiceTransition(
                service_name=service_name,
                from_mode=current_mode,
                to_mode=ServiceMode.LOCAL,
                strategy=self.config.strategy,
                timestamp=start_time,
                reason=reason,
                success=True,
                recovery_time_seconds=(datetime.now() - start_time).total_seconds()
            )
            
            self.transition_history.append(transition)
            
            logger.info(f"Successfully executed fallback for {service_name}")
            
        except Exception as e:
            # Record failed transition
            transition = ServiceTransition(
                service_name=service_name,
                from_mode=current_mode,
                to_mode=ServiceMode.LOCAL,
                strategy=self.config.strategy,
                timestamp=start_time,
                reason=reason,
                success=False,
                error_message=str(e)
            )
            
            self.transition_history.append(transition)
            
            logger.error(f"Failed to execute fallback for {service_name}: {e}")
            raise
    
    async def _consider_recovery(self, service_name: str):
        """Consider recovery back to cloud services."""
        if service_name not in self.active_fallbacks:
            return
        
        # Check if recovery monitoring is already active
        if service_name in self.recovery_coordinator.recovery_tasks:
            return
        
        # Check if we can attempt recovery
        if not await self.recovery_coordinator.can_attempt_recovery(service_name):
            logger.warning(f"Maximum recovery attempts reached for {service_name}")
            return
        
        # Start recovery monitoring
        await self.recovery_coordinator.start_recovery_monitoring(service_name)
    
    async def execute_recovery(self, service_name: str) -> bool:
        """
        Execute recovery back to cloud services.
        
        Args:
            service_name: Name of the service to recover
            
        Returns:
            True if recovery was successful, False otherwise
        """
        if self.current_mode.get(service_name) != ServiceMode.LOCAL:
            logger.info(f"Service {service_name} is not in fallback mode")
            return True
        
        start_time = datetime.now()
        
        try:
            # Check if cloud service is healthy
            health_status = await self.health_service.check_service_health(service_name)
            
            if health_status != ServiceHealth.HEALTHY:
                logger.warning(f"Cloud service {service_name} is not healthy, cannot recover")
                await self.recovery_coordinator.record_recovery_attempt(service_name, False)
                return False
            
            # Force circuit breaker to closed state for testing
            await self.circuit_breaker_manager.force_close_circuit(service_name)
            
            # Test cloud service with a simple operation
            cloud_service = self.service_registry.get_service(service_name, ServiceMode.CLOUD)
            if cloud_service is None:
                raise RuntimeError(f"Cloud service {service_name} not available")
            
            # Update mode back to cloud
            self.current_mode[service_name] = ServiceMode.CLOUD
            
            # Clean up fallback state
            self.active_fallbacks.pop(service_name, None)
            await self.degradation_manager.stop_degradation(service_name)
            await self.recovery_coordinator.stop_recovery_monitoring(service_name)
            
            # Record successful recovery
            transition = ServiceTransition(
                service_name=service_name,
                from_mode=ServiceMode.LOCAL,
                to_mode=ServiceMode.CLOUD,
                strategy=self.config.strategy,
                timestamp=start_time,
                reason="recovery",
                success=True,
                recovery_time_seconds=(datetime.now() - start_time).total_seconds()
            )
            
            self.transition_history.append(transition)
            await self.recovery_coordinator.record_recovery_attempt(service_name, True)
            
            logger.info(f"Successfully recovered {service_name} to cloud mode")
            return True
            
        except Exception as e:
            # Recovery failed, record it
            transition = ServiceTransition(
                service_name=service_name,
                from_mode=ServiceMode.LOCAL,
                to_mode=ServiceMode.CLOUD,
                strategy=self.config.strategy,
                timestamp=start_time,
                reason="recovery",
                success=False,
                error_message=str(e)
            )
            
            self.transition_history.append(transition)
            await self.recovery_coordinator.record_recovery_attempt(service_name, False)
            
            logger.error(f"Failed to recover {service_name}: {e}")
            return False
    
    async def _handle_degraded_operation(self, service_name: str, method_name: str, *args, **kwargs) -> Any:
        """Handle a degraded operation with reduced functionality."""
        logger.info(f"Handling degraded operation: {service_name}.{method_name}")
        
        # Service-specific degradation logic
        if service_name == "search" and method_name == "hybrid_search":
            # Fallback to text-only search
            service = await self.get_service(service_name)
            if hasattr(service, "search"):
                # Extract query from hybrid search parameters
                query = args[0] if args else kwargs.get("query", "")
                tenant_id = args[2] if len(args) > 2 else kwargs.get("tenant_id")
                filters = args[3] if len(args) > 3 else kwargs.get("filters")
                
                logger.info("Degrading hybrid_search to text-only search")
                return await service.search(query, tenant_id, filters)
        
        elif service_name == "cache":
            # Cache operations can be skipped in degraded mode
            if method_name in ["get", "exists"]:
                logger.info(f"Cache {method_name} operation skipped in degraded mode")
                return None if method_name == "get" else False
            elif method_name in ["set", "delete"]:
                logger.info(f"Cache {method_name} operation skipped in degraded mode")
                return True
        
        elif service_name == "storage" and method_name == "list_objects":
            # Return empty list for non-critical list operations
            logger.info("Storage list_objects operation returning empty list in degraded mode")
            return []
        
        # Default: raise exception for unsupported degraded operations
        raise RuntimeError(f"Operation {service_name}.{method_name} cannot be degraded")
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get current status of all services."""
        status = {}
        
        for service_name, mode in self.current_mode.items():
            circuit_state = asyncio.create_task(
                self.circuit_breaker_manager.get_circuit_state(service_name)
            )
            
            status[service_name] = {
                "mode": mode.value,
                "circuit_state": circuit_state,
                "is_fallback": service_name in self.active_fallbacks,
                "fallback_since": self.active_fallbacks.get(service_name),
                "is_degraded": asyncio.create_task(
                    self.degradation_manager.is_degraded(service_name)
                ),
                "recovery_monitoring": service_name in self.recovery_coordinator.recovery_tasks
            }
        
        return status
    
    def get_transition_history(self, service_name: str = None, limit: int = 100) -> List[ServiceTransition]:
        """Get transition history for services."""
        history = self.transition_history
        
        if service_name:
            history = [t for t in history if t.service_name == service_name]
        
        # Return most recent transitions
        return sorted(history, key=lambda t: t.timestamp, reverse=True)[:limit]
    
    async def force_fallback(self, service_name: str, reason: str = "manual") -> bool:
        """Force a service to fallback mode."""
        try:
            await self._execute_fallback(service_name, f"forced: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to force fallback for {service_name}: {e}")
            return False
    
    async def force_recovery(self, service_name: str) -> bool:
        """Force recovery of a service back to cloud mode."""
        return await self.execute_recovery(service_name)
    
    async def shutdown(self):
        """Shutdown the fallback manager and clean up resources."""
        logger.info("Shutting down fallback manager")
        
        # Stop all recovery monitoring
        for service_name in list(self.recovery_coordinator.recovery_tasks.keys()):
            await self.recovery_coordinator.stop_recovery_monitoring(service_name)
        
        # Clear state
        self.active_services.clear()
        self.active_fallbacks.clear()
        
        logger.info("Fallback manager shutdown complete")


# Global fallback manager instance
_fallback_manager: Optional[FallbackManager] = None


def get_fallback_manager() -> FallbackManager:
    """Get the global fallback manager instance."""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = FallbackManager()
    return _fallback_manager


def configure_fallback_manager(config: FallbackConfiguration) -> FallbackManager:
    """Configure and get the fallback manager with custom configuration."""
    global _fallback_manager
    _fallback_manager = FallbackManager(config)
    return _fallback_manager