"""
HappyOS SDK Configuration Management

Provides centralized configuration for the SDK with environment-specific
settings and validation.
"""

import os
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from .exceptions import HappyOSSDKError


class Environment(Enum):
    """Supported deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


@dataclass
class SDKConfig:
    """Main HappyOS SDK configuration.
    
    Provides centralized configuration management with environment-specific
    settings and validation.
    """
    
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    
    # MCP Configuration
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8080
    mcp_timeout: int = 30
    
    # Security
    enable_mcp_signing: bool = True
    mcp_signing_key: Optional[str] = None
    
    # Observability
    log_level: str = "INFO"
    enable_metrics: bool = True
    enable_tracing: bool = True
    
    # AWS
    aws_region: str = "us-east-1"
    aws_profile: Optional[str] = None
    
    # Custom settings
    custom: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_environment(cls, env: str = None) -> "SDKConfig":
        """Create configuration from environment variables.
        
        Args:
            env: Environment name (development, staging, production, test)
            
        Returns:
            Configured SDKConfig instance
        """
        if env is None:
            env = os.getenv("HAPPYOS_ENV", "development")
        
        try:
            environment = Environment(env.lower())
        except ValueError:
            raise HappyOSSDKError(f"Invalid environment: {env}")
        
        config = cls(environment=environment)
        config._load_from_env_vars()
        config._apply_environment_defaults()
        
        return config
    
    def _load_from_env_vars(self) -> None:
        """Load configuration from environment variables."""
        # MCP settings
        if mcp_host := os.getenv("HAPPYOS_MCP_HOST"):
            self.mcp_server_host = mcp_host
        
        if mcp_port := os.getenv("HAPPYOS_MCP_PORT"):
            try:
                self.mcp_server_port = int(mcp_port)
            except ValueError:
                raise HappyOSSDKError(f"Invalid MCP port: {mcp_port}")
        
        # Security
        if signing_key := os.getenv("HAPPYOS_MCP_SIGNING_KEY"):
            self.mcp_signing_key = signing_key
        
        # Observability
        if log_level := os.getenv("HAPPYOS_LOG_LEVEL"):
            self.log_level = log_level.upper()
        
        # AWS
        if region := os.getenv("AWS_REGION"):
            self.aws_region = region
        
        if profile := os.getenv("AWS_PROFILE"):
            self.aws_profile = profile
    
    def _apply_environment_defaults(self) -> None:
        """Apply environment-specific defaults."""
        if self.environment == Environment.PRODUCTION:
            self.debug = False
            self.log_level = "INFO"
            self.enable_mcp_signing = True
        
        elif self.environment == Environment.DEVELOPMENT:
            self.debug = True
            self.log_level = "DEBUG"
            self.enable_mcp_signing = False  # Easier development
        
        elif self.environment == Environment.TEST:
            self.debug = True
            self.log_level = "WARNING"
            self.enable_metrics = False
            self.enable_tracing = False
    
    def validate(self) -> None:
        """Validate the configuration.
        
        Raises:
            HappyOSSDKError: If configuration is invalid
        """
        if self.environment == Environment.PRODUCTION:
            if self.enable_mcp_signing and not self.mcp_signing_key:
                raise HappyOSSDKError("MCP signing key required in production")
        
        if not (1024 <= self.mcp_server_port <= 65535):
            raise HappyOSSDKError(
                f"MCP port must be between 1024-65535, got {self.mcp_server_port}"
            )