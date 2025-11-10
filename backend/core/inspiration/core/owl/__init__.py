"""
Owl Integration Package

This package provides integration with the Owl multi-agent runtime framework,
enabling HappyOS to leverage CAMEL agents for advanced tasks like code generation,
multi-agent collaboration, and complex workflows.
"""

from .owl_client import OwlClient, OwlResponse
from .owl_helpers import should_use_owl_for_skill, sanitize_input
from .owl_config import get_owl_config

__all__ = [
    'OwlClient',
    'OwlResponse',
    'should_use_owl_for_skill',
    'sanitize_input',
    'get_owl_config'
]