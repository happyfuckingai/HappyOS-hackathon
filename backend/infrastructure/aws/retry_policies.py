"""
AWS-specific retry policies and error handling.

This module extends the existing resilience patterns with AWS-specific
error handling, exponential backoff, and service-specific retry strategies.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError
from backend.services.integration.resilience import (
    RetryHandler, RetryConfig, CircuitBreaker, CircuitBreakerConfig,
    GracefulDegradationHandler, CircuitBreakerOpenError
)

logger = logging.getLogger(__name__)


class AWSErrorType(Enum):
    """AWS-specific error types for retry strategies."""
    THROTTLING = "throttling"
    TEMPORARY = "temporary"
    PERMANENT = "permanent"
    CREDENTIALS = "credentials"
    NETWORK = "network"
    SERVICE_UNAVAILABLE = "service_unavailable"


@dataclass
class AWSRetryConfig(RetryConfig):
    """AWS-specific retry configuration."""
    throttling_base_delay: float = 2.0
    throttling_max_delay: float = 300.0  # 5 minutes
    service_unavailable_delay: float = 5.0
    credential_retry_attempts: int = 1  # Don't retry credential errors
    
    # Service-specific configurations
    dynamodb_max_attempts: int = 5
    s3_max_attempts: int = 3
    lambda_max_attempts: int = 3
    opensearch_max_attempts: int = 4
    elasticache_max_attempts: int = 3
    secrets_manager_max_attempts: int = 3


class AWSErrorClassifier:
    """Classifies AWS errors for appropriate retry strategies."""
    
    # Throttling error codes
    THROTTLING_ERRORS = {
        'Throttling',
        'ThrottlingException', 
        'ProvisionedThroughputExceededException',
        'RequestLimitExceeded',
        'TooManyRequestsException',
        'SlowDown',
        'RequestThrottled'
    }
    
    # Temporary errors that should be retried
    TEMPORARY_ERRORS = {
        'InternalServerError',
        'InternalError',
        'ServiceUnavailable',
        'ServiceUnavailableException',
        'InternalServiceError',
        'InternalFailure',
        'RequestTimeout',
        'RequestTimeoutException'
    }
    
    # Permanent errors that should not be retried
    PERMANENT_ERRORS = {
        'ValidationException',
        'InvalidParameterValue',
        'InvalidParameterCombination',
        'MissingParameter',
        'ResourceNotFoundException',
        'ResourceNotFound',
        'NoSuchBucket',
        'NoSuchKey',
        'AccessDenied',
        'Forbidden',
        'UnauthorizedOperation',
        'InvalidUserID.NotFound',
        'InvalidGroupId.NotFound'
    }
    
    # Credential-related errors
    CREDENTIAL_ERRORS = {
        'InvalidAccessKeyId',
        'SignatureDoesNotMatch',
        'TokenRefreshRequired',
        'ExpiredToken',
        'InvalidToken',
        'CredentialsNotFound'
    }
    
    @classmethod
    def classify_error(cls, error: Exception) -> AWSErrorType:
        """Classify an AWS error for retry strategy."""
        if isinstance(error, NoCredentialsError):
            return AWSErrorType.CREDENTIALS
        
        if isinstance(error, (ConnectionError, TimeoutError)):
            return AWSErrorType.NETWORK
        
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', '')
            
            if error_code in cls.THROTTLING_ERRORS:
                return AWSErrorType.THROTTLING
            elif error_code in cls.TEMPORARY_ERRORS:
                return AWSErrorType.TEMPORARY
            elif error_code in cls.PERMANENT_ERRORS:
                return AWSErrorType.PERMANENT
            elif error_code in cls.CREDENTIAL_ERRORS:
                return AWSErrorType.CREDENTIALS
            
            # Check HTTP status code
            status_code = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
            if status_code == 503:
                return AWSErrorType.SERVICE_UNAVAILABLE
            elif status_code in [500, 502, 504]:
                return AWSErrorType.TEMPORARY
            elif status_code in [400, 403, 404]:
                return AWSErrorType.PERMANENT
            elif status_code == 429:
                return AWSErrorType.THROTTLING
        
        # Default to temporary for unknown errors
        return AWSErrorType.TEMPORARY
    
    @classmethod
    def should_retry(cls, error: Exception) -> bool:
        """Determine if an error should be retried."""
        error_type = cls.classify_error(error)
        return error_type in [
            AWSErrorType.THROTTLING,
            AWSErrorType.TEMPORARY,
            AWSErrorType.NETWORK,
            AWSErrorType.SERVICE_UNAVAILABLE
        ]


class AWSRetryHandler(RetryHandler):
    """AWS-specific retry handler with intelligent backoff strategies."""
    
    def __init__(self, config: AWSRetryConfig, service_name: str = "aws"):
        super().__init__(config)
        self.aws_config = config
        self.service_name = service_name
        self.logger = logging.getLogger(f"{__name__}.{service_name}")
    
    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute AWS operation with intelligent retry logic."""
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                self.logger.debug(f"AWS {self.service_name} attempt {attempt + 1}/{self.config.max_attempts}")
                result = await operation(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"AWS {self.service_name} succeeded on attempt {attempt + 1}")
                
                return result
                
            except Exception as e:
                last_exception = e
                error_type = AWSErrorClassifier.classify_error(e)
                
                self.logger.warning(
                    f"AWS {self.service_name} attempt {attempt + 1} failed: {error_type.value} - {str(e)}"
                )
                
                # Don't retry permanent errors or credential errors
                if error_type in [AWSErrorType.PERMANENT, AWSErrorType.CREDENTIALS]:
                    self.logger.error(f"AWS {self.service_name} permanent error, not retrying: {str(e)}")
                    break
                
                # Check if we should retry
                if not AWSErrorClassifier.should_retry(e):
                    self.logger.error(f"AWS {self.service_name} error not retryable: {str(e)}")
                    break
                
                if attempt < self.config.max_attempts - 1:
                    delay = self._calculate_aws_delay(attempt, error_type)
                    self.logger.debug(f"AWS {self.service_name} waiting {delay:.2f}s before retry")
                    await asyncio.sleep(delay)
        
        self.logger.error(
            f"AWS {self.service_name} all {self.config.max_attempts} attempts failed. "
            f"Last error: {str(last_exception)}"
        )
        raise last_exception
    
    def _calculate_aws_delay(self, attempt: int, error_type: AWSErrorType) -> float:
        """Calculate delay with AWS-specific strategies."""
        if error_type == AWSErrorType.THROTTLING:
            # Exponential backoff with longer delays for throttling
            delay = min(
                self.aws_config.throttling_base_delay * (2 ** attempt),
                self.aws_config.throttling_max_delay
            )
        elif error_type == AWSErrorType.SERVICE_UNAVAILABLE:
            # Fixed delay for service unavailable
            delay = self.aws_config.service_unavailable_delay
        else:
            # Standard exponential backoff
            delay = min(
                self.config.base_delay * (self.config.exponential_base ** attempt),
                self.config.max_delay
            )
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class AWSServiceRetryManager:
    """Manages retry policies for different AWS services."""
    
    def __init__(self):
        self.retry_handlers: Dict[str, AWSRetryHandler] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.degradation_handler = GracefulDegradationHandler()
        
        # Initialize service-specific configurations
        self._initialize_service_configs()
    
    def _initialize_service_configs(self):
        """Initialize retry configurations for each AWS service."""
        services_config = {
            'dynamodb': AWSRetryConfig(
                max_attempts=5,
                base_delay=0.1,
                max_delay=20.0,
                throttling_base_delay=1.0,
                throttling_max_delay=60.0
            ),
            's3': AWSRetryConfig(
                max_attempts=3,
                base_delay=0.5,
                max_delay=30.0,
                throttling_base_delay=2.0
            ),
            'lambda': AWSRetryConfig(
                max_attempts=3,
                base_delay=1.0,
                max_delay=60.0,
                throttling_base_delay=5.0
            ),
            'opensearch': AWSRetryConfig(
                max_attempts=4,
                base_delay=1.0,
                max_delay=45.0,
                throttling_base_delay=3.0
            ),
            'elasticache': AWSRetryConfig(
                max_attempts=3,
                base_delay=0.5,
                max_delay=30.0
            ),
            'secretsmanager': AWSRetryConfig(
                max_attempts=3,
                base_delay=0.5,
                max_delay=20.0
            ),
            'apigateway': AWSRetryConfig(
                max_attempts=3,
                base_delay=1.0,
                max_delay=30.0
            )
        }
        
        # Create retry handlers and circuit breakers for each service
        for service_name, config in services_config.items():
            self.retry_handlers[service_name] = AWSRetryHandler(config, service_name)
            
            # Create circuit breaker with service-specific thresholds
            cb_config = CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60,
                success_threshold=3
            )
            self.circuit_breakers[service_name] = CircuitBreaker(cb_config)
    
    async def execute_with_resilience(
        self,
        service_name: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with full resilience (retry + circuit breaker)."""
        retry_handler = self.retry_handlers.get(service_name)
        circuit_breaker = self.circuit_breakers.get(service_name)
        
        if not retry_handler or not circuit_breaker:
            raise ValueError(f"Unknown AWS service: {service_name}")
        
        async def resilient_operation():
            return await retry_handler.execute_with_retry(operation, *args, **kwargs)
        
        try:
            return await circuit_breaker.execute(resilient_operation)
        except CircuitBreakerOpenError:
            # Circuit breaker is open, provide fallback if available
            logger.warning(f"AWS {service_name} circuit breaker is open, attempting fallback")
            return await self._handle_circuit_breaker_open(service_name, operation, *args, **kwargs)
    
    async def _handle_circuit_breaker_open(
        self,
        service_name: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Handle circuit breaker open state with fallbacks."""
        # Service-specific fallback strategies
        if service_name == 'dynamodb':
            # For DynamoDB operations, we might fall back to local storage
            logger.info("DynamoDB circuit breaker open, falling back to local storage")
            raise CircuitBreakerOpenError(f"DynamoDB unavailable, use local fallback")
        
        elif service_name == 's3':
            # For S3 operations, we might fall back to local file storage
            logger.info("S3 circuit breaker open, falling back to local file storage")
            raise CircuitBreakerOpenError(f"S3 unavailable, use local fallback")
        
        elif service_name == 'opensearch':
            # For search operations, we might fall back to local search
            logger.info("OpenSearch circuit breaker open, falling back to local search")
            raise CircuitBreakerOpenError(f"OpenSearch unavailable, use local fallback")
        
        elif service_name == 'lambda':
            # For Lambda operations, we might fall back to local execution
            logger.info("Lambda circuit breaker open, falling back to local execution")
            raise CircuitBreakerOpenError(f"Lambda unavailable, use local fallback")
        
        else:
            # Generic fallback
            logger.error(f"No fallback available for {service_name}")
            raise CircuitBreakerOpenError(f"AWS {service_name} unavailable and no fallback configured")
    
    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get status of a specific AWS service."""
        circuit_breaker = self.circuit_breakers.get(service_name)
        if not circuit_breaker:
            return {"error": f"Unknown service: {service_name}"}
        
        return {
            "service": service_name,
            "circuit_breaker_state": circuit_breaker.state.value,
            "failure_count": circuit_breaker.failure_count,
            "success_count": circuit_breaker.success_count,
            "last_failure_time": circuit_breaker.last_failure_time
        }
    
    def get_all_services_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all AWS services."""
        return {
            service_name: self.get_service_status(service_name)
            for service_name in self.circuit_breakers.keys()
        }
    
    def force_circuit_breaker_state(self, service_name: str, state: str) -> bool:
        """Force circuit breaker to a specific state (for testing/maintenance)."""
        circuit_breaker = self.circuit_breakers.get(service_name)
        if not circuit_breaker:
            return False
        
        if state.lower() == 'open':
            circuit_breaker._trip()
        elif state.lower() == 'closed':
            circuit_breaker._reset()
        else:
            return False
        
        logger.info(f"Forced {service_name} circuit breaker to {state.upper()} state")
        return True


# Global retry manager instance
_retry_manager: Optional[AWSServiceRetryManager] = None


def get_aws_retry_manager() -> AWSServiceRetryManager:
    """Get or create the global AWS retry manager."""
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = AWSServiceRetryManager()
    return _retry_manager


# Decorator for AWS operations
def aws_resilient(service_name: str):
    """Decorator to add resilience to AWS operations."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            retry_manager = get_aws_retry_manager()
            return await retry_manager.execute_with_resilience(
                service_name, func, *args, **kwargs
            )
        return wrapper
    return decorator


# Context manager for AWS operations
class AWSResilientContext:
    """Context manager for AWS operations with resilience."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.retry_manager = get_aws_retry_manager()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Log any exceptions for monitoring
        if exc_type:
            logger.error(f"AWS {self.service_name} operation failed: {exc_val}")
    
    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation with resilience."""
        return await self.retry_manager.execute_with_resilience(
            self.service_name, operation, *args, **kwargs
        )


# Utility functions
async def execute_aws_operation(
    service_name: str,
    operation: Callable,
    *args,
    **kwargs
) -> Any:
    """Execute AWS operation with full resilience."""
    retry_manager = get_aws_retry_manager()
    return await retry_manager.execute_with_resilience(
        service_name, operation, *args, **kwargs
    )


def create_service_retry_handler(service_name: str) -> AWSRetryHandler:
    """Create a retry handler for a specific service."""
    retry_manager = get_aws_retry_manager()
    return retry_manager.retry_handlers.get(service_name)


def get_service_circuit_breaker(service_name: str) -> Optional[CircuitBreaker]:
    """Get circuit breaker for a specific service."""
    retry_manager = get_aws_retry_manager()
    return retry_manager.circuit_breakers.get(service_name)