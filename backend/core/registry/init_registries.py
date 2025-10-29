"""
Registry Initialization

Imports all domain registries to ensure agents are registered with the global registry.
This module must be imported during application startup to register all agents.
"""

import logging

logger = logging.getLogger(__name__)

def initialize_all_registries():
    """Initialize all domain registries by importing them."""
    try:
        # Import Agent Svea registry (already implemented)
        try:
            from backend.agents.agent_svea import registry as svea_registry
        except ImportError:
            from agents.agent_svea import registry as svea_registry
        logger.info("Agent Svea registry imported and agents registered")
        
        # Import Felicia's Finance registry
        try:
            from backend.agents.felicias_finance import registry as felicia_registry
        except ImportError:
            from agents.felicias_finance import registry as felicia_registry
        logger.info("Felicia's Finance registry imported and agents registered")
        
        # Import MeetMind registry
        try:
            from backend.agents.meetmind import registry as meetmind_registry
        except ImportError:
            from agents.meetmind import registry as meetmind_registry
        logger.info("MeetMind registry imported and agents registered")
        
        # Log the total number of registered agents
        from .agents import get_all_agents, get_registry_stats
        
        all_agents = get_all_agents()
        stats = get_registry_stats()
        
        logger.info(f"All registries initialized successfully")
        logger.info(f"Total agents registered: {len(all_agents)}")
        logger.info(f"Domains: {stats['domains']}")
        logger.info(f"Coordinators: {stats['coordinators']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize registries: {e}")
        return False