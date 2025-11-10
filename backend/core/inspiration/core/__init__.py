"""
HappyOS Core Package
====================

This package contains the core components of the HappyOS system including:

- Configuration management with environment-based settings
- Comprehensive logging with structured logging and rotation
- Service management with health checks and auto-recovery
- Monitoring and metrics collection
- Error handling and recovery mechanisms
- Production-ready main application entry point

Main Components:
    - config: Configuration management system
    - logging: Structured logging system
    - service_manager: Async service management
    - monitoring: Health checks and metrics
    - error_handling: Robust error handling and recovery

Usage:
    from app.core.config.settings import get_config
    from app.core.logging.logger import get_logger
    from app.core.service_manager.service_manager import ServiceManager

Author: HappyOS Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "HappyOS Team"

# Export main components for easy importing
from .config.settings import get_config, reload_config, HappyOSConfig
from .logging.logger import get_logger, configure_logging, log_service_event
from .service_manager.service_manager import ServiceManager
from .monitoring.monitor import MonitoringServer, HealthChecker, MetricsCollector
from .error_handling.error_handler import (
    ErrorHandler, get_error_handler, handle_errors,
    error_boundary, ErrorSeverity, RecoveryAction
)

__all__ = [
    # Configuration
    "get_config",
    "reload_config",
    "HappyOSConfig",

    # Logging
    "get_logger",
    "configure_logging",
    "log_service_event",

    # Service Management
    "ServiceManager",

    # Monitoring
    "MonitoringServer",
    "HealthChecker",
    "MetricsCollector",

    # Error Handling
    "ErrorHandler",
    "get_error_handler",
    "handle_errors",
    "error_boundary",
    "ErrorSeverity",
    "RecoveryAction",
]