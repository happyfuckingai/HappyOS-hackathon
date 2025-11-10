"""
CAMEL Agent Factory Module

This module provides factory functions for creating and managing CAMEL agents.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Union, Tuple
import json
import os
from pathlib import Path

from app.core.camel.camel_config import AgentRole, camel_config
from app.core.camel.camel_client import camel_client, CamelResponse

logger = logging.getLogger(__name__)

# Cache for agent instances
_agent_cache: Dict[str, Dict[str, Any]] = {}

async def create_agent(
    role: Union[AgentRole, str],
    name: Optional[str] = None,
    system_message: Optional[str] = None,
    capabilities: Optional[List[str]] = None,
    constraints: Optional[List[str]] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    custom_parameters: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create a new CAMEL agent.
    
    Args:
        role: Agent role
        name: Agent name
        system_message: System message for the agent
        capabilities: List of agent capabilities
        constraints: List of agent constraints
        model: LLM model to use
        temperature: Temperature for generation
        max_tokens: Maximum tokens for generation
        custom_parameters: Additional parameters
        
    Returns:
        Tuple of (success, agent_data)
    """
    # Convert role to string if it's an enum
    if isinstance(role, AgentRole):
        role_str = role.value
    else:
        role_str = role
    
    # Get agent configuration if available
    agent_config = camel_config.agent_configs.get(
        AgentRole(role_str) if role_str in [e.value for e in AgentRole] else AgentRole.CUSTOM,
        None
    )
    
    # Build system message if not provided
    if not system_message and agent_config:
        system_message = agent_config.system_message
    
    if not system_message:
        # Build a default system message based on role, capabilities, and constraints
        system_message = f"You are a {role_str} agent."
        
        if capabilities:
            system_message += "\n\nCapabilities:\n" + "\n".join([f"- {cap}" for cap in capabilities])
        elif agent_config and agent_config.capabilities:
            system_message += "\n\nCapabilities:\n" + "\n".join([f"- {cap}" for cap in agent_config.capabilities])
        
        if constraints:
            system_message += "\n\nConstraints:\n" + "\n".join([f"- {con}" for con in constraints])
        elif agent_config and agent_config.constraints:
            system_message += "\n\nConstraints:\n" + "\n".join([f"- {con}" for con in agent_config.constraints])
    
    # Create agent
    agent_response = await camel_client.create_agent(
        role=role_str,
        name=name or (agent_config.name if agent_config else f"{role_str}_agent"),
        system_message=system_message,
        model=model or (agent_config.model if agent_config else None),
        temperature=temperature or (agent_config.temperature if agent_config else None),
        max_tokens=max_tokens or (agent_config.max_tokens if agent_config else None),
        custom_parameters=custom_parameters or (agent_config.custom_parameters if agent_config else None)
    )
    
    if not agent_response.success:
        logger.error(f"Failed to create agent with role {role_str}: {agent_response.message}")
        return False, {"error": f"Failed to create agent: {agent_response.message}"}
    
    agent_data = agent_response.data
    agent_id = agent_data.get("agent_id")
    
    if agent_id:
        # Cache agent data
        _agent_cache[agent_id] = {
            "role": role_str,
            "name": agent_data.get("name"),
            "system_message": system_message,
            "model": agent_data.get("model"),
            "temperature": agent_data.get("temperature"),
            "max_tokens": agent_data.get("max_tokens"),
            "created_at": agent_data.get("created_at")
        }
    
    return True, agent_data

async def get_agent_by_role(
    role: Union[AgentRole, str],
    create_if_missing: bool = True
) -> Tuple[bool, Dict[str, Any]]:
    """
    Get an agent by role, creating it if it doesn't exist.
    
    Args:
        role: Agent role
        create_if_missing: Whether to create the agent if it doesn't exist
        
    Returns:
        Tuple of (success, agent_data)
    """
    # Convert role to string if it's an enum
    if isinstance(role, AgentRole):
        role_str = role.value
    else:
        role_str = role
    
    # Check if we have a cached agent with this role
    for agent_id, agent_data in _agent_cache.items():
        if agent_data.get("role") == role_str:
            # Verify agent still exists
            agent_response = await camel_client.get_agent(agent_id)
            if agent_response.success:
                return True, agent_response.data
            else:
                # Agent no longer exists, remove from cache
                del _agent_cache[agent_id]
                break
    
    # Create agent if it doesn't exist
    if create_if_missing:
        return await create_agent(role=role_str)
    else:
        return False, {"error": f"No agent found with role {role_str}"}

async def create_agent_team(
    roles: List[Union[AgentRole, str]],
    team_name: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create a team of agents with specified roles.
    
    Args:
        roles: List of agent roles
        team_name: Name for the team
        
    Returns:
        Tuple of (success, team_data)
    """
    team_data = {
        "name": team_name or f"team_{int(asyncio.get_event_loop().time())}",
        "agents": []
    }
    
    for role in roles:
        success, agent_data = await get_agent_by_role(role)
        if not success:
            logger.error(f"Failed to get agent with role {role}: {agent_data.get('error')}")
            return False, {"error": f"Failed to create team: {agent_data.get('error')}"}
        
        team_data["agents"].append(agent_data)
    
    return True, team_data

async def load_agent_templates(templates_dir: Optional[Union[str, Path]] = None) -> Dict[str, Dict[str, Any]]:
    """
    Load agent templates from JSON files.
    
    Args:
        templates_dir: Directory containing template files
        
    Returns:
        Dictionary of template name to template data
    """
    if templates_dir is None:
        templates_dir = os.path.join(os.getcwd(), "config", "agent_templates")
    
    templates_dir = Path(templates_dir)
    if not templates_dir.exists():
        logger.warning(f"Templates directory not found: {templates_dir}")
        return {}
    
    templates = {}
    
    for file_path in templates_dir.glob("*.json"):
        try:
            with open(file_path, 'r') as f:
                template_data = json.load(f)
            
            template_name = file_path.stem
            templates[template_name] = template_data
            logger.info(f"Loaded agent template: {template_name}")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading template from {file_path}: {str(e)}")
    
    return templates

async def create_agent_from_template(
    template_name: str,
    templates: Optional[Dict[str, Dict[str, Any]]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Create an agent from a template.
    
    Args:
        template_name: Name of the template
        templates: Dictionary of templates (if None, templates will be loaded)
        
    Returns:
        Tuple of (success, agent_data)
    """
    if templates is None:
        templates = await load_agent_templates()
    
    if template_name not in templates:
        logger.error(f"Template not found: {template_name}")
        return False, {"error": f"Template not found: {template_name}"}
    
    template = templates[template_name]
    
    return await create_agent(
        role=template.get("role", "assistant"),
        name=template.get("name"),
        system_message=template.get("system_message"),
        capabilities=template.get("capabilities"),
        constraints=template.get("constraints"),
        model=template.get("model"),
        temperature=template.get("temperature"),
        max_tokens=template.get("max_tokens"),
        custom_parameters=template.get("custom_parameters")
    )