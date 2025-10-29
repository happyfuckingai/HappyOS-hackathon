"""
Configuration for observability components.
"""

from typing import Optional
from pydantic import BaseModel, Field

try:
    from backend.modules.config.settings import settings
except ImportError:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from backend.modules.config.settings import settings


class CloudWatchConfig(BaseModel):
    """CloudWatch monitoring configuration."""
    
    enabled: bool = Field(default=True, description="Enable CloudWatch monitoring")
    namespace: str = Field(default="MeetMind/MCPUIHub", description="CloudWatch namespace")
    region: str = Field(default="us-east-1", description="AWS region")
    buffer_size: int = Field(default=20, description="Metric buffer size")
    flush_interval_seconds: int = Field(default=60, description="Buffer flush interval")
    
    # Dashboard settings
    create_tenant_dashboards: bool = Field(default=True, description="Auto-create tenant dashboards")
    dashboard_refresh_minutes: int = Field(default=5, description="Dashboard refresh interval")
    
    # Alert settings
    create_system_alerts: bool = Field(default=True, description="Auto-create system alerts")
    error_rate_threshold: float = Field(default=10.0, description="Error rate alarm threshold")
    latency_threshold_ms: float = Field(default=1000.0, description="Latency alarm threshold")
    low_activity_threshold: float = Field(default=1.0, description="Low activity alarm threshold")


class XRayConfig(BaseModel):
    """X-Ray tracing configuration."""
    
    enabled: bool = Field(default=True, description="Enable X-Ray tracing")
    daemon_address: str = Field(default="127.0.0.1:2000", description="X-Ray daemon address")
    service_name: str = Field(default="meetmind-mcp-ui-hub", description="Service name for tracing")
    sampling_rate: float = Field(default=0.1, description="Trace sampling rate")
    
    # Context settings
    use_correlation_ids: bool = Field(default=True, description="Generate correlation IDs")
    trace_http_requests: bool = Field(default=True, description="Trace HTTP requests")
    trace_database_operations: bool = Field(default=True, description="Trace database operations")
    trace_mcp_operations: bool = Field(default=True, description="Trace MCP operations")
    
    # Performance settings
    max_subsegments: int = Field(default=100, description="Maximum subsegments per trace")
    segment_timeout_seconds: int = Field(default=30, description="Segment timeout")


class AuditLogConfig(BaseModel):
    """Audit logging configuration."""
    
    enabled: bool = Field(default=True, description="Enable audit logging")
    buffer_size: int = Field(default=100, description="Audit log buffer size")
    flush_interval_seconds: int = Field(default=30, description="Buffer flush interval")
    
    # Local file settings
    local_file_enabled: bool = Field(default=True, description="Enable local file logging")
    local_file_path: str = Field(default="logs/audit.jsonl", description="Local audit log file path")
    local_file_max_size_mb: int = Field(default=100, description="Max local file size in MB")
    local_file_backup_count: int = Field(default=5, description="Number of backup files to keep")
    
    # S3 settings
    s3_enabled: bool = Field(default=True, description="Enable S3 audit logging")
    s3_bucket: Optional[str] = Field(default=None, description="S3 bucket for audit logs")
    s3_prefix: str = Field(default="audit-logs", description="S3 key prefix")
    s3_compression: bool = Field(default=True, description="Compress S3 audit logs")
    
    # CloudWatch Logs settings
    cloudwatch_logs_enabled: bool = Field(default=True, description="Enable CloudWatch Logs")
    cloudwatch_log_group: str = Field(default="/meetmind/audit-logs", description="CloudWatch log group")
    cloudwatch_retention_days: int = Field(default=30, description="Log retention in days")
    
    # Event filtering
    log_resource_operations: bool = Field(default=True, description="Log resource operations")
    log_authentication_events: bool = Field(default=True, description="Log authentication events")
    log_security_events: bool = Field(default=True, description="Log security events")
    log_system_events: bool = Field(default=False, description="Log system events")
    
    # Sensitive data handling
    mask_sensitive_data: bool = Field(default=True, description="Mask sensitive data in logs")
    sensitive_fields: list = Field(
        default=["password", "token", "key", "secret"],
        description="Fields to mask in audit logs"
    )


class ObservabilityConfig(BaseModel):
    """Main observability configuration."""
    
    enabled: bool = Field(default=True, description="Enable observability system")
    environment: str = Field(default="development", description="Environment name")
    
    # Component configurations
    cloudwatch: CloudWatchConfig = Field(default_factory=CloudWatchConfig)
    xray: XRayConfig = Field(default_factory=XRayConfig)
    audit_logging: AuditLogConfig = Field(default_factory=AuditLogConfig)
    
    # Integration settings
    middleware_enabled: bool = Field(default=True, description="Enable observability middleware")
    auto_flush_on_shutdown: bool = Field(default=True, description="Auto-flush buffers on shutdown")
    health_check_interval_seconds: int = Field(default=300, description="Health check interval")
    
    # Performance settings
    async_processing: bool = Field(default=True, description="Use async processing for observability")
    max_concurrent_operations: int = Field(default=10, description="Max concurrent observability operations")
    operation_timeout_seconds: int = Field(default=30, description="Operation timeout")
    
    @classmethod
    def from_settings(cls) -> "ObservabilityConfig":
        """Create configuration from application settings."""
        config = cls()
        
        # Override with environment-specific settings
        if hasattr(settings, 'ENVIRONMENT'):
            config.environment = settings.ENVIRONMENT
        
        # CloudWatch settings
        if hasattr(settings, 'AWS_REGION'):
            config.cloudwatch.region = settings.AWS_REGION
        
        if hasattr(settings, 'CLOUDWATCH_NAMESPACE'):
            config.cloudwatch.namespace = settings.CLOUDWATCH_NAMESPACE
        
        # X-Ray settings
        if hasattr(settings, 'XRAY_DAEMON_ADDRESS'):
            config.xray.daemon_address = settings.XRAY_DAEMON_ADDRESS
        
        if hasattr(settings, 'XRAY_SAMPLING_RATE'):
            config.xray.sampling_rate = settings.XRAY_SAMPLING_RATE
        
        # Audit logging settings
        if hasattr(settings, 'AUDIT_LOG_S3_BUCKET'):
            config.audit_logging.s3_bucket = settings.AUDIT_LOG_S3_BUCKET
        
        # Disable components in development if needed
        if config.environment == "development":
            config.cloudwatch.create_system_alerts = False
            config.xray.sampling_rate = 1.0  # Full sampling in dev
        
        # Disable components in production if AWS not available
        if config.environment == "production":
            # These would be set based on actual AWS availability
            pass
        
        return config


# Global configuration instance
_observability_config: Optional[ObservabilityConfig] = None


def get_observability_config() -> ObservabilityConfig:
    """Get or create the global observability configuration."""
    global _observability_config
    if _observability_config is None:
        _observability_config = ObservabilityConfig.from_settings()
    return _observability_config