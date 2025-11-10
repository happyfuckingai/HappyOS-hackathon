"""
Owl Configuration Module

This module handles configuration for the Owl integration, including
loading settings from environment variables and providing defaults.
"""

import os
import logging
from typing import Dict, Any
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

def get_owl_config() -> Dict[str, Any]:
    """
    Get configuration for Owl integration.
    
    Loads configuration from environment variables with sensible defaults.
    
    Returns:
        Dictionary containing Owl configuration
    """
    settings = get_settings()
    
    # Default configuration
    default_config = {
        "api_url": "http://localhost:8000",
        "timeout_seconds": 120,
        "max_retries": 3,
        "use_local_owl": True,
        "default_agent": "camel_chat",
        "complexity_threshold": 0.7,  # Threshold for determining when to use Owl
        "length_threshold": 50,       # Minimum request length to consider Owl
    }
    
    # Override with environment variables if available
    config = {
        "api_url": os.getenv("OWL_API_URL", default_config["api_url"]),
        "timeout_seconds": int(os.getenv("OWL_TIMEOUT_SECONDS", default_config["timeout_seconds"])),
        "max_retries": int(os.getenv("OWL_MAX_RETRIES", default_config["max_retries"])),
        "use_local_owl": os.getenv("OWL_USE_LOCAL", str(default_config["use_local_owl"])).lower() == "true",
        "default_agent": os.getenv("OWL_DEFAULT_AGENT", default_config["default_agent"]),
        "complexity_threshold": float(os.getenv("OWL_COMPLEXITY_THRESHOLD", default_config["complexity_threshold"])),
        "length_threshold": int(os.getenv("OWL_LENGTH_THRESHOLD", default_config["length_threshold"])),
    }
    
    # Add any additional configuration from settings if available
    if hasattr(settings, "owl") and settings.owl:
        config.update(settings.owl)
    
    logger.debug(f"Loaded Owl configuration: {config}")
    return config