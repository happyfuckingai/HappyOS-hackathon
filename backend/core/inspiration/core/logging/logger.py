"""
Comprehensive Logging System for HappyOS
Production-ready logging with structured logging, rotation, and multiple outputs.
"""
import sys
import json
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger
from loguru._logger import Logger

from app.core.config.settings import get_config


class HappyOSLogger:
    """Centralized logging configuration for HappyOS."""

    def __init__(self):
        self.config = get_config()
        self._configured = False
        self._loggers: Dict[str, Logger] = {}

    def configure(self) -> None:
        """Configure the logging system based on settings."""
        if self._configured:
            return

        # Remove default handler
        logger.remove()

        # Configure console logging
        logger.add(
            sys.stdout,
            level=self.config.logging.level,
            format=self.config.logging.format,
            serialize=self.config.logging.serialize,
            backtrace=True,
            diagnose=True
        )

        # Configure file logging if path is specified
        if self.config.logging.file_path:
            log_file = Path(self.config.logs_directory) / self.config.logging.file_path
            log_file.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                str(log_file),
                level=self.config.logging.level,
                format=self.config.logging.format,
                rotation=self.config.logging.rotation,
                retention=self.config.logging.retention,
                compression=self.config.logging.compression,
                serialize=self.config.logging.serialize,
                backtrace=True,
                diagnose=True
            )

        # Add error file logging
        error_log_file = Path(self.config.logs_directory) / "error.log"
        error_log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            str(error_log_file),
            level="ERROR",
            format=self.config.logging.format,
            rotation=self.config.logging.rotation,
            retention=self.config.logging.retention,
            compression=self.config.logging.compression,
            serialize=self.config.logging.serialize,
            backtrace=True,
            diagnose=True
        )

        self._configured = True
        logger.info("HappyOS logging system configured successfully")

    def get_logger(self, name: str) -> Logger:
        """Get a logger instance for a specific module."""
        if not self._configured:
            self.configure()

        if name not in self._loggers:
            self._loggers[name] = logger.bind(module=name)

        return self._loggers[name]

    def add_service_logger(self, service_name: str, service_config: Any) -> Logger:
        """Create a dedicated logger for a service."""
        service_logger = self.get_logger(f"service.{service_name}")

        # Add service-specific file logging if needed
        service_log_file = Path(self.config.logs_directory) / f"services/{service_name}.log"
        service_log_file.parent.mkdir(parents=True, exist_ok=True)

        service_logger.add(
            str(service_log_file),
            level=self.config.logging.level,
            format=self.config.logging.format,
            rotation=self.config.logging.rotation,
            retention=self.config.logging.retention,
            compression=self.config.logging.compression,
            serialize=self.config.logging.serialize,
            backtrace=True,
            diagnose=True,
            filter=lambda record: record["extra"].get("service") == service_name
        )

        return service_logger.bind(service=service_name)

    def log_startup_event(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log system startup events."""
        logger.bind(event_type="startup").info(f"System startup: {event}", **(details or {}))

    def log_shutdown_event(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log system shutdown events."""
        logger.bind(event_type="shutdown").info(f"System shutdown: {event}", **(details or {}))

    def log_service_event(self, service_name: str, event: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log service-specific events."""
        service_logger = self.get_logger(f"service.{service_name}")
        service_logger.bind(
            event_type="service_event",
            service=service_name,
            event=event,
            status=status
        ).info(f"Service {service_name}: {event} - {status}", **(details or {}))

    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Log errors with context."""
        logger.bind(
            event_type="error",
            error_type=type(error).__name__,
            error_message=str(error)
        ).error("Error occurred", error=error, **(context or {}))

    def log_performance_metric(self, metric_name: str, value: Any, unit: str = "", details: Optional[Dict[str, Any]] = None) -> None:
        """Log performance metrics."""
        logger.bind(
            event_type="performance",
            metric=metric_name,
            value=value,
            unit=unit
        ).info(f"Performance metric: {metric_name} = {value} {unit}", **(details or {}))


# Global logger instance
_logger_instance: Optional[HappyOSLogger] = None


def get_logger(name: str = "happyos") -> Logger:
    """Get the global HappyOS logger instance."""
    global _logger_instance

    if _logger_instance is None:
        _logger_instance = HappyOSLogger()
        _logger_instance.configure()

    return _logger_instance.get_logger(name)


def configure_logging() -> None:
    """Configure the global logging system."""
    global _logger_instance

    if _logger_instance is None:
        _logger_instance = HappyOSLogger()

    _logger_instance.configure()


def reload_logging() -> None:
    """Reload logging configuration."""
    global _logger_instance

    if _logger_instance:
        _logger_instance._configured = False
        _logger_instance.configure()


# Export convenience functions
def log_service_event(service_name: str, event: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Convenience function to log service events."""
    global _logger_instance

    if _logger_instance is None:
        configure_logging()
        _logger_instance = HappyOSLogger()

    _logger_instance.log_service_event(service_name, event, status, details)


def log_startup_event(event: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Convenience function to log startup events."""
    global _logger_instance

    if _logger_instance is None:
        configure_logging()
        _logger_instance = HappyOSLogger()

    _logger_instance.log_startup_event(event, details)


def log_shutdown_event(event: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Convenience function to log shutdown events."""
    global _logger_instance

    if _logger_instance is None:
        configure_logging()
        _logger_instance = HappyOSLogger()

    _logger_instance.log_shutdown_event(event, details)