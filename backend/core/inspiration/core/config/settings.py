"""
Centralized Configuration Management for HappyOS
Production-ready configuration with environment variable support and validation.
"""
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from functools import lru_cache
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseModel):
    """Configuration for individual services."""

    name: str
    host: str = "0.0.0.0"
    port: int
    command: List[str]
    environment: Dict[str, str] = Field(default_factory=dict, exclude=True)
    health_check_url: Optional[str] = None
    health_check_timeout: int = 30
    startup_timeout: int = 60
    max_retries: int = 3
    restart_delay: float = 5.0
    enabled: bool = True


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
    file_path: Optional[str] = None
    rotation: str = "10 MB"
    retention: str = "30 days"
    compression: str = "zip"
    serialize: bool = False


class MonitoringConfig(BaseSettings):
    """Monitoring and metrics configuration."""

    enabled: bool = True
    metrics_port: int = 9090
    health_check_port: int = 8080
    collect_system_metrics: bool = True
    collect_service_metrics: bool = True
    metrics_interval: int = 30  # seconds


class SecurityConfig(BaseSettings):
    """Security configuration."""

    enable_ssl: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    cors_credentials: bool = True
    cors_methods: List[str] = Field(default_factory=lambda: ["*"])
    cors_headers: List[str] = Field(default_factory=lambda: ["*"])


