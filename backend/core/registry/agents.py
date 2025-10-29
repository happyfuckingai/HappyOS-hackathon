"""
Global Agent Registry

Single source of truth for all agents across all domains.
Provides factory pattern for agent creation and discovery.
"""

from typing import Callable, Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Global registry of all agents
REGISTRY: Dict[str, Callable[[], object]] = {}

def register(name: str):
    """
    Decorator to register an agent factory function.
    
    Usage:
        @register("felicia.coordinator")
        def build():
            return CoordinatorAgent(...)
    """
    def wrap(factory: Callable[[], object]):
        if name in REGISTRY:
            logger.warning(f"Agent '{name}' already registered, overwriting")
        
        REGISTRY[name] = factory
        logger.info(f"Registered agent: {name}")
        return factory
    return wrap

def build(name: str) -> object:
    """
    Build an agent instance by name.
    
    Args:
        name: Agent name (e.g., "felicia.coordinator")
        
    Returns:
        Agent instance
        
    Raises:
        ValueError: If agent not found in registry
    """
    if name not in REGISTRY:
        available = list(REGISTRY.keys())
        raise ValueError(f"Agent '{name}' not registered. Available: {available}")
    
    try:
        agent = REGISTRY[name]()
        logger.info(f"Built agent: {name}")
        return agent
    except Exception as e:
        logger.error(f"Failed to build agent '{name}': {e}")
        raise

def get_all_agents() -> List[str]:
    """Get list of all registered agent names."""
    return list(REGISTRY.keys())

def get_agents_by_domain(domain: str) -> List[str]:
    """
    Get all agents for a specific domain.
    
    Args:
        domain: Domain name (e.g., "felicia", "svea", "meetmind")
        
    Returns:
        List of agent names in that domain
    """
    return [name for name in REGISTRY.keys() if name.startswith(f"{domain}.")]

def get_coordinators() -> List[str]:
    """Get all coordinator agents (main entry points)."""
    return [name for name in REGISTRY.keys() if name.endswith(".coordinator")]

def is_registered(name: str) -> bool:
    """Check if an agent is registered."""
    return name in REGISTRY

def unregister(name: str) -> bool:
    """
    Unregister an agent.
    
    Args:
        name: Agent name to unregister
        
    Returns:
        True if agent was unregistered, False if not found
    """
    if name in REGISTRY:
        del REGISTRY[name]
        logger.info(f"Unregistered agent: {name}")
        return True
    return False

def clear_registry() -> None:
    """Clear all registered agents (mainly for testing)."""
    REGISTRY.clear()
    logger.info("Cleared agent registry")

def get_registry_stats() -> Dict[str, Any]:
    """Get registry statistics."""
    agents_by_domain = {}
    
    for name in REGISTRY.keys():
        domain = name.split('.')[0] if '.' in name else 'unknown'
        if domain not in agents_by_domain:
            agents_by_domain[domain] = []
        agents_by_domain[domain].append(name)
    
    return {
        "total_agents": len(REGISTRY),
        "domains": list(agents_by_domain.keys()),
        "agents_by_domain": agents_by_domain,
        "coordinators": get_coordinators()
    }