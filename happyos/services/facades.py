"""
HappyOS Service Facades

Unified AWS service facades with built-in circuit breakers, retry logic,
and intelligent fallback patterns for maximum uptime.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from ..config import SDKConfig
from ..exceptions import ServiceUnavailableError, HappyOSSDKError
from ..observability import get_logger, MetricsCollector
from ..resilience import CircuitBreaker, RetryStrategy


class ServiceFacade(ABC):
    """
    Base class for all service facades.
    
    Provides enterprise patterns including:
    - Circuit breaker protection
    - Automatic retry logic
    - Fallback mechanisms
    - Observability integration
    """
    
    def __init__(self, service_name: str, config: SDKConfig):
        self.service_name = service_name
        self.config = config
        self.logger = get_logger(f"service.{service_name}")
        
        # Observability
        self.metrics = MetricsCollector(f"service_{service_name}")
        
        # Resilience
        self.circuit_breaker = CircuitBreaker(
            threshold=config.resilience.circuit_breaker_threshold,
            timeout=config.resilience.circuit_breaker_timeout
        )
        
        self.retry_strategy = RetryStrategy(
            max_attempts=config.resilience.retry_attempts,
            backoff_type=config.resilience.retry_backoff
        )
        
        # Service state
        self._aws_client = None
        self._local_fallback = None
        self._last_health_check = None
        
        self.logger.info(f"Service facade {service_name} initialized")
    
    async def execute_with_fallback(self, operation: str, *args, **kwargs) -> Any:
        """Execute operation with automatic fallback to local services."""
        try:
            # Try AWS service first
            result = await self.circuit_breaker.call(
                self._execute_aws_operation, operation, *args, **kwargs
            )
            
            self.metrics.increment(f'{operation}_success')
            return result
            
        except Exception as aws_error:
            self.logger.warning(f"AWS {operation} failed: {aws_error}")
            self.metrics.increment(f'{operation}_aws_failure')
            
            # Try local fallback if enabled
            if self.config.services.enable_local_fallback:
                try:
                    result = await self._execute_local_fallback(operation, *args, **kwargs)
                    self.metrics.increment(f'{operation}_fallback_success')
                    self.logger.info(f"Local fallback succeeded for {operation}")
                    return result
                    
                except Exception as fallback_error:
                    self.logger.error(f"Local fallback failed for {operation}: {fallback_error}")
                    self.metrics.increment(f'{operation}_fallback_failure')
            
            # Both AWS and fallback failed
            self.metrics.increment(f'{operation}_total_failure')
            raise ServiceUnavailableError(
                f"Service {self.service_name} operation {operation} failed",
                service_name=self.service_name
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform service health check."""
        try:
            health_status = {
                "service": self.service_name,
                "healthy": True,
                "checks": {},
                "timestamp": datetime.now().isoformat()
            }
            
            # AWS service health
            try:
                aws_health = await self._check_aws_health()
                health_status["checks"]["aws"] = aws_health
            except Exception as e:
                health_status["checks"]["aws"] = {"healthy": False, "error": str(e)}
            
            # Local fallback health (if enabled)
            if self.config.services.enable_local_fallback:
                try:
                    local_health = await self._check_local_health()
                    health_status["checks"]["local_fallback"] = local_health
                except Exception as e:
                    health_status["checks"]["local_fallback"] = {"healthy": False, "error": str(e)}
            
            # Circuit breaker status
            health_status["checks"]["circuit_breaker"] = {
                "healthy": not self.circuit_breaker.is_open(),
                "state": self.circuit_breaker.state.value,
                "failure_count": self.circuit_breaker.failure_count
            }
            
            # Overall health
            health_status["healthy"] = any(
                check.get("healthy", False) 
                for check in health_status["checks"].values()
            )
            
            self._last_health_check = health_status
            return health_status
            
        except Exception as e:
            return {
                "service": self.service_name,
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        return await self.metrics.get_summary()
    
    # Abstract methods that subclasses must implement
    
    @abstractmethod
    async def _execute_aws_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute operation using AWS service."""
        pass
    
    @abstractmethod
    async def _execute_local_fallback(self, operation: str, *args, **kwargs) -> Any:
        """Execute operation using local fallback."""
        pass
    
    @abstractmethod
    async def _check_aws_health(self) -> Dict[str, Any]:
        """Check AWS service health."""
        pass
    
    @abstractmethod
    async def _check_local_health(self) -> Dict[str, Any]:
        """Check local fallback health."""
        pass


class UnifiedServiceFacades:
    """
    Unified facade providing access to all AWS services with fallback patterns.
    
    This is the main entry point for accessing AWS services in HappyOS applications.
    """
    
    def __init__(self, config: Optional[SDKConfig] = None):
        self.config = config or SDKConfig.from_environment()
        self.logger = get_logger("unified_services")
        
        # Initialize service facades
        self._services: Dict[str, ServiceFacade] = {}
        self._initialize_services()
        
        self.logger.info("Unified service facades initialized")
    
    def _initialize_services(self):
        """Initialize all service facades."""
        from .unified import (
            DatabaseService,
            StorageService,
            ComputeService,
            SearchService,
            MessagingService
        )
        
        self._services = {
            "database": DatabaseService(self.config),
            "storage": StorageService(self.config),
            "compute": ComputeService(self.config),
            "search": SearchService(self.config),
            "messaging": MessagingService(self.config)
        }
    
    @property
    def database(self) -> 'DatabaseService':
        """Get database service facade."""
        return self._services["database"]
    
    @property
    def storage(self) -> 'StorageService':
        """Get storage service facade."""
        return self._services["storage"]
    
    @property
    def compute(self) -> 'ComputeService':
        """Get compute service facade."""
        return self._services["compute"]
    
    @property
    def search(self) -> 'SearchService':
        """Get search service facade."""
        return self._services["search"]
    
    @property
    def messaging(self) -> 'MessagingService':
        """Get messaging service facade."""
        return self._services["messaging"]
    
    async def health_check_all(self) -> Dict[str, Any]:
        """Perform health check on all services."""
        health_results = {}
        
        for service_name, service in self._services.items():
            try:
                health_results[service_name] = await service.health_check()
            except Exception as e:
                health_results[service_name] = {
                    "healthy": False,
                    "error": str(e)
                }
        
        # Overall system health
        overall_healthy = any(
            result.get("healthy", False) 
            for result in health_results.values()
        )
        
        return {
            "overall_healthy": overall_healthy,
            "services": health_results,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics from all services."""
        metrics = {}
        
        for service_name, service in self._services.items():
            try:
                metrics[service_name] = await service.get_metrics()
            except Exception as e:
                metrics[service_name] = {"error": str(e)}
        
        return metrics
    
    def get_service(self, service_name: str) -> Optional[ServiceFacade]:
        """Get a specific service facade by name."""
        return self._services.get(service_name)