"""
Configuration management system for the infrastructure recovery platform.
Supports environment-specific settings, tenant configurations, and feature flags.
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


class Environment(Enum):
    """Environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ServiceMode(Enum):
    """Service operation modes."""
    AWS_ONLY = "aws_only"
    LOCAL_ONLY = "local_only"
    HYBRID = "hybrid"
    AUTO = "auto"


@dataclass
class AWSConfig:
    """AWS service configuration."""
    region: str = "us-east-1"
    profile: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    
    # Service-specific configurations
    opensearch_endpoint: Optional[str] = None
    lambda_function_prefix: str = "meetmind"
    api_gateway_stage: str = "prod"
    elasticache_cluster: Optional[str] = None
    s3_bucket_prefix: str = "meetmind"
    secrets_manager_prefix: str = "meetmind"
    
    # Resource limits
    lambda_timeout: int = 300
    lambda_memory: int = 512
    opensearch_instance_type: str = "t3.small.search"
    elasticache_node_type: str = "cache.t3.micro"


@dataclass
class LocalConfig:
    """Local fallback service configuration."""
    data_directory: str = "./data"
    cache_directory: str = "./cache"
    logs_directory: str = "./logs"
    
    # Service ports
    search_port: int = 9200
    cache_port: int = 6379
    job_runner_port: int = 8080
    
    # Resource limits
    max_memory_mb: int = 1024
    max_disk_gb: int = 10
    max_concurrent_jobs: int = 10
    
    # Search configuration
    search_index_shards: int = 1
    search_index_replicas: int = 0
    vector_dimensions: int = 1536


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    timeout_seconds: int = 60
    half_open_max_calls: int = 3
    health_check_interval: int = 30
    
    # Service-specific thresholds
    service_thresholds: Dict[str, int] = field(default_factory=lambda: {
        "agent_core": 3,
        "opensearch": 5,
        "lambda": 3,
        "elasticache": 2,
        "s3": 5
    })


@dataclass
class SecurityConfig:
    """Security configuration."""
    encryption_key_size: int = 2048
    token_expiry_hours: int = 24
    max_login_attempts: int = 5
    password_min_length: int = 8
    
    # A2A Protocol security
    message_encryption_algorithm: str = "RSA-OAEP"
    signature_algorithm: str = "RSA-PSS"
    key_rotation_days: int = 90
    
    # CORS settings
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:3000"])
    cors_methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])


@dataclass
class ObservabilityConfig:
    """Observability and monitoring configuration."""
    enable_metrics: bool = True
    enable_tracing: bool = True
    enable_logging: bool = True
    
    # Metrics configuration
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    
    # Tracing configuration
    jaeger_endpoint: Optional[str] = None
    trace_sample_rate: float = 0.1
    
    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: Optional[str] = None


@dataclass
class TenantConfig:
    """Individual tenant configuration."""
    tenant_id: str
    domain: str
    agents: List[str]
    resources: Dict[str, str]
    settings: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class FeatureFlags:
    """Feature flag configuration."""
    enable_a2a_protocol: bool = True
    enable_circuit_breaker: bool = True
    enable_local_fallback: bool = True
    enable_multi_tenant: bool = True
    enable_observability: bool = True
    enable_auto_scaling: bool = False
    enable_cost_optimization: bool = False
    
    # Experimental features
    enable_ml_optimization: bool = False
    enable_predictive_scaling: bool = False


