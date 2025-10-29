"""
A2A Protocol Core - Secure Agent-to-Agent Communication Framework

This module implements the core components of the A2A Protocol for HappyOS,
providing secure, scalable, and intelligent communication between autonomous agents.
"""

from .constants import *
from .identity import IdentityManager
from .auth import AuthenticationManager
from .messaging import MessageManager
from .transport import TransportLayer
from .discovery import DiscoveryService
from .agent import A2AAgent
from .client import A2AClient
from .orchestrator import A2AProtocolManager

__version__ = "1.0.0"
__all__ = [
    'IdentityManager',
    'AuthenticationManager',
    'MessageManager',
    'TransportLayer',
    'DiscoveryService',
    'A2AAgent',
    'A2AClient',
    'A2AOrchestrator'
]