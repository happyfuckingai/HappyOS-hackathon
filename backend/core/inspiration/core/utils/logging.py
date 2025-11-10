"""
Logging configuration for Happy AI.
This module provides structured logging using Loguru.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get logging configuration from environment variables
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
JSON_LOGS = os.getenv("JSON_LOGS", "0") == "1"
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/happyai.log")
LOG_ROTATION = os.getenv("LOG_ROTATION", "10 MB")
LOG_RETENTION = os.getenv("LOG_RETENTION", "1 week")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Create logs directory if it doesn't exist
log_dir = Path(LOG_FILE_PATH).parent
log_dir.mkdir(parents=True, exist_ok=True)

# Configure Loguru
class InterceptHandler:
    """
    Intercept handler for standard library logging.
    """
    def __init__(self):
        self.logger = logger

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        self.logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def setup_logging():
    """
    Set up logging configuration.
    """
    # Remove default logger
    logger.remove()

    # Add console logger
    logger.add(
        sys.stdout,
        colorize=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message} | {extra}",
        level=LOG_LEVEL,
        serialize=JSON_LOGS,
    )

    # Add file logger
    logger.add(
        LOG_FILE_PATH,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        level=LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message} | {extra}",
        serialize=JSON_LOGS,
        compression="zip",
    )

    # Configure standard library logging to use Loguru
    if JSON_LOGS:
        try:
            import logging
            logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
            for name in logging.root.manager.loggerDict.keys():
                logging.getLogger(name).handlers = []
                logging.getLogger(name).propagate = True
        except ImportError:
            pass

    # Add context to all logs
    return logger.bind(environment=ENVIRONMENT)

# Initialize logger
logger = setup_logging()

def get_logger(name=None):
    """
    Get a logger instance with optional context.
    
    Args:
        name: Optional name for the logger context
        
    Returns:
        Logger: Configured logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger

class RequestLoggingMiddleware:
    """
    Middleware for logging HTTP requests.
    """
    async def __call__(self, request, call_next):
        import uuid
        
        # Start timer
        start_time = datetime.now()
        request_id = str(uuid.uuid4())
        
        # Process request
        try:
            # Add request_id to request state
            request.state.request_id = request_id
            
            # Get client IP
            forwarded_for = request.headers.get("X-Forwarded-For")
            client_ip = forwarded_for.split(",")[0] if forwarded_for else request.client.host
            
            # Log request
            logger.info(
                f"Request started: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                }
            )
            
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path} - Status: {response.status_code}",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration": f"{duration:.3f}s",
                }
            )
            
            # Add request_id to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
        except Exception as e:
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Log exception
            logger.error(
                f"Request failed: {request.method} {request.url.path} - Exception: {str(e)}",
                extra={
                    "request_id": request_id,
                    "duration": f"{duration:.3f}s",
                    "exception": str(e),
                }
            )
            raise