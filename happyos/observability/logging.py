"""
Logging utilities for HappyOS SDK.

Stub implementation for testing purposes.
"""

import logging
from typing import Optional


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Get logger instance."""
    logger = logging.getLogger(name)
    if level:
        logger.setLevel(getattr(logging, level.upper()))
    return logger