"""
HappyOS SDK Configuration Management

Environment-aware configuration system for enterprise deployments.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
import os


class Environment(Enum):
    """Deployment environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


@dataclass
class SecurityConfig:
    """Security configuration."""
    enable_tenant_isolation: bool = True
    jwt_secret: Optional[str] = None
    saml_config: Optional[Dict[str, Any]] = None
    oidc_config: Optional[Dict[str, Any]] = None
    message_signing_enabled: bool = True


@dataclass
class ObservabilityConfig:
    """Observability configuration."""
    enable_logging: bool = True
    enable_metrics: bool = True
    enable_tracing: bool = True
    log_level: str = "INFO"
    metrics_endpoint: Optional[str] = None
    tracing_endpoint: Optional[str] = None


@dataclass
class ResilienceConfig:
    """Resilience configuration."""
    enable_circuit_breaker: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    retry_attempts: int = 3
    retry_backoff: str = "exponential"


@dataclass
class ServiceConfig:
    """Service configuration."""
    aws_region: str = "us-east-1"
    enable_local_fallback: bool = True
    service_timeout: int = 30


@dataclass
class SDKConfig:
    """Root SDK configuration."""
    environment: Environment
    security: SecurityConfig
    observability: ObservabilityConfig
    resilience: ResilienceConfig
    services: ServiceConfig
    
    @classmethod
    def from_environment(cls, env: Optional[Environment] = None) -> 'SDKConfig':
        """Load configuration from environment variables."""
        if env is None:
            env_str = os.getenv("HAPPYOS_ENVIRONMENT", "development")
            env = Environment(env_str)
        
        return cls(
            environment=env,
            security=SecurityConfig(
                enable_tenant_isolation=os.getenv("HAPPYOS_TENANT_ISOLATION", "true").lower() == "true",
                jwt_secret=os.getenv("HAPPYOS_JWT_SECRET"),
                message_signing_enabled=os.getenv("HAPPYOS_MESSAGE_SIGNING", "true").lower() == "true",
            ),
            observability=ObservabilityConfig(
                enable_logging=os.getenv("HAPPYOS_LOGGING", "true").lower() == "true",
                enable_metrics=os.getenv("HAPPYOS_METRICS", "true").lower() == "true",
                enable_tracing=os.getenv("HAPPYOS_TRACING", "true").lower() == "true",
                log_level=os.getenv("HAPPYOS_LOG_LEVEL", "INFO"),
                metrics_endpoint=os.getenv("HAPPYOS_METRICS_ENDPOINT"),
                tracing_endpoint=os.getenv("HAPPYOS_TRACING_ENDPOINT"),
            ),
            resilience=ResilienceConfig(
                enable_circuit_breaker=os.getenv("HAPPYOS_CIRCUIT_BREAKER", "true").lower() == "true",
                circuit_breaker_threshold=int(os.getenv("HAPPYOS_CB_THRESHOLD", "5")),
                circuit_breaker_timeout=int(os.getenv("HAPPYOS_CB_TIMEOUT", "60")),
                retry_attempts=int(os.getenv("HAPPYOS_RETRY_ATTEMPTS", "3")),
                retry_backoff=os.getenv("HAPPYOS_RETRY_BACKOFF", "exponential"),
            ),
            services=ServiceConfig(
                aws_region=os.getenv("AWS_REGION", "us-east-1"),
                enable_local_fallback=os.getenv("HAPPYOS_LOCAL_FALLBACK", "true").lower() == "true",
                service_timeout=int(os.getenv("HAPPYOS_SERVICE_TIMEOUT", "30")),
            ),
        )