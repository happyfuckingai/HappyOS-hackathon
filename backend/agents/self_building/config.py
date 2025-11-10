"""
Self-Building MCP Server Configuration

Configuration settings for the self-building MCP server.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class SelfBuildingConfig(BaseSettings):
    """Configuration for self-building MCP server."""
    
    # Server configuration
    mcp_host: str = Field(default="0.0.0.0", description="MCP server host")
    mcp_port: int = Field(default=8004, description="MCP server port")
    mcp_api_key: Optional[str] = Field(default=None, description="API key for authentication")
    
    # CORS configuration
    allowed_origins: str = Field(default="*", description="Comma-separated allowed origins")
    
    # Improvement cycle configuration
    improvement_cycle_interval_hours: int = Field(
        default=24, 
        description="Hours between autonomous improvement cycles"
    )
    max_concurrent_improvements: int = Field(
        default=3, 
        description="Maximum concurrent improvements to execute"
    )
    improvement_quality_threshold: float = Field(
        default=0.85, 
        description="Minimum quality threshold for improvements"
    )
    improvement_risk_tolerance: float = Field(
        default=0.1, 
        description="Maximum acceptable risk level for improvements"
    )
    monitoring_duration_seconds: int = Field(
        default=3600, 
        description="Duration to monitor improvements before considering stable"
    )
    rollback_degradation_threshold: float = Field(
        default=0.10, 
        description="Performance degradation threshold that triggers rollback"
    )
    
    # CloudWatch configuration
    aws_region: str = Field(default="us-east-1", description="AWS region")
    cloudwatch_namespace: str = Field(
        default="MeetMind/MCPUIHub", 
        description="CloudWatch metrics namespace"
    )
    cloudwatch_metrics_period: int = Field(
        default=300, 
        description="CloudWatch metrics period in seconds"
    )
    cloudwatch_log_group_pattern: str = Field(
        default="/aws/lambda/happyos-*", 
        description="CloudWatch log group pattern"
    )
    
    # Feature flags
    enable_self_building: bool = Field(default=True, description="Enable self-building system")
    enable_cloudwatch_streaming: bool = Field(
        default=True, 
        description="Enable CloudWatch telemetry streaming"
    )
    enable_autonomous_improvements: bool = Field(
        default=False, 
        description="Enable autonomous improvement cycles"
    )
    enable_component_generation: bool = Field(
        default=True, 
        description="Enable component generation"
    )
    enable_improvement_rollback: bool = Field(
        default=True, 
        description="Enable automatic improvement rollback"
    )
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_prefix = "SELF_BUILDING_"
        case_sensitive = False


# Global configuration instance
config = SelfBuildingConfig()


def get_config() -> SelfBuildingConfig:
    """Get the global configuration instance."""
    return config
