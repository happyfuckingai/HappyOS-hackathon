"""
Self-Building Agent Registry

Registers the self-building agent with the HappyOS agent registry.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def register_self_building_agent(agent_registry) -> Dict[str, Any]:
    """
    Register the self-building agent in the HappyOS agent registry.
    
    Args:
        agent_registry: The AgentRegistry instance
        
    Returns:
        Registration result dictionary
    """
    agent_info = {
        "agent_id": "self-building",
        "name": "Self-Building Agent",
        "type": "system",
        "mcp_endpoint": "http://localhost:8004/mcp",
        "capabilities": [
            "autonomous_improvement",
            "code_generation",
            "system_optimization",
            "telemetry_analysis",
            "component_generation"
        ],
        "health_endpoint": "http://localhost:8004/health",
        "version": "1.0.0",
        "status": "active",
        "description": "Autonomous system improvement and code generation agent"
    }
    
    try:
        await agent_registry.register_agent(agent_info)
        logger.info("Self-building agent registered successfully")
        return {"success": True, "agent_info": agent_info}
    except Exception as e:
        logger.error(f"Failed to register self-building agent: {e}")
        return {"success": False, "error": str(e)}
