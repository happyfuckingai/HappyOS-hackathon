"""
HappyOS Agent Registry

Global agent registry providing single source of truth for all agents
across all domains (Felicia's Finance, Agent Svea, MeetMind).
"""

from .agents import register, build, get_all_agents, REGISTRY

__all__ = [
    "register",
    "build", 
    "get_all_agents",
    "REGISTRY"
]