"""
Network Module

This module provides network communication capabilities for HappyOS.
"""

from .owl_network import owl_network_client, OwlNetworkError
from .camel_network import camel_network_client, CamelNetworkError

__all__ = [
    'owl_network_client',
    'OwlNetworkError',
    'camel_network_client',
    'CamelNetworkError'
]