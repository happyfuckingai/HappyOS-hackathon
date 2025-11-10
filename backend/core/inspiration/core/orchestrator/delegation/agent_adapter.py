"""
Agent adapter module.
Provides compatibility layer for legacy code while using new AgentDelegator.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .agent_delegator import agent_delegator, AgentType

logger = logging.getLogger(__name__)

# Legacy compatibility functions - map to new AgentDelegator
async def get_available_agents() -> List[str]:
    """
    Get available agent types (legacy compatibility).
    """
    try:
        return [agent_type.value for agent_type in AgentType]
    except Exception as e:
        logger.error(f"Error getting available agents: {e}")
        return []

async def get_all_agents() -> Dict[str, Any]:
    """
    Get information about active dynamic agents.
    """
    try:
        return agent_delegator.get_active_agents_info()
    except Exception as e:
        logger.error(f"Error getting all agents: {e}")
        return {}

async def execute_task(task) -> Dict[str, Any]:
    """
    Execute task using new AgentDelegator.

    Args:
        task: Task object (legacy) or dict with description/context

    Returns:
        Task execution result
    """
    try:
        # Handle both legacy Task objects and dicts
        if hasattr(task, 'description'):
            user_request = task.description
            context = getattr(task, 'context', {})
            # Map legacy agent name to AgentType
            agent_name = getattr(task, 'assigned_agent', 'general')
            agent_type = _map_legacy_agent_name_to_type(agent_name)
        else:
            # Assume it's a dict
            user_request = task.get('description', '')
            context = task.get('context', {})
            agent_name = task.get('assigned_agent', 'general')
            agent_type = _map_legacy_agent_name_to_type(agent_name)

        # Delegate to new AgentDelegator
        result = await agent_delegator.delegate_to_agent(
            agent_type=agent_type,
            request=user_request,
            context=context
        )

        # Convert to legacy format for compatibility
        return {
            "success": result.success,
            "result": result.response,
            "error": result.error,
            "execution_time": result.execution_time,
            "agent_used": result.agent_name
        }

    except Exception as e:
        logger.error(f"Error executing task: {e}")
        return {"success": False, "error": str(e)}

def _map_legacy_agent_name_to_type(agent_name: str) -> AgentType:
    """Map legacy agent names to new AgentType enum."""
    name_lower = agent_name.lower()

    mapping = {
        'accounting': AgentType.ACCOUNTING,
        'research': AgentType.RESEARCH,
        'writing': AgentType.WRITING,
        'coding': AgentType.CODING,
        'analysis': AgentType.ANALYSIS,
        'camel': AgentType.TEAM_LEAD,
        'general': AgentType.GENERAL
    }

    return mapping.get(name_lower, AgentType.GENERAL)

# Legacy compatibility - create mock agent_orchestrator object
class MockAgentOrchestrator:
    """Mock object for legacy compatibility."""

    def __init__(self):
        self.agents = {}  # Empty dict for legacy code

    async def get_available_agents(self):
        return await get_available_agents()

    async def get_all_agents(self):
        return await get_all_agents()

    async def execute_task(self, task):
        return await execute_task(task)

# Create global mock instance for legacy compatibility
mock_agent_orchestrator = MockAgentOrchestrator()

# Export for legacy compatibility
__all__ = ['mock_agent_orchestrator', 'get_available_agents', 'get_all_agents', 'execute_task']