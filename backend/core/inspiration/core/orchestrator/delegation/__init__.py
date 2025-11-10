"""Agent delegation module."""

# Import adapter first to ensure monkey patching happens before delegator is used
from .agent_adapter import get_available_agents, get_all_agents, execute_task
from .agent_delegator import agent_delegator, DelegationResult

__all__ = ["agent_delegator", "DelegationResult", "get_available_agents", "get_all_agents", "execute_task"]