class Settings:
    """Main configuration class that loads and manages all settings."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.environment = Environment(os.getenv("ENVIRONMENT", "development"))
        self.service_mode = ServiceMode(os.getenv("SERVICE_MODE", "auto"))
        
        # Load configurations
        self.aws = self._load_aws_config()
        self.local = self._load_local_config()
        self.circuit_breaker = self._load_circuit_breaker_config()
        self.security = self._load_security_config()
        self.observability = self._load_observability_config()
        self.feature_flags = self._load_feature_flags()
        
        # Load tenant configurations
        self.tenants = self._load_tenant_configs()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration path."""
        return os.path.join(os.path.dirname(__file__), "..", "config")
    
    def _load_aws_config(self) -> AWSConfig:
        """Load AWS configuration from environment and config files."""
        config = AWSConfig()
        
        # Override with environment variables
        config.region = os.getenv("AWS_REGION", config.region)
        config.profile = os.getenv("AWS_PROFILE")
        config.access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        config.secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        config.session_token = os.getenv("AWS_SESSION_TOKEN")
        
        # Service endpoints
        config.opensearch_endpoint = os.getenv("OPENSEARCH_ENDPOINT")
        config.elasticache_cluster = os.getenv("ELASTICACHE_CLUSTER")
        
        # Load from config file if exists
        config_file = os.path.join(self.config_path, "aws.yaml")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f)
                for key, value in file_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        
        return config
    
    def _load_local_config(self) -> LocalConfig:
        """Load local fallback configuration."""
        config = LocalConfig()
        
        # Override with environment variables
        config.data_directory = os.getenv("LOCAL_DATA_DIR", config.data_directory)
        config.cache_directory = os.getenv("LOCAL_CACHE_DIR", config.cache_directory)
        config.logs_directory = os.getenv("LOCAL_LOGS_DIR", config.logs_directory)
        
        # Load from config file if exists
        config_file = os.path.join(self.config_path, "local.yaml")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f)
                for key, value in file_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        
        return config
    
    def _load_circuit_breaker_config(self) -> CircuitBreakerConfig:
        """Load circuit breaker configuration."""
        config = CircuitBreakerConfig()
        
        # Override with environment variables
        config.failure_threshold = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", config.failure_threshold))
        config.timeout_seconds = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", config.timeout_seconds))
        
        # Load from config file if exists
        config_file = os.path.join(self.config_path, "circuit_breaker.yaml")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f)
                for key, value in file_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        
        return config
    
    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration."""
        config = SecurityConfig()
        
        # Override with environment variables
        config.token_expiry_hours = int(os.getenv("TOKEN_EXPIRY_HOURS", config.token_expiry_hours))
        config.password_min_length = int(os.getenv("PASSWORD_MIN_LENGTH", config.password_min_length))
        
        # CORS settings
        cors_origins = os.getenv("CORS_ORIGINS")
        if cors_origins:
            config.cors_origins = cors_origins.split(",")
        
        # Load from config file if exists
        config_file = os.path.join(self.config_path, "security.yaml")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f)
                for key, value in file_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        
        return config
    
    def _load_observability_config(self) -> ObservabilityConfig:
        """Load observability configuration."""
        config = ObservabilityConfig()
        
        # Override with environment variables
        config.enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        config.enable_tracing = os.getenv("ENABLE_TRACING", "true").lower() == "true"
        config.enable_logging = os.getenv("ENABLE_LOGGING", "true").lower() == "true"
        config.log_level = os.getenv("LOG_LEVEL", config.log_level)
        config.jaeger_endpoint = os.getenv("JAEGER_ENDPOINT")
        
        # Load from config file if exists
        config_file = os.path.join(self.config_path, "observability.yaml")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f)
                for key, value in file_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        
        return config
    
    def _load_feature_flags(self) -> FeatureFlags:
        """Load feature flag configuration."""
        config = FeatureFlags()
        
        # Override with environment variables
        config.enable_a2a_protocol = os.getenv("ENABLE_A2A_PROTOCOL", "true").lower() == "true"
        config.enable_circuit_breaker = os.getenv("ENABLE_CIRCUIT_BREAKER", "true").lower() == "true"
        config.enable_local_fallback = os.getenv("ENABLE_LOCAL_FALLBACK", "true").lower() == "true"
        config.enable_multi_tenant = os.getenv("ENABLE_MULTI_TENANT", "true").lower() == "true"
        config.enable_observability = os.getenv("ENABLE_OBSERVABILITY", "true").lower() == "true"
        config.enable_auto_scaling = os.getenv("ENABLE_AUTO_SCALING", "false").lower() == "true"
        config.enable_cost_optimization = os.getenv("ENABLE_COST_OPTIMIZATION", "false").lower() == "true"
        
        # Load from config file if exists
        config_file = os.path.join(self.config_path, "features.yaml")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f)
                for key, value in file_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        
        return config
    
    def _load_tenant_configs(self) -> Dict[str, TenantConfig]:
        """Load tenant configurations."""
        tenants = {}
        
        # Load from tenants.yaml file
        config_file = os.path.join(self.config_path, "tenants.yaml")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                tenant_data = yaml.safe_load(f)
                
                if "tenants" in tenant_data:
                    for tenant_id, config_data in tenant_data["tenants"].items():
                        tenant_config = TenantConfig(
                            tenant_id=tenant_id,
                            domain=config_data.get("domain", ""),
                            agents=config_data.get("agents", []),
                            resources=config_data.get("resources", {}),
                            settings=config_data.get("settings", {}),
                            enabled=config_data.get("enabled", True)
                        )
                        tenants[tenant_id] = tenant_config
        
        return tenants
    
    def get_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get configuration for a specific tenant."""
        return self.tenants.get(tenant_id)
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature flag is enabled."""
        return getattr(self.feature_flags, feature_name, False)
    
    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """Get configuration for a specific service."""
        service_configs = {
            "aws": self.aws.__dict__,
            "local": self.local.__dict__,
            "circuit_breaker": self.circuit_breaker.__dict__,
            "security": self.security.__dict__,
            "observability": self.observability.__dict__
        }
        return service_configs.get(service_name, {})
    
    def reload_config(self):
        """Reload all configurations from files."""
        self.__init__(self.config_path)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


def reload_settings():
    """Reload the global settings."""
    global settings
    settings.reload_config()