class HappyOSConfig(BaseSettings):
    """Main HappyOS configuration with environment variable support."""

    # Project paths
    base_path: str = "/home/mr/happyos"
    logs_directory: str = Field(default="logs", env="HAPPYOS_LOGS_DIR")
    data_directory: str = Field(default="data", env="HAPPYOS_DATA_DIR")

    # Service configuration
    chat_agent_service: ServiceConfig = Field(default_factory=lambda: ServiceConfig(
        name="chat_agent",
        port=8000,
        command=["python3", "happyos/app/core/agent/chat_agent_server.py"],
        health_check_url="http://localhost:8000/health"
    ))

    orchestrator_service: ServiceConfig = Field(default_factory=lambda: ServiceConfig(
        name="orchestrator",
        port=8001,
        command=["python3", "-m", "uvicorn", "app.core.orchestrator.orchestrator_agent_server:app", "--host", "0.0.0.0", "--port", "8001"],
        health_check_url="http://localhost:8001/health"
    ))

    mcp_service: ServiceConfig = Field(default_factory=lambda: ServiceConfig(
        name="mcp_server",
        port=8055,
        command=["python3", "-m", "uvicorn", "app.core.mcp_server:app", "--host", "0.0.0.0", "--port", "8055"],
        health_check_url="http://localhost:8055/health"
    ))

    websocket_service: ServiceConfig = Field(default_factory=lambda: ServiceConfig(
        name="websocket_server",
        port=8002,
        command=["python3", "happyos/websocket_server.py"],
        health_check_url=None  # WebSocket servers typically don't have HTTP health checks
    ))

    # System configuration
    max_concurrent_processes: int = Field(default=10, env="HAPPYOS_MAX_PROCESSES")
    process_timeout: int = Field(default=300, env="HAPPYOS_PROCESS_TIMEOUT")  # seconds
    system_check_interval: int = Field(default=60, env="HAPPYOS_CHECK_INTERVAL")  # seconds
    enable_auto_recovery: bool = Field(default=True, env="HAPPYOS_AUTO_RECOVERY")

    # Self-building integration
    self_building_enabled: bool = Field(default=True, env="HAPPYOS_SELF_BUILDING")
    hot_reload_enabled: bool = Field(default=True, env="HAPPYOS_HOT_RELOAD")

    # Component initialization control
    auto_initialize_components: bool = Field(default=False, env="HAPPYOS_AUTO_INIT_COMPONENTS")
    enable_healing_orchestrator: bool = Field(default=False, env="HAPPYOS_ENABLE_HEALING")
    enable_dependency_analyzer: bool = Field(default=False, env="HAPPYOS_ENABLE_DEPENDENCY_ANALYZER")
    enable_graph_visualizer: bool = Field(default=False, env="HAPPYOS_ENABLE_GRAPH_VISUALIZER")
    enable_doc_generator: bool = Field(default=False, env="HAPPYOS_ENABLE_DOC_GENERATOR")
    enable_external_marketplace: bool = Field(default=False, env="HAPPYOS_ENABLE_MARKETPLACE")
    enable_optimization_engine: bool = Field(default=False, env="HAPPYOS_ENABLE_OPTIMIZATION")
    enable_meta_orchestrator: bool = Field(default=False, env="HAPPYOS_ENABLE_META_ORCHESTRATOR")

    # Skill generation control
    auto_skill_generation: bool = Field(default=False, env="HAPPYOS_AUTO_SKILL_GENERATION")
    skill_generation_timeout: int = Field(default=300, env="HAPPYOS_SKILL_GENERATION_TIMEOUT")
    max_skill_generation_attempts: int = Field(default=3, env="HAPPYOS_MAX_SKILL_GENERATION_ATTEMPTS")

    # Healing system control
    auto_healing_enabled: bool = Field(default=False, env="HAPPYOS_AUTO_HEALING")
    healing_timeout: int = Field(default=300, env="HAPPYOS_HEALING_TIMEOUT")
    max_healing_attempts: int = Field(default=3, env="HAPPYOS_MAX_HEALING_ATTEMPTS")
    healing_rollback_enabled: bool = Field(default=False, env="HAPPYOS_HEALING_ROLLBACK")
    healing_regeneration_enabled: bool = Field(default=False, env="HAPPYOS_HEALING_REGENERATION")

    # System automation control
    recursive_improvement_enabled: bool = Field(default=False, env="HAPPYOS_RECURSIVE_IMPROVEMENT")
    periodic_health_checks: bool = Field(default=False, env="HAPPYOS_PERIODIC_HEALTH_CHECKS")
    health_check_interval: int = Field(default=300, env="HAPPYOS_HEALTH_CHECK_INTERVAL")
    system_evolution_tracking: bool = Field(default=False, env="HAPPYOS_SYSTEM_EVOLUTION_TRACKING")

    # Sub-configurations
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # Pydantic configuration
    model_config = SettingsConfigDict(
        env_prefix="HAPPYOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore'
    )

    @field_validator("base_path")
    @classmethod
    def validate_base_path(cls, v):
        """Validate and normalize base path."""
        path = Path(v).resolve()
        if not path.exists():
            raise ValueError(f"Base path does not exist: {path}")
        return str(path)

    @field_validator("logs_directory", "data_directory")
    @classmethod
    def validate_directories(cls, v, info):
        """Validate and create directories if they don't exist."""
        base_path = getattr(info.data, 'base_path', None)
        if not base_path:
            return v

        base_path = Path(base_path)
        full_path = base_path / v

        try:
            full_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(f"Cannot create directory {full_path}: {e}")

        return str(full_path)

    def get_service_configs(self) -> List[ServiceConfig]:
        """Get all enabled service configurations."""
        services = []
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, ServiceConfig) and field_value.enabled:
                services.append(field_value)
        return services

    def get_full_path(self, *path_parts: str) -> str:
        """Get full path relative to base directory."""
        return str(Path(self.base_path).joinpath(*path_parts))


@lru_cache()
def get_config() -> HappyOSConfig:
    """Get cached configuration instance."""
    return HappyOSConfig()


def reload_config() -> HappyOSConfig:
    """Reload configuration from environment."""
    get_config.cache_clear()
    return get_config()


@lru_cache()
def get_settings() -> HappyOSConfig:
    """Get cached configuration instance (alias for get_config for backward compatibility)."""
    return get_config()


# Export configuration
config = get_config()
