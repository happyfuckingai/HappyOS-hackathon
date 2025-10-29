"""
HappyOS A2A (Agent-to-Agent) Communication

Unified A2A router and protocol for inter-agent communication
across all domains using the global agent registry.
"""

from .router import A2ARouter, route_message
from .protocol import A2AMessage, A2AMessageType, A2AResponse

__all__ = [
    "A2ARouter",
    "route_message", 
    "A2AMessage",
    "A2AMessageType",
    "A2AResponse"